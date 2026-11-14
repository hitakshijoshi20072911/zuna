import hashlib
import hmac
import json
import os
import re
import secrets
import urllib.error
import urllib.request
import uuid
import base64
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from .db import Base, engine, ensure_order_checkout_columns, get_db
from .models import (
    CollaborationOpportunity,
    CollaborationRequest,
    Offer,
    OfferEvent,
    Order,
    Product,
    ProductOrder,
    Referral,
    User,
    utcnow,
    wishlist_items,
)
from .schemas import (
    CheckoutCreate,
    OpportunityCreate,
    OfferCounter,
    OfferCreate,
    PaymentVerify,
    PricingRequest,
    ProductCheckoutCreate,
    ProductWrite,
    UserCreate,
    UserLogin,
    WishlistUpdate,
)
from .security import create_access_token, get_current_user, hash_password, require_role, verify_password
from .seed import seed_data


ROOT_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIR = ROOT_DIR / "frontend"
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
API_PREFIX = "/api/v1"
DELIVERY_TIME_WINDOW = "9:00 AM–6:00 PM IST"
DELIVERY_BUSINESS_DAYS = 5
INDIA_TIMEZONE = timezone(timedelta(hours=5, minutes=30))


def _product_size_options(product: Product) -> list[str]:
    tags = {tag.strip().lower() for tag in product.tags.split(",")}
    name = product.name.lower()
    if "saree" in name or "saree" in tags:
        return ["Free size"]
    if product.category == "Fashion & Footwear":
        if tags.intersection({"sneakers", "flats", "footwear"}) or any(
            word in name for word in ("sneaker", "flat", "shoe")
        ):
            return ["UK 6", "UK 7", "UK 8", "UK 9", "UK 10"]
        if tags.intersection({"shirt", "tee", "overshirt", "clothing"}) or any(
            word in name for word in ("shirt", "tee", "overshirt")
        ):
            return ["XS", "S", "M", "L", "XL"]
    if product.category == "Jewellery" and tags.intersection({"ring", "rings"}):
        return ["US 6", "US 7", "US 8", "US 9"]
    return ["One size"]


def _selected_product_size(product: Product, requested_size: str | None) -> str:
    sizes = _product_size_options(product)
    if requested_size is None:
        return sizes[0]
    if requested_size not in sizes:
        raise HTTPException(status_code=422, detail="Choose a valid size for this product.")
    return requested_size


def _expected_delivery(created_at: datetime) -> dict[str, str]:
    placed_at = created_at
    if placed_at.tzinfo is None:
        placed_at = placed_at.replace(tzinfo=timezone.utc)
    delivery_date = placed_at.astimezone(INDIA_TIMEZONE).date()
    business_days = 0
    while business_days < DELIVERY_BUSINESS_DAYS:
        delivery_date += timedelta(days=1)
        if delivery_date.weekday() < 5:
            business_days += 1
    return {
        "date": delivery_date.isoformat(),
        "window": DELIVERY_TIME_WINDOW,
    }


def _deduct_product_stock(product: Product) -> None:
    if not product.available or product.stock_qty < 1:
        raise HTTPException(status_code=409, detail="This product is no longer available.")
    product.stock_qty -= 1
    product.available = product.stock_qty > 0


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_order_checkout_columns()
    with Session(engine) as db:
        seed_data(db)
    yield


app = FastAPI(title="Zuna Marketplace API", version="1.0.0", lifespan=lifespan)
allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "ZUNA_ALLOWED_ORIGINS",
        "http://localhost:4173,http://127.0.0.1:4173,http://localhost:8000,http://127.0.0.1:8000",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


def _serialize_user(user: User) -> dict[str, Any]:
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role}


def _serialize_product(product: Product, include_cost: bool = False) -> dict[str, Any]:
    tags = [tag for tag in product.tags.split(",") if tag]
    family = next((tag.partition(":")[2] for tag in tags if tag.startswith("family:")), "")
    available = product.available and product.stock_qty > 0
    serialized = {
        "id": product.id,
        "name": product.name,
        "maker": product.maker,
        "seller": product.seller,
        "ownerId": product.owner_id,
        "isSample": product.owner_id is None,
        "region": product.region,
        "price": product.price,
        "image": product.image,
        "offers": product.offers or product.owner_id is None,
        "available": available,
        "sizes": _product_size_options(product),
        "category": product.category,
        "tags": [tag for tag in tags if not tag.startswith("family:")],
        "variantGroup": family.replace("-", " ").title() if family else product.category,
        "addedOrder": product.added_order,
        "stock": f"{product.stock_qty} in stock" if available else "Out of stock",
        "stockQty": product.stock_qty,
        "age": product.age,
        "description": product.description,
        "story": product.story,
        "createdAt": product.created_at.isoformat(),
    }
    if include_cost:
        serialized["cost"] = product.cost
    return serialized


def _serialize_offer(offer: Offer, include_cost: bool = False) -> dict[str, Any]:
    return {
        "id": offer.id,
        "productId": offer.product_id,
        "product": _serialize_product(
            offer.product,
            include_cost=include_cost and offer.product.owner_id is not None,
        ),
        "offeredPrice": offer.offered_price,
        "counterPrice": offer.counter_price,
        "acceptedPrice": offer.accepted_price,
        "status": offer.status,
        "expiresAt": offer.expires_at.isoformat(),
        "history": [
            {
                "actor": event.actor.name,
                "amount": event.amount,
                "status": event.status,
                "time": event.created_at.isoformat(),
            }
            for event in offer.events
        ],
    }


