import base64
import hashlib
import hmac
import json
import os
import secrets
import time

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .db import get_db
from .models import User


TOKEN_SECRET = os.getenv("ZUNA_TOKEN_SECRET", "")
TOKEN_LIFETIME_SECONDS = 60 * 60 * 12
bearer = HTTPBearer(auto_error=False)


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt_text, expected = stored.split("$", 2)
        if scheme != "scrypt":
            return False
        salt = base64.urlsafe_b64decode(salt_text + "=" * (-len(salt_text) % 4))
        digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
        return hmac.compare_digest(_b64(digest), expected)
    except (ValueError, TypeError):
        return False


def _token_secret() -> bytes:
    if TOKEN_SECRET:
        return TOKEN_SECRET.encode("utf-8")
    if os.getenv("ZUNA_ENV", "development") == "production":
        raise HTTPException(status_code=500, detail="ZUNA_TOKEN_SECRET must be configured in production.")
    return b"local-zuna-development-only-token-secret"


def create_access_token(user: User) -> str:
    now = int(time.time())
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64(json.dumps({
        "sub": str(user.id),
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "iat": now,
        "exp": now + TOKEN_LIFETIME_SECONDS,
    }, separators=(",", ":")).encode())
    signing_input = f"{header}.{payload}".encode("ascii")
    signature = hmac.new(_token_secret(), signing_input, hashlib.sha256).digest()
    return f"{header}.{payload}.{_b64(signature)}"


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sign in to continue.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized
    try:
        header, payload, signature = credentials.credentials.split(".")
        signing_input = f"{header}.{payload}".encode("ascii")
        expected = _b64(hmac.new(_token_secret(), signing_input, hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise unauthorized
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        if int(claims["exp"]) <= int(time.time()):
            raise unauthorized
        user = db.get(User, int(claims["sub"]))
    except HTTPException:
        raise
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise unauthorized from None
    if user is None:
        raise unauthorized
    return user


def require_role(*roles: str):
    def role_dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Your account role cannot perform this action.")
        return user
    return role_dependency
