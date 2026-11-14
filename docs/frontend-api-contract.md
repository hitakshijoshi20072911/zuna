# Zuna API contract

The vanilla-JavaScript frontend uses the FastAPI service through `apiRequest()` in `frontend/index.js`. The default base is `/api/v1`; for a separately hosted API, configure the `zuna-api-base-url` meta value in `frontend/home.html` or define `window.ZUNA_API_BASE_URL` before loading the application. Browser state is never authoritative for account ownership, offer status, payable amounts, referral codes or payment verification.

## Accounts and catalogue

- `POST /api/v1/auth/register` — create a buyer, seller or creator account; returns a signed bearer token and public user profile.
- `POST /api/v1/auth/login` — authenticate with email and password.
- `GET /api/v1/auth/me` — validate the current account token.
- `GET /api/v1/products?q=&category=&available=&offers=&min_price=&max_price=&sort=` — browse and filter the catalogue.
- `GET /api/v1/products/{product_id}` — product detail.
- `POST /api/v1/products` and `PUT /api/v1/products/{product_id}` — seller-owned product management.
- `GET /api/v1/seller/products` — listings owned by the current seller.
- `GET /api/v1/users/me/wishlist` and `PUT /api/v1/users/me/wishlist/{product_id}` — persistent account wishlist.
- `POST /api/v1/seller/pricing/suggest` — seller-only estimate from unit cost, target margin, inventory age and demand index; returns its calculation inputs and explanation.

## Offers

- `POST /api/v1/products/{product_id}/offers` with `{amount}` — buyer creates an offer on an available seller-owned listing or illustrative sample product.
- `GET /api/v1/offers` — buyers see their offers; sellers see offers on their listings and sample-product offers in a shared seller inbox.
- `POST /api/v1/offers/{offer_id}/counter` with `{amount}` — listing owner counters, or a seller responds to a sample-product offer.
- `POST /api/v1/offers/{offer_id}/accept` — listing owner or seller-inbox seller accepts the current offer; the buyer can accept a seller counter.
- `POST /api/v1/offers/{offer_id}/reject` — listing owner or seller-inbox seller rejects an active offer.

When either party accepts an offer, the buyer sees a prompt to order at the accepted price. If they save it for later, the product is added to their saved products and the accepted-offer checkout link remains in their dashboard. Seller acceptances are surfaced while the buyer is using the app.
The API enforces account roles, listing ownership, expiry, stock and state transitions. Illustrative sample products support direct checkout at listed prices and negotiated-price checkout after acceptance.
Product responses include the current `stockQty`, `available`/`stock` status and size options; apparel and footwear have category-appropriate choices, while other items default to `One size`.
Seller-estimated `cost` is returned only to the listing owner and is omitted from public product and buyer-offer responses.

## Collaborations and referrals

- `GET /api/v1/collaborations/opportunities?category=&product_id=&status=&search=` — authenticated opportunity discovery; creator responses include their request state.
- `POST /api/v1/collaborations` — seller publishes an opportunity for an owned product.
- `POST /api/v1/collaborations/{id}/requests` — creator requests the opportunity.
- `GET /api/v1/collaborations/{id}/requests` — owning seller views creator requests.
- `POST /api/v1/collaborations/{id}/requests/{request_id}/accept` — owning seller accepts and the API issues a referral link.
- `POST /api/v1/collaborations/{id}/requests/{request_id}/reject` — owning seller rejects.
- `GET /api/v1/creator/referrals` — creator's referral links and server-recorded click/conversion counts.
- `POST /api/v1/referrals/{code}/visit` — validates a referral code and records a visit.

The browser preserves referral codes as opaque query values and does not invent IDs or report link rendering as a click. No social platform or external sharing API is connected.

## Checkout and payment boundary

- `POST /api/v1/checkout/sessions` with `{accepted_offer_id, size, payment_method, delivery_name, delivery_phone, delivery_address}` — requires the buyer's accepted offer and uses its accepted amount. `payment_method` is `razorpay` or `cod`; Razorpay returns a provider session, while COD creates an unpaid `cod_pending` order and reduces available stock. Delivery details are required for COD and supplied by the checkout UI for either method.
- `POST /api/v1/checkout/products` with `{product_id, size, payment_method, delivery_name, delivery_phone, delivery_address}` — requires an available product and buyer account, including illustrative samples. `payment_method` is `razorpay` or `cod`; Razorpay uses the listed price and returns a provider session, while COD creates an unpaid `cod_pending` order and reduces available stock.
- `POST /api/v1/payments/verify` — validates the callback signature and confirms Razorpay reports a captured payment of the matching amount before marking either order type paid.
- `GET /api/v1/orders` and `GET /api/v1/orders/{order_id}` — buyer-owned accepted-offer and direct-purchase orders, including selected size, expected delivery date and delivery time window.

Without server-side `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET`, online checkout explicitly returns `503` and creates no order; COD remains available. The browser never stores a secret, collects card details or marks a payment successful from a callback alone. COD is not marked paid when the order is placed.

## Errors and configuration

The API uses standard HTTP errors: `401` unauthenticated, `403` forbidden, `404` missing, `409` state/expiry conflicts, `422` invalid or unsupported business input, and `5xx` service/provider errors. The frontend shows these messages rather than substituting demo state.

Configure `ZUNA_TOKEN_SECRET`, `DATABASE_URL`, `ZUNA_ALLOWED_ORIGINS`, and optional Razorpay keys on the backend only. API interactive docs are available at `/docs`.