def _serialize_opportunity(
    opportunity: CollaborationOpportunity,
    my_request: CollaborationRequest | None = None,
) -> dict[str, Any]:
    return {
        "id": opportunity.public_id,
        "productId": opportunity.product_id,
        "product": _serialize_product(opportunity.product),
        "business": opportunity.product.seller,
        "type": opportunity.collaboration_type,
        "brief": opportunity.brief,
        "terms": opportunity.terms,
        "category": opportunity.category,
        "status": opportunity.status,
        "sellerId": opportunity.seller_id,
        "createdAt": opportunity.created_at.isoformat(),
        "request": (
            {"id": my_request.id, "status": my_request.status}
            if my_request is not None
            else None
        ),
    }


def _date_is_expired(value: datetime) -> bool:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value <= datetime.now(timezone.utc)


def _expire_offer(offer: Offer, db: Session) -> None:
    if offer.status in {"pending", "countered", "accepted"} and _date_is_expired(offer.expires_at):
        offer.status = "expired"
        db.add(OfferEvent(
            offer=offer,
            actor_id=offer.buyer_id,
            amount=offer.accepted_price or offer.counter_price or offer.offered_price,
            status="expired",
        ))
        db.commit()
        db.refresh(offer)


def _get_offer(offer_id: int, db: Session) -> Offer:
    offer = db.scalar(
        select(Offer)
        .options(joinedload(Offer.product), joinedload(Offer.events).joinedload(OfferEvent.actor))
        .where(Offer.id == offer_id)
    )
    if offer is None:
        raise HTTPException(status_code=404, detail="Offer not found.")
    _expire_offer(offer, db)
    return offer


def _require_offer_access(offer: Offer, user: User) -> None:
    if offer.buyer_id != user.id and offer.product.owner_id != user.id:
        raise HTTPException(status_code=403, detail="You cannot access this offer.")


def _razorpay_request(path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
        raise HTTPException(
            status_code=503,
            detail="Razorpay is not configured. Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET on the server.",
        )
    credentials = f"{RAZORPAY_KEY_ID}:{RAZORPAY_KEY_SECRET}".encode("utf-8")
    request_data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        f"https://api.razorpay.com/v1{path}",
        data=request_data,
        headers={
            "Authorization": "Basic " + base64.b64encode(credentials).decode("ascii"),
            "Content-Type": "application/json",
        },
        method="POST" if payload is not None else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise HTTPException(status_code=502, detail=f"Razorpay request failed ({error.code}): {detail[:300]}") from error
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=502, detail="Razorpay could not be reached. Retry the checkout.") from error


