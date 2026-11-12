# Zuna frontend API contract — Phase 5

The static frontend currently runs in explicit demo mode. `apiRequest()` in `frontend/index.js` is the single adapter boundary; it returns local demo state while `CONFIG.demoMode` is true and is the only place that should be extended for FastAPI calls. No browser state is authoritative.

## Collaboration

- `GET /api/v1/collaborations/opportunities?category=&product_id=&status=&search=` returns opportunities with product/business summaries, brief, supported terms and timestamps.
- `POST /api/v1/collaborations` creates an opportunity for an authorized seller.
- `POST /api/v1/collaborations/{id}/requests` creates a creator request.
- `GET /api/v1/collaborations/{id}/requests` lists requests visible to the authorized seller.
- `POST /api/v1/collaborations/{id}/requests/{request_id}/accept` returns accepted status and, when issued, a backend-generated referral link.
- `POST /api/v1/collaborations/{id}/requests/{request_id}/reject` returns rejected status.
- `GET /api/v1/creator/referrals` returns referral links and server-provided click/conversion metrics only.

The browser must never guess referral IDs or treat rendering a link as a click. Incoming `?ref=` values may be preserved as opaque, validated attribution context; the backend decides whether a code is valid and records a visit. External share destinations must be allowlisted.

## Checkout and payment boundary

- `POST /api/v1/checkout/sessions` with `{accepted_offer_id}` returns the server-created order/session, payable amount, currency, public Razorpay key ID, Razorpay order ID and expiry.
- `POST /api/v1/payments/verify` receives the checkout reference and Razorpay callback fields. The backend verifies the signature and payment status.
- `GET /api/v1/orders/{order_id}` returns the authorized order and verified payment state.

The frontend never calculates or overwrites the negotiated amount, stores a secret, collects card details, or marks an order paid from a browser callback. Demo checkout intentionally ends at “pending verification”.

## Error and state expectations

The UI must distinguish `400` validation, `401` unauthenticated, `403` forbidden, `404` missing, `409` expired/conflict, `422` business validation and `5xx`/timeout retry states. Accepted offers are checkout-eligible only while the backend says they are valid.

## Environment names

- `ZUNA_API_BASE_URL` — public API origin/configuration input.
- `ZUNA_DEMO_MODE` — frontend demo/live switch.
- `RAZORPAY_KEY_ID` — public key ID returned/configured for test checkout only.

`RAZORPAY_KEY_SECRET`, database credentials and signing secrets must remain server-side.
