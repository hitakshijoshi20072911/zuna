# Member 3 — AI Pricing, Negotiation & Payments

Files: `backend/app/pricing.py`, negotiation + payment sections of `backend/app/main.py`, `backend/tests/test_member3.py`.

## 1. Pricing engine (`pricing.py`)
- `C = M + L + P + O`; `Ps = C / (1 - m/100)` (30% margin on ₹250 -> ₹357).
- Adjustments: demand -10%..+10%, stock age 0.1%/day after 30 days (max 15%), +5% negotiation buffer.
- Negotiation floor keeps part of the margin (50% / 45% / 30% by stock age), never below cost.
- Stock-age bands (0-15, 16-30, 31-60, 60+) are *recommendations*; the seller decides.
- AI layer: optional Gemini (`GEMINI_API_KEY`) only rewords the explanation. Text is discarded if it
  contains a ₹ amount the engine did not calculate. No key / error / timeout -> rules explanation.
- Endpoint: `POST /api/v1/seller/pricing/suggest` (old `unit_cost` payload and new cost components both work).

## 2. Negotiation rules
| Rule | Where |
|---|---|
| Minimum price | `Product.min_price` (seller-set via `minPrice`) or automatic floor; accept/counter below it -> 422 |
| Offer expiry | `ZUNA_OFFER_EXPIRY_HOURS` (default 72); refreshed on counter |
| Counteroffers | not below buyer's offer, not above listing, not below minimum |
| Status | pending / countered / accepted / rejected / expired |
| Offer history | `events` list on each offer |
| Payment lock | only `accepted` offers reach checkout; amount read from DB; window `ZUNA_CHECKOUT_WINDOW_HOURS` (24) |
| Long-unsold hint | `insight` on seller offers (60+ days and offer >= minimum -> "Consider accepting...") |

## 3. Razorpay
1. Backend creates order for the accepted price. 2. Frontend opens Checkout. 3. Backend verifies
`HMAC_SHA256(order_id|payment_id, key_secret)` and fetches the payment from Razorpay. 4. Order becomes `paid` only then.
5. `POST /api/v1/payments/webhook` (secret `RAZORPAY_WEBHOOK_SECRET`) confirms `payment.captured` server-to-server; idempotent.

## Optional: show the seller hint in the UI
The frontend was left untouched, so `insight.message` is returned by the API but not drawn. To show it, add inside the seller
offer card template in `frontend/index.js`: `${offer.insight ? `<p class="muted">${offer.insight.message}</p>` : ""}`.

## Viva one-liners
- Why not ML? No reliable price dataset; rules are explainable. ML is future scope.
- Why verify signature? A browser "success" message can be faked; only the secret-key HMAC proves Razorpay issued it.
- How do you stop unprofitable acceptance? Backend compares price to minimum before accept/counter.
