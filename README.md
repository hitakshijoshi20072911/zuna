# Zuna frontend

Zuna is an AI-assisted negotiation and social-commerce marketplace concept for Indian artisans, MSMEs and home-based businesses. This repository currently contains the **Phase 2 static frontend**: the Phase 1 brand foundation plus marketplace discovery and product detail demo flows.

## Stack

- HTML5, CSS3 and Vanilla JavaScript (ES6+)
- One entry point: `frontend/home.html`
- Primary application files: `frontend/home.html`, `frontend/index.css`, `frontend/index.js`
- Local editorial WebP assets under `frontend/assets/images/`
- No framework, bundler or UI library

## Local preview

From the repository root, serve the `frontend/` directory with any static server, for example:

```bash
cd frontend
python3 -m http.server 4173
```

Then open `http://localhost:4173/`. Because the entry point is `home.html`, the Vercel configuration rewrites `/` to `/home.html` when the project root is set to `frontend`.

## Routes in this phase

The frontend uses hash routes from the single HTML entry point:

- `#/` — homepage
- `#/marketplace` — Phase 2 marketplace with local search, category/price/availability/offer filters, sort modes, wishlist state and empty/loading states
- `#/product/:id` — Phase 2 product detail with gallery, seller story, stock state and a disabled offer-entry shell
- Other account, dashboard, collaboration and checkout routes — designed placeholders for later phases

## Demo limitations

Products, maker labels, prices and interactions are illustrative sample data. Phase 2 does not implement authentication, FastAPI calls, AI pricing, live offer submission, negotiation persistence, Razorpay checkout or a database. Wishlist state exists only in the current browser session, and the offer panel is intentionally disabled until the negotiation phase. No payment, login or seller operation is represented as successful. Later phases will add buyer, seller and creator flows behind backend validation.

## Vercel setup

Import the repository into Vercel with `frontend` as the Root Directory, framework preset **Other**, no build command and `.` as the output directory. With that recommended setting, `frontend/vercel.json` rewrites `/` to `/home.html`.

For projects that were already created with the repository root as Root Directory, the root-level `vercel.json` provides a compatibility rewrite from `/` to `/frontend/home.html`; this keeps the current production project from returning a root 404 while its Vercel setting is corrected. Do not set a build command or install dependencies. After changing Root Directory, redeploy and verify `/`, `/#/marketplace`, `/frontend/index.css` (root deployment) or `/index.css` (frontend-root deployment), and `/frontend/index.js` or `/index.js` respectively. The repository owner must connect and verify Vercel; deployment is not claimed until the public production URL returns the Zuna page.
