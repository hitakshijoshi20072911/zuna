# Zuna marketplace

Zuna is an editorial marketplace for independent makers, buyers and creators. The existing vanilla-JavaScript frontend now uses a FastAPI backend and a persistent SQLite database for accounts, listings, wishlists, offers, collaborations, referrals and orders.

## Stack

- Frontend: HTML, CSS and vanilla JavaScript in `frontend/`
- Backend: Python 3.10+, FastAPI, SQLAlchemy 2 and Pydantic
- Database: SQLite by default; configure `DATABASE_URL` to use another SQLAlchemy-supported database
- Payments: Razorpay Orders and server-side signature/status verification when server credentials are configured

## Run locally on Windows

From the repository root in PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
python -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/`. FastAPI serves the existing frontend and the API from the same origin. API documentation is at `http://127.0.0.1:8000/docs`; health check is `/api/v1/health`.

On first startup, the API creates `backend/zuna.db` and seeds the fictional catalogue used by the existing design. New user data is persisted across restarts. The database file is ignored by Git.

## Configuration

Set secrets in the backend process environment; never put them in browser code:

- `ZUNA_TOKEN_SECRET` — required for production; use a high-entropy secret. Development has a local-only fallback.
- `ZUNA_ENV=production` — makes the server fail closed if `ZUNA_TOKEN_SECRET` is missing.
- `DATABASE_URL` — optional SQLAlchemy URL; defaults to `backend/zuna.db`.
- `ZUNA_ALLOWED_ORIGINS` — comma-separated browser origins when the frontend is hosted separately.
- `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET` — optional server-side Razorpay credentials. Without both, online checkout returns `503`; cash-on-delivery orders remain available.

The frontend defaults to `/api/v1`. To host it separately, change the `zuna-api-base-url` meta value in `frontend/home.html` to the backend API base URL (including `/api/v1`), or define `window.ZUNA_API_BASE_URL` before `index.js` loads.

## Functional flows

- Register and sign in as buyer, seller or creator; passwords are stored as scrypt hashes and API requests use expiring signed bearer tokens.
- Browse and filter the seeded and seller-created catalogue. Product pages show other in-stock options from the same product family when defined, or from the same category otherwise; sellers can create and edit only their own listings.
- Save products to the signed-in buyer's persistent wishlist.
- Buyers can negotiate on seller-owned listings and sample products; listing owners manage their offers, while sellers can respond to sample-product offers through the shared seller inbox.
- Sellers can request an explainable price estimate from cost, target margin, inventory age and demand inputs; this bounded formula is explicitly not an AI prediction.
- Sellers publish collaboration opportunities for their listings. Creators request them; only the owning seller can review requests. Approval issues backend-generated referral links and visit counts are recorded by the API.
- Buyers can purchase available products at listed or accepted negotiated prices using Razorpay (UPI, cards, net banking or wallets) or cash on delivery. Online orders become paid only after server-side signature and captured-payment verification; COD orders remain unpaid until payment is collected at delivery.

The seeded catalogue is illustrative and is not owned by an account. Buyers can place direct orders at listed prices or negotiate a sample product price and check out after acceptance.

## Tests

```powershell
python -m unittest discover -s backend\tests -v
node --check frontend\index.js
```

The API tests cover authentication, catalogue reads, seller ownership, offer negotiation, direct product checkout, COD order creation, collaboration approval/referral tracking and Razorpay verification with mocked provider responses. A live Razorpay transaction requires valid server-side test credentials.

## Deployment

Deploy FastAPI and the database as a backend service with persistent disk storage for SQLite (or configure a managed database). Static frontend hosting may remain on Vercel; set its `zuna-api-base-url` to the deployed API base and configure `ZUNA_ALLOWED_ORIGINS` on the API. Do not expose Razorpay secrets, JWT signing secrets or database credentials to the browser. SQLite files on ephemeral serverless storage are not persistent; use a managed database for that deployment model.
