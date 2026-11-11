# Zuna frontend

Zuna is an AI-assisted negotiation and social-commerce marketplace concept for Indian artisans, MSMEs and home-based businesses. This repository currently contains the **Phase 3 static frontend**: the Phase 1 brand foundation, Phase 2 marketplace discovery and Phase 3 authentication UI plus role-based demo experiences.

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
- `#/login` and `#/register` — validated demo sign-in/profile forms with password visibility controls and buyer/seller/creator role selection
- `#/buyer` — buyer overview with sample offers, order history and session-only saved products
- `#/seller` — seller overview with listing summary, stock-age indicators and pending offers
- `#/seller/products` — seller product table with add and edit actions
- `#/seller/products/new` and `#/seller/products/:id/edit` — validated product forms for session-only demo listings
- `#/creator` — creator profile and collaboration summary
- Later pricing, offers, collaborations and checkout routes remain designed placeholders for later phases

## Demo limitations

Products, maker labels, prices, offers, orders, creator metrics and interactions are illustrative sample data. Phase 3 uses an explicit **in-memory demo session** only: it is not secure authentication, does not store plaintext passwords, and does not provide authorization. Enter any fictional email and a password of at least eight characters, choose a role, and use the Reset control or refresh the page to clear the session. Product add/edit changes and wishlist changes last only until refresh/reset. FastAPI, database persistence, real authentication, AI pricing, live offer submission, negotiation persistence and Razorpay checkout are not implemented. No payment, login or seller operation is represented as successful.

## Phase 3 demo walkthrough

1. Open `#/register`, enter a fictional name/email, choose Buyer, Seller or Creator, and create a demo session.
2. Use the role-aware navigation to open the matching dashboard. Directly opening a different role route shows a clear role-mismatch state rather than exposing that dashboard.
3. In the Seller dashboard, open **Manage products**, add a sample product, then edit it from the product table. The updated values remain coherent during the current in-memory session.
4. Use **Reset** in the shared navigation, or refresh the page, to clear the demo session and return to sign-in. Backend authorization remains mandatory for a real application.

## Vercel setup

Import the repository into Vercel with `frontend` as the Root Directory, framework preset **Other**, no build command and `.` as the output directory. With that recommended setting, `frontend/vercel.json` rewrites `/` to `/home.html`.

For projects that were already created with the repository root as Root Directory, the root-level `vercel.json` provides compatibility rewrites for `/`, `/index.css`, `/index.js`, `/assets/*` and `/manus-routes.json`; this keeps the current production project working while its Vercel setting is corrected. Do not set a build command or install dependencies. After changing Root Directory, redeploy and verify `/`, `/#/marketplace`, the CSS file, the JavaScript file and an image asset. The repository owner must connect and verify Vercel; deployment is not claimed until the public production URL returns the styled Zuna page.