@app.get(f"{API_PREFIX}/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(f"{API_PREFIX}/auth/register", status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
    email = str(payload.email).strip().lower()
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    user = User(name=payload.name, email=email, password_hash=hash_password(payload.password), role=payload.role)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists.") from None
    db.refresh(user)
    return {"access_token": create_access_token(user), "token_type": "bearer", "user": _serialize_user(user)}


@app.post(f"{API_PREFIX}/auth/login")
def login(payload: UserLogin, db: Session = Depends(get_db)) -> dict[str, Any]:
    email = str(payload.email).strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    return {"access_token": create_access_token(user), "token_type": "bearer", "user": _serialize_user(user)}


@app.get(f"{API_PREFIX}/auth/me")
def current_account(user: User = Depends(get_current_user)) -> dict[str, Any]:
    return _serialize_user(user)


@app.get(f"{API_PREFIX}/products")
def list_products(
    q: str = Query(default="", max_length=120),
    category: str = Query(default="", max_length=100),
    available: bool | None = None,
    offers: bool | None = None,
    min_price: int | None = Query(default=None, ge=0),
    max_price: int | None = Query(default=None, ge=0),
    sort: str = Query(default="featured", pattern="^(featured|price-low|price-high|recent)$"),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    statement = select(Product)
    if q.strip():
        term = f"%{q.strip()}%"
        statement = statement.where(or_(
            Product.name.ilike(term),
            Product.maker.ilike(term),
            Product.category.ilike(term),
            Product.tags.ilike(term),
            Product.description.ilike(term),
        ))
    if category:
        statement = statement.where(Product.category == category)
    if available is True:
        statement = statement.where(and_(Product.available.is_(True), Product.stock_qty > 0))
    elif available is False:
        statement = statement.where(or_(Product.available.is_(False), Product.stock_qty <= 0))
    if offers is True:
        statement = statement.where(Product.offers.is_(offers))
    elif offers is False:
        statement = statement.where(Product.offers.is_(False))
    if min_price is not None:
        statement = statement.where(Product.price >= min_price)
    if max_price is not None:
        statement = statement.where(Product.price <= max_price)
    products = list(db.scalars(statement).all())
    if sort == "price-low":
        products.sort(key=lambda product: product.price)
    elif sort == "price-high":
        products.sort(key=lambda product: product.price, reverse=True)
    elif sort == "recent":
        products.sort(key=lambda product: (product.created_at, product.added_order), reverse=True)
    else:
        products.sort(
            key=lambda product: (product.offers, product.added_order),
            reverse=True,
        )
    return [_serialize_product(product) for product in products]


@app.get(f"{API_PREFIX}/products/{{product_id}}")
def get_product(product_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found.")
    return _serialize_product(product)


@app.get(f"{API_PREFIX}/seller/products")
def seller_products(
    db: Session = Depends(get_db),
    seller: User = Depends(require_role("seller")),
) -> list[dict[str, Any]]:
    products = db.scalars(select(Product).where(Product.owner_id == seller.id).order_by(Product.created_at.desc())).all()
    return [_serialize_product(product, include_cost=True) for product in products]


def _safe_product_image(image: str) -> str:
    if not (image.startswith("./assets/") or image.startswith("/assets/")):
        raise HTTPException(status_code=422, detail="Choose a local image from the existing Zuna asset library.")
    if ".." in image:
        raise HTTPException(status_code=422, detail="Product image path is invalid.")
    return image


def _apply_product_write(product: Product, payload: ProductWrite, user: User) -> None:
    product.name = payload.name.strip()
    product.category = payload.category.strip()
    product.price = payload.price
    product.cost = payload.cost
    product.stock_qty = payload.stockQty
    product.available = payload.stockQty > 0
    product.age = payload.age
    product.image = _safe_product_image(payload.image)
    product.offers = payload.offers
    product.description = payload.description.strip()
    product.maker = f"{user.name} · maker"
    product.seller = f"{user.name}'s studio"
    product.story = "A product listing managed by its verified Zuna seller account."
    product.region = "India"


@app.post(f"{API_PREFIX}/products", status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductWrite,
    db: Session = Depends(get_db),
    seller: User = Depends(require_role("seller")),
) -> dict[str, Any]:
    product_id = re.sub(r"[^a-z0-9]+", "-", payload.name.lower()).strip("-")[:48] or "product"
    product_id = f"{product_id}-{secrets.token_hex(4)}"
    product = Product(
        id=product_id,
        owner_id=seller.id,
        tags=payload.category.lower(),
        added_order=(db.scalar(select(Product.added_order).order_by(Product.added_order.desc()).limit(1)) or 0) + 1,
        stock_qty=payload.stockQty,
        available=payload.stockQty > 0,
        name=payload.name.strip(),
        maker="",
        seller="",
        region="India",
        price=payload.price,
        cost=payload.cost,
        image=_safe_product_image(payload.image),
        offers=payload.offers,
        category=payload.category.strip(),
        description=payload.description.strip(),
        story="",
        age=payload.age,
    )
    _apply_product_write(product, payload, seller)
    db.add(product)
    db.commit()
    db.refresh(product)
    return _serialize_product(product, include_cost=True)


@app.put(f"{API_PREFIX}/products/{{product_id}}")
def update_product(
    product_id: str,
    payload: ProductWrite,
    db: Session = Depends(get_db),
    seller: User = Depends(require_role("seller")),
) -> dict[str, Any]:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found.")
    if product.owner_id != seller.id:
        raise HTTPException(status_code=403, detail="You can only edit products owned by your account.")
    _apply_product_write(product, payload, seller)
    db.commit()
    db.refresh(product)
    return _serialize_product(product, include_cost=True)


@app.post(f"{API_PREFIX}/seller/pricing/suggest")
def suggest_price(
    payload: PricingRequest,
    _seller: User = Depends(require_role("seller")),
) -> dict[str, Any]:
    target_margin = payload.target_margin_percent / 100
    base_price = payload.unit_cost / (1 - target_margin)
    age_discount = min(0.15, max(0, payload.inventory_age_days - 30) * 0.001)
    demand_adjustment = (payload.demand_index - 50) / 50 * 0.1
    adjusted = base_price * (1 - age_discount) * (1 + demand_adjustment)
    suggested_price = max(payload.unit_cost, int(round(adjusted / 10) * 10))
    actual_margin = (suggested_price - payload.unit_cost) / suggested_price * 100
    return {
        "unitCost": payload.unit_cost,
        "targetMarginPercent": payload.target_margin_percent,
        "inventoryAgeDays": payload.inventory_age_days,
        "demandIndex": payload.demand_index,
        "basePrice": int(round(base_price)),
        "suggestedPrice": suggested_price,
        "actualMarginPercent": round(actual_margin, 1),
        "adjustmentPercent": round(((1 - age_discount) * (1 + demand_adjustment) - 1) * 100, 1),
        "explanation": (
            "This transparent estimate starts with cost and target margin, then applies "
            "bounded inventory-age and demand adjustments. It is not an AI prediction."
        ),
    }


@app.get(f"{API_PREFIX}/users/me/wishlist")
def get_wishlist(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[str]:
    return list(db.scalars(select(wishlist_items.c.product_id).where(wishlist_items.c.user_id == user.id)).all())


@app.put(f"{API_PREFIX}/users/me/wishlist/{{product_id}}")
def update_wishlist(
    product_id: str,
    payload: WishlistUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    if db.get(Product, product_id) is None:
        raise HTTPException(status_code=404, detail="Product not found.")
    existing = db.execute(
        select(wishlist_items.c.product_id).where(
            wishlist_items.c.user_id == user.id,
            wishlist_items.c.product_id == product_id,
        )
    ).first()
    if payload.saved and existing is None:
        db.execute(wishlist_items.insert().values(user_id=user.id, product_id=product_id))
    elif not payload.saved and existing is not None:
        db.execute(wishlist_items.delete().where(
            wishlist_items.c.user_id == user.id,
            wishlist_items.c.product_id == product_id,
        ))
    db.commit()
    return {"productId": product_id, "saved": payload.saved}


@app.post(f"{API_PREFIX}/products/{{product_id}}/offers", status_code=status.HTTP_201_CREATED)
def create_offer(
    product_id: str,
    payload: OfferCreate,
    db: Session = Depends(get_db),
    buyer: User = Depends(require_role("buyer")),
) -> dict[str, Any]:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found.")
    if product.owner_id == buyer.id:
        raise HTTPException(status_code=403, detail="You cannot make an offer on your own listing.")
    if not product.available or product.stock_qty < 1:
        raise HTTPException(status_code=409, detail="This product is currently unavailable.")
    if product.owner_id is not None and not product.offers:
        raise HTTPException(status_code=422, detail="This listing is not accepting offers.")
    if payload.amount > product.price:
        raise HTTPException(status_code=422, detail="An offer cannot exceed the listing price.")
    pending = db.scalar(select(Offer.id).where(
        Offer.product_id == product_id,
        Offer.buyer_id == buyer.id,
        Offer.status.in_(["pending", "countered"]),
    ))
    if pending is not None:
        raise HTTPException(status_code=409, detail="You already have an active offer for this product.")
    offer = Offer(
        product_id=product_id,
        buyer_id=buyer.id,
        offered_price=payload.amount,
        status="pending",
        expires_at=datetime.now(timezone.utc) + timedelta(days=3),
    )
    db.add(offer)
    db.flush()
    db.add(OfferEvent(offer_id=offer.id, actor_id=buyer.id, amount=payload.amount, status="pending"))
    db.commit()
    return _serialize_offer(_get_offer(offer.id, db))


@app.get(f"{API_PREFIX}/offers")
def list_offers(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    statement = select(Offer).options(
        joinedload(Offer.product),
        joinedload(Offer.events).joinedload(OfferEvent.actor),
    )
    if user.role == "buyer":
        statement = statement.where(Offer.buyer_id == user.id)
    elif user.role == "seller":
        statement = statement.join(Product).where(
            or_(Product.owner_id == user.id, Product.owner_id.is_(None))
        )
    else:
        return []
    offers = list(db.scalars(statement.order_by(Offer.created_at.desc())).unique().all())
    for offer in offers:
        _expire_offer(offer, db)
    return [_serialize_offer(offer, include_cost=user.role == "seller") for offer in offers]


@app.post(f"{API_PREFIX}/offers/{{offer_id}}/counter")
def counter_offer(
    offer_id: int,
    payload: OfferCounter,
    db: Session = Depends(get_db),
    seller: User = Depends(require_role("seller")),
) -> dict[str, Any]:
    offer = _get_offer(offer_id, db)
    if offer.product.owner_id != seller.id and offer.product.owner_id is not None:
        raise HTTPException(status_code=403, detail="You can only counter offers on your listings or sample products.")
    if offer.status not in {"pending", "countered"}:
        raise HTTPException(status_code=409, detail="This offer can no longer be changed.")
    if payload.amount > offer.product.price:
        raise HTTPException(status_code=422, detail="A counter cannot be higher than the listing price.")
    offer.counter_price = payload.amount
    offer.status = "countered"
    db.add(OfferEvent(offer=offer, actor_id=seller.id, amount=payload.amount, status="countered"))
    db.commit()
    return _serialize_offer(_get_offer(offer.id, db), include_cost=True)


@app.post(f"{API_PREFIX}/offers/{{offer_id}}/accept")
def accept_offer(
    offer_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    offer = _get_offer(offer_id, db)
    if offer.status not in {"pending", "countered"}:
        raise HTTPException(status_code=409, detail="This offer is no longer available to accept.")
    if user.role == "seller" and (
        offer.product.owner_id == user.id or offer.product.owner_id is None
    ):
        actor_id = user.id
        accepted_price = offer.counter_price or offer.offered_price
    elif (
        user.role == "buyer"
        and offer.buyer_id == user.id
        and offer.status == "countered"
        and offer.counter_price
    ):
        actor_id = user.id
        accepted_price = offer.counter_price
    else:
        raise HTTPException(status_code=403, detail="You cannot accept this offer.")
    reserved = db.scalar(select(func.count(Offer.id)).where(
        Offer.product_id == offer.product_id,
        Offer.status == "accepted",
        Offer.id != offer.id,
        Offer.id.not_in(select(Order.offer_id).where(Order.payment_status == "paid")),
    )) or 0
    if offer.product.stock_qty - reserved <= 0:
        raise HTTPException(status_code=409, detail="There is no unreserved stock available for this offer.")
    offer.status = "accepted"
    offer.accepted_price = accepted_price
    db.add(OfferEvent(offer=offer, actor_id=actor_id, amount=offer.accepted_price, status="accepted"))
    db.commit()
    return _serialize_offer(_get_offer(offer.id, db), include_cost=user.role == "seller")


@app.post(f"{API_PREFIX}/offers/{{offer_id}}/reject")
def reject_offer(
    offer_id: int,
    db: Session = Depends(get_db),
    seller: User = Depends(require_role("seller")),
) -> dict[str, Any]:
    offer = _get_offer(offer_id, db)
    if offer.product.owner_id != seller.id and offer.product.owner_id is not None:
        raise HTTPException(status_code=403, detail="You can only reject offers on your listings or sample products.")
    if offer.status not in {"pending", "countered"}:
        raise HTTPException(status_code=409, detail="This offer is no longer available to reject.")
    offer.status = "rejected"
    db.add(OfferEvent(offer=offer, actor_id=seller.id, amount=offer.counter_price or offer.offered_price, status="rejected"))
    db.commit()
    return _serialize_offer(_get_offer(offer.id, db), include_cost=True)


@app.get(f"{API_PREFIX}/collaborations/opportunities")
def list_opportunities(
    category: str = Query(default="", max_length=100),
    product_id: str = Query(default="", max_length=80),
    status_filter: str = Query(default="", alias="status", max_length=20),
    search: str = Query(default="", max_length=120),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    statement = select(CollaborationOpportunity).options(joinedload(CollaborationOpportunity.product))
    if category:
        statement = statement.where(CollaborationOpportunity.category == category)
    if product_id:
        statement = statement.where(CollaborationOpportunity.product_id == product_id)
    if status_filter:
        statement = statement.where(CollaborationOpportunity.status == status_filter.lower())
    if search.strip():
        term = f"%{search.strip()}%"
        statement = statement.join(Product).where(or_(
            CollaborationOpportunity.brief.ilike(term),
            CollaborationOpportunity.collaboration_type.ilike(term),
            Product.name.ilike(term),
            Product.seller.ilike(term),
        ))
    opportunities = list(db.scalars(statement.order_by(CollaborationOpportunity.created_at.desc())).unique().all())
    my_requests = {}
    if user.role == "creator":
        rows = db.scalars(select(CollaborationRequest).where(
            CollaborationRequest.creator_id == user.id,
            CollaborationRequest.opportunity_id.in_([item.id for item in opportunities]),
        )).all() if opportunities else []
        my_requests = {request.opportunity_id: request for request in rows}
    return [_serialize_opportunity(item, my_requests.get(item.id)) for item in opportunities]


@app.post(f"{API_PREFIX}/collaborations", status_code=status.HTTP_201_CREATED)
def create_opportunity(
    payload: OpportunityCreate,
    db: Session = Depends(get_db),
    seller: User = Depends(require_role("seller")),
) -> dict[str, Any]:
    product = db.get(Product, payload.product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found.")
    if product.owner_id != seller.id:
        raise HTTPException(status_code=403, detail="A collaboration must reference one of your listings.")
    opportunity = CollaborationOpportunity(
        public_id=f"collab-{secrets.token_hex(8)}",
        seller_id=seller.id,
        product_id=product.id,
        category=product.category,
        collaboration_type=payload.collaboration_type.strip(),
        brief=payload.brief.strip(),
        terms=payload.terms.strip(),
    )
    db.add(opportunity)
    db.commit()
    db.refresh(opportunity)
    return _serialize_opportunity(opportunity)


def _get_opportunity(public_id: str, db: Session) -> CollaborationOpportunity:
    item = db.scalar(
        select(CollaborationOpportunity)
        .options(joinedload(CollaborationOpportunity.product))
        .where(CollaborationOpportunity.public_id == public_id)
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Collaboration opportunity not found.")
    return item


@app.post(f"{API_PREFIX}/collaborations/{{public_id}}/requests", status_code=status.HTTP_201_CREATED)
def request_collaboration(
    public_id: str,
    db: Session = Depends(get_db),
    creator: User = Depends(require_role("creator")),
) -> dict[str, Any]:
    opportunity = _get_opportunity(public_id, db)
    if opportunity.status != "open":
        raise HTTPException(status_code=409, detail="This opportunity is no longer open.")
    existing = db.scalar(select(CollaborationRequest).where(
        CollaborationRequest.opportunity_id == opportunity.id,
        CollaborationRequest.creator_id == creator.id,
    ))
    if existing is not None:
        raise HTTPException(status_code=409, detail="You have already requested this collaboration.")
    request = CollaborationRequest(opportunity_id=opportunity.id, creator_id=creator.id)
    db.add(request)
    db.commit()
    db.refresh(request)
    return {"id": request.id, "opportunityId": public_id, "status": request.status, "createdAt": request.created_at.isoformat()}


@app.get(f"{API_PREFIX}/collaborations/{{public_id}}/requests")
def list_collaboration_requests(
    public_id: str,
    db: Session = Depends(get_db),
    seller: User = Depends(require_role("seller")),
) -> list[dict[str, Any]]:
    opportunity = _get_opportunity(public_id, db)
    if opportunity.seller_id != seller.id:
        raise HTTPException(status_code=403, detail="You can only view requests for your own opportunities.")
    requests = db.scalars(
        select(CollaborationRequest)
        .options(joinedload(CollaborationRequest.creator))
        .where(CollaborationRequest.opportunity_id == opportunity.id)
        .order_by(CollaborationRequest.created_at.desc())
    ).unique().all()
    return [
        {
            "id": request.id,
            "status": request.status,
            "creator": _serialize_user(request.creator),
            "createdAt": request.created_at.isoformat(),
        }
        for request in requests
    ]


def _review_collaboration_request(public_id: str, request_id: int, db: Session, seller: User) -> CollaborationRequest:
    request = db.scalar(
        select(CollaborationRequest)
        .options(joinedload(CollaborationRequest.opportunity).joinedload(CollaborationOpportunity.product))
        .where(CollaborationRequest.id == request_id)
    )
    if request is None or request.opportunity.public_id != public_id:
        raise HTTPException(status_code=404, detail="Collaboration request not found.")
    if request.opportunity.seller_id != seller.id:
        raise HTTPException(status_code=403, detail="You can only review requests for your own opportunities.")
    if request.status != "pending":
        raise HTTPException(status_code=409, detail="This request has already been reviewed.")
    return request


@app.post(f"{API_PREFIX}/collaborations/{{public_id}}/requests/{{request_id}}/accept")
def accept_collaboration(
    public_id: str,
    request_id: int,
    db: Session = Depends(get_db),
    seller: User = Depends(require_role("seller")),
) -> dict[str, Any]:
    request = _review_collaboration_request(public_id, request_id, db, seller)
    request.status = "accepted"
    referral = Referral(code=secrets.token_urlsafe(16), request_id=request.id)
    db.add(referral)
    db.commit()
    return {
        "id": request.id,
        "status": request.status,
        "referralLink": f"/?ref={referral.code}#/product/{request.opportunity.product_id}",
    }


@app.post(f"{API_PREFIX}/collaborations/{{public_id}}/requests/{{request_id}}/reject")
def reject_collaboration(
    public_id: str,
    request_id: int,
    db: Session = Depends(get_db),
    seller: User = Depends(require_role("seller")),
) -> dict[str, Any]:
    request = _review_collaboration_request(public_id, request_id, db, seller)
    request.status = "rejected"
    db.commit()
    return {"id": request.id, "status": request.status}


@app.get(f"{API_PREFIX}/creator/referrals")
def creator_referrals(
    db: Session = Depends(get_db),
    creator: User = Depends(require_role("creator")),
) -> list[dict[str, Any]]:
    referrals = db.scalars(
        select(Referral)
        .join(CollaborationRequest)
        .where(CollaborationRequest.creator_id == creator.id)
        .order_by(Referral.created_at.desc())
    ).all()
    return [
        {
            "code": referral.code,
            "link": f"/?ref={referral.code}#/product/{referral.request.opportunity.product_id}",
            "opportunityId": referral.request.opportunity.public_id,
            "clicks": referral.clicks,
            "conversions": referral.conversions,
            "createdAt": referral.created_at.isoformat(),
        }
        for referral in referrals
    ]


@app.post(f"{API_PREFIX}/referrals/{{code}}/visit")
def record_referral_visit(code: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    referral = db.scalar(select(Referral).where(Referral.code == code))
    if referral is None:
        raise HTTPException(status_code=404, detail="Referral code is not valid.")
    referral.clicks += 1
    db.commit()
    return {"valid": True}


@app.post(f"{API_PREFIX}/checkout/sessions", status_code=status.HTTP_201_CREATED)
def create_checkout_session(
    payload: CheckoutCreate,
    db: Session = Depends(get_db),
    buyer: User = Depends(require_role("buyer")),
) -> dict[str, Any]:
    offer = _get_offer(payload.accepted_offer_id, db)
    if offer.buyer_id != buyer.id:
        raise HTTPException(status_code=403, detail="This accepted offer belongs to another buyer.")
    if offer.status != "accepted" or offer.accepted_price is None:
        raise HTTPException(status_code=409, detail="Checkout is available only for an accepted offer.")
    if offer.status != "accepted":
        raise HTTPException(status_code=409, detail="This accepted offer has expired. Ask the seller for a new offer.")
    referral = None
    if payload.referral_code:
        referral = db.scalar(select(Referral).where(Referral.code == payload.referral_code))
        if referral is None:
            raise HTTPException(status_code=422, detail="Referral code is not valid.")
    existing = db.scalar(select(Order).where(Order.offer_id == offer.id))
    if not offer.product.available or offer.product.stock_qty < 1:
        if existing is None:
            raise HTTPException(status_code=409, detail="This product is no longer available.")
    if existing is not None and existing.payment_status not in {"pending", "cod_pending"}:
        raise HTTPException(status_code=409, detail="This offer already has a completed order.")
    existing_method = (
        existing.payment_method or ("razorpay" if existing.razorpay_order_id else None)
        if existing is not None
        else None
    )
    if existing_method is not None and existing_method != payload.payment_method:
        raise HTTPException(status_code=409, detail="Checkout for this offer has already started with a different payment method.")
    size = _selected_product_size(offer.product, payload.size or (existing.size if existing else None))
    if existing is not None and existing.size is not None and existing.size != size:
        raise HTTPException(status_code=409, detail="This order has already been started with a different size.")
    if payload.payment_method == "cod":
        if not payload.delivery_name or not payload.delivery_phone or not payload.delivery_address:
            raise HTTPException(status_code=422, detail="Delivery details are required for cash on delivery.")
        order = existing or Order(
            id=str(uuid.uuid4()),
            buyer_id=buyer.id,
            offer_id=offer.id,
            referral_id=referral.id if referral else None,
            amount=offer.accepted_price,
            currency="INR",
            payment_status="cod_pending",
            payment_method="cod",
        )
        order.delivery_name = payload.delivery_name
        order.delivery_phone = payload.delivery_phone
        order.delivery_address = payload.delivery_address
        order.size = size
        if existing is None:
            _deduct_product_stock(offer.product)
        db.add(order)
        db.commit()
        return {
            "order_id": order.id,
            "accepted_offer_id": offer.id,
            "amount": order.amount,
            "currency": order.currency,
            "payment_method": "cod",
            "payment_status": order.payment_status,
        }
    if existing is not None and existing.razorpay_order_id:
        existing.payment_method = "razorpay"
        existing.delivery_name = payload.delivery_name
        existing.delivery_phone = payload.delivery_phone
        existing.delivery_address = payload.delivery_address
        db.commit()
        return {
            "order_id": existing.id,
            "accepted_offer_id": offer.id,
            "amount": existing.amount,
            "currency": existing.currency,
            "key_id": RAZORPAY_KEY_ID,
            "razorpay_order_id": existing.razorpay_order_id,
            "expires_at": existing.created_at.isoformat(),
        }
    order_id = existing.id if existing else str(uuid.uuid4())
    razorpay_order = _razorpay_request("/orders", {
        "amount": offer.accepted_price * 100,
        "currency": "INR",
        "receipt": order_id,
        "notes": {"zuna_order_id": order_id, "offer_id": str(offer.id)},
    })
    order = existing or Order(
        id=order_id,
        buyer_id=buyer.id,
        offer_id=offer.id,
        referral_id=referral.id if referral else None,
        amount=offer.accepted_price,
        currency="INR",
    )
    order.payment_method = "razorpay"
    order.delivery_name = payload.delivery_name
    order.delivery_phone = payload.delivery_phone
    order.delivery_address = payload.delivery_address
    order.size = size
    order.razorpay_order_id = razorpay_order["id"]
    db.add(order)
    db.commit()
    return {
        "order_id": order.id,
        "accepted_offer_id": offer.id,
        "amount": order.amount,
        "currency": order.currency,
        "key_id": RAZORPAY_KEY_ID,
        "razorpay_order_id": order.razorpay_order_id,
        "expires_at": order.created_at.isoformat(),
    }


@app.post(f"{API_PREFIX}/checkout/products", status_code=status.HTTP_201_CREATED)
def create_product_checkout(
    payload: ProductCheckoutCreate,
    db: Session = Depends(get_db),
    buyer: User = Depends(require_role("buyer")),
) -> dict[str, Any]:
    product = db.get(Product, payload.product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found.")
    if product.owner_id == buyer.id:
        raise HTTPException(status_code=409, detail="You cannot purchase your own product.")
    if not product.available or product.stock_qty < 1:
        raise HTTPException(status_code=409, detail="This product is no longer available.")
    size = _selected_product_size(product, payload.size)

    order_id = str(uuid.uuid4())
    order = ProductOrder(
        id=order_id,
        buyer_id=buyer.id,
        product_id=product.id,
        amount=product.price,
        currency="INR",
        payment_method=payload.payment_method,
        payment_status="cod_pending" if payload.payment_method == "cod" else "pending",
        size=size,
        delivery_name=payload.delivery_name,
        delivery_phone=payload.delivery_phone,
        delivery_address=payload.delivery_address,
    )
    if payload.payment_method == "cod":
        _deduct_product_stock(product)
        db.add(order)
        db.commit()
        return _serialize_product_order(order)

    razorpay_order = _razorpay_request("/orders", {
        "amount": product.price * 100,
        "currency": "INR",
        "receipt": order_id,
        "notes": {"zuna_order_id": order_id, "product_id": product.id},
    })
    order.razorpay_order_id = razorpay_order["id"]
    db.add(order)
    db.commit()
    return {
        **_serialize_product_order(order),
        "key_id": RAZORPAY_KEY_ID,
        "razorpay_order_id": order.razorpay_order_id,
    }


def _serialize_order(order: Order) -> dict[str, Any]:
    return {
        "id": order.id,
        "offerId": order.offer_id,
        "product": _serialize_product(order.offer.product),
        "amount": order.amount,
        "currency": order.currency,
        "paymentMethod": order.payment_method or "razorpay",
        "paymentStatus": order.payment_status,
        "size": order.size,
        "expectedDelivery": _expected_delivery(order.created_at),
        "delivery": {
            "name": order.delivery_name,
            "phone": order.delivery_phone,
            "address": order.delivery_address,
        } if order.delivery_name or order.delivery_phone or order.delivery_address else None,
        "razorpayOrderId": order.razorpay_order_id,
        "createdAt": order.created_at.isoformat(),
    }


def _serialize_product_order(order: ProductOrder) -> dict[str, Any]:
    return {
        "id": order.id,
        "product": _serialize_product(order.product),
        "amount": order.amount,
        "currency": order.currency,
        "paymentMethod": order.payment_method,
        "paymentStatus": order.payment_status,
        "size": order.size,
        "expectedDelivery": _expected_delivery(order.created_at),
        "delivery": {
            "name": order.delivery_name,
            "phone": order.delivery_phone,
            "address": order.delivery_address,
        },
        "razorpayOrderId": order.razorpay_order_id,
        "createdAt": order.created_at.isoformat(),
    }


@app.get(f"{API_PREFIX}/orders")
def list_orders(
    db: Session = Depends(get_db),
    buyer: User = Depends(require_role("buyer")),
) -> list[dict[str, Any]]:
    orders = db.scalars(
        select(Order)
        .options(joinedload(Order.offer).joinedload(Offer.product))
        .where(Order.buyer_id == buyer.id)
    ).unique().all()
    product_orders = db.scalars(
        select(ProductOrder)
        .options(joinedload(ProductOrder.product))
        .where(ProductOrder.buyer_id == buyer.id)
    ).unique().all()
    serialized = [_serialize_order(order) for order in orders]
    serialized.extend(_serialize_product_order(order) for order in product_orders)
    return sorted(serialized, key=lambda order: order["createdAt"], reverse=True)


@app.get(f"{API_PREFIX}/orders/{{order_id}}")
def get_order(
    order_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    order = db.scalar(
        select(Order)
        .options(joinedload(Order.offer).joinedload(Offer.product))
        .where(Order.id == order_id)
    )
    if order is not None:
        if order.buyer_id != user.id:
            raise HTTPException(status_code=403, detail="You cannot access this order.")
        return _serialize_order(order)
    product_order = db.scalar(
        select(ProductOrder)
        .options(joinedload(ProductOrder.product))
        .where(ProductOrder.id == order_id)
    )
    if product_order is None:
        raise HTTPException(status_code=404, detail="Order not found.")
    if product_order.buyer_id != user.id:
        raise HTTPException(status_code=403, detail="You cannot access this order.")
    return _serialize_product_order(product_order)


@app.post(f"{API_PREFIX}/payments/verify")
def verify_payment(
    payload: PaymentVerify,
    db: Session = Depends(get_db),
    buyer: User = Depends(require_role("buyer")),
) -> dict[str, Any]:
    order = db.scalar(
        select(Order)
        .options(joinedload(Order.offer).joinedload(Offer.product))
        .where(Order.id == payload.order_id)
    )
    product_order = None
    if order is None:
        product_order = db.scalar(
            select(ProductOrder)
            .options(joinedload(ProductOrder.product))
            .where(ProductOrder.id == payload.order_id)
        )
    if order is None and product_order is None:
        raise HTTPException(status_code=404, detail="Order not found.")
    checkout_order = order or product_order
    product = order.offer.product if order is not None else product_order.product
    if checkout_order.buyer_id != buyer.id:
        raise HTTPException(status_code=403, detail="You cannot verify another buyer's order.")
    if checkout_order.payment_method == "cod":
        raise HTTPException(status_code=409, detail="Cash-on-delivery orders cannot be verified as online payments.")
    if checkout_order.payment_status == "paid":
        if checkout_order.razorpay_payment_id == payload.razorpay_payment_id:
            return _serialize_order(order) if order is not None else _serialize_product_order(product_order)
        raise HTTPException(status_code=409, detail="This order already has a verified payment.")
    if not checkout_order.razorpay_order_id or checkout_order.razorpay_order_id != payload.razorpay_order_id:
        raise HTTPException(status_code=422, detail="Payment order does not match this checkout.")
    if not RAZORPAY_KEY_SECRET:
        raise HTTPException(status_code=503, detail="Payment verification is unavailable because Razorpay is not configured.")
    message = f"{payload.razorpay_order_id}|{payload.razorpay_payment_id}".encode("utf-8")
    expected = hmac.new(RAZORPAY_KEY_SECRET.encode("utf-8"), message, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, payload.razorpay_signature):
        raise HTTPException(status_code=422, detail="Payment signature is invalid.")
    payment = _razorpay_request(f"/payments/{payload.razorpay_payment_id}")
    if payment.get("order_id") != checkout_order.razorpay_order_id or payment.get("status") != "captured":
        raise HTTPException(status_code=409, detail="Razorpay has not confirmed a captured payment.")
    if int(payment.get("amount", 0)) != checkout_order.amount * 100 or payment.get("currency") != checkout_order.currency:
        raise HTTPException(status_code=409, detail="Verified payment amount does not match this order.")
    if not product.available or product.stock_qty < 1:
        raise HTTPException(status_code=409, detail="This product sold out before payment completed.")
    checkout_order.payment_status = "paid"
    checkout_order.razorpay_payment_id = payload.razorpay_payment_id
    _deduct_product_stock(product)
    if order is not None and order.referral_id:
        referral = db.get(Referral, order.referral_id)
        if referral is not None:
            referral.conversions += 1
    db.commit()
    return _serialize_order(order) if order is not None else _serialize_product_order(product_order)


@app.get("/")
def frontend_entry() -> FileResponse:
    if not (FRONTEND_DIR / "home.html").exists():
        raise HTTPException(status_code=404, detail="Frontend entry point not found.")
    return FileResponse(FRONTEND_DIR / "home.html")


if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR), name="frontend")
