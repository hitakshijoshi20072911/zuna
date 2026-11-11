# Zuna frontend

Zuna is an AI-assisted negotiation and social-commerce marketplace concept for Indian artisans, MSMEs and home-based businesses. This repository currently contains the **Phase 1 static frontend** only.

## Stack

- HTML5, CSS3 and Vanilla JavaScript (ES6+)
- One entry point: `frontend/home.html`
- Primary application files: `frontend/home.html`, `frontend/index.css`, `frontend/index.js`
- Local editorial JPG assets under `frontend/assets/images/`
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
- `#/marketplace` — Phase 1 marketplace preview with sample cards
- Other product, account, dashboard, collaboration and checkout routes — designed placeholders for later phases

## Demo limitations

Products, maker labels, prices and interactions are illustrative sample data. Phase 1 does not implement authentication, FastAPI calls, AI pricing, negotiation persistence, Razorpay checkout or a database. No payment, login or seller operation is represented as successful. Later phases will add the buyer, seller and creator flows behind backend validation.

## Vercel setup

Import the repository into Vercel with `frontend` as the Root Directory, framework preset **Other**, no build command and `.` as the output directory. The included `frontend/vercel.json` rewrites `/` to `/home.html`. The repository owner must connect and verify Vercel; deployment has not been claimed from this repository workflow.
