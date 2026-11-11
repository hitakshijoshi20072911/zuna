# Zuna — Frontend Development Phases

**Project:** Zuna — AI-Powered Negotiation & Social Commerce Marketplace  
**Repository:** `https://github.com/hitakshijoshi20072911/zuna`  
**Frontend stack:** HTML5, CSS3, Vanilla JavaScript (ES6+)  
**Backend planned separately:** Python + FastAPI  
**Database planned separately:** SQLite + SQLAlchemy  
**Deployment target:** Vercel (static frontend initially)

> This file is the working source of truth for the frontend roadmap. Update the status, implementation notes, screenshots, decisions and known issues at the end of every phase. Do not mark work complete unless it exists in the repository and has been checked.

---

## Non-negotiable technical constraints

1. Frontend application code lives in `frontend/`.
2. The three primary application files are exactly:
   - `frontend/home.html`
   - `frontend/index.css`
   - `frontend/index.js`
3. Use only HTML, CSS and Vanilla JavaScript. No React, Vue, Angular, Svelte, JSX, TypeScript, build system, bundler or UI framework.
4. Do not add a dependency merely for convenience. No Three.js, GSAP, Lenis, jQuery, Bootstrap or Tailwind in the MVP. Recreate the desired motion using CSS, native browser APIs, `IntersectionObserver` and carefully scoped `requestAnimationFrame` effects.
5. Additional static assets are allowed under `frontend/assets/`. Keep the application logic in the three primary files. `frontend/vercel.json` may be used for Vercel routing.
6. Keep the code readable for a second-year undergraduate viva. Prefer named functions, small modules/sections, descriptive variables and comments explaining non-obvious logic.
7. All user-facing data must be rendered safely. Escape dynamic text before inserting it into HTML. Do not use `eval`, `new Function`, inline event-handler attributes or unsafe HTML injection.
8. The frontend must be backend-ready, but this frontend project must not implement the FastAPI backend or database.
9. Never put Razorpay secret keys, Gemini keys, JWT secrets, passwords or other private credentials in HTML, CSS, JavaScript, Git history or Vercel client-side environment variables. Browser code may use only public configuration such as an API base URL.
10. Do not make the interface pretend that a payment, login, seller settlement, AI prediction or API operation succeeded when it is only a demo. Clearly label mock/demo behaviour.
11. Respect accessibility: semantic HTML, keyboard access, visible focus, labels, sufficient contrast, reduced-motion support and responsive layouts.
12. Do not invent platform statistics, seller counts, customer reviews, delivery guarantees, marketplace impact metrics or verified claims. Demo products and demo interactions must be identifiable as sample data.

## Visual direction

Zuna should feel like a contemporary Indian craft and commerce house: heritage-inspired, editorial, warm, elegant and useful. It must not resemble a generic marketplace template or a dark, cluttered dashboard.

### Brand palette

| Token | Hex | Intended use |
|---|---|---|
| Blood Red | `#74070E` | Main brand accent, important CTA, active states |
| Vanilla | `#F4E3B2` | Warm highlight, soft section background, contrast on dark |
| Drab Dark Brown | `#45462A` | Earthy green-brown surfaces and secondary accents |
| Cinereous | `#947268` | Muted surfaces, dividers and secondary text |
| Black Bean | `#310E10` | Deep sections, footer and high-contrast panels |

Use warm ivory/vanilla as the dominant canvas, Blood Red sparingly for emphasis, Black Bean for selected dramatic sections, Drab Dark Brown for earthy contrast, and Cinereous for restrained secondary details. Define all colours as CSS custom properties. Avoid using all colours at equal intensity.

### Typography and visual language

- Display: elegant high-contrast serif, e.g. Cormorant Garamond.
- Interface/body: clean sans-serif, e.g. DM Sans or Manrope.
- Use no more than two primary families plus an optional restrained label face.
- Oversized editorial headings, compact uppercase eyebrow labels, generous line-height and clear hierarchy.
- Art direction: Indian craft, textiles, ceramics, handmade jewellery, carved wood, brass, block prints, heritage architecture and natural materials.
- Use real, high-quality product/editorial imagery. Prefer downloaded, optimized local WebP/AVIF assets in `frontend/assets/images/`; record image source/licence notes in `frontend/assets/ASSETS.md`. Do not use broken image links or unstable random-image endpoints.
- Decorative arches, fine rules, subtle grain, borders and ornamental motifs should be restrained and CSS/SVG-based. Avoid excessive mandalas, paisley clip-art, gradients, glassmorphism and gold-on-everything styling.

### Motion direction

Take inspiration from the *feel* of Lenis: immersive scroll-led storytelling, intentional reveals, smooth transitions, layered imagery and cohesive motion. Do not copy the site, its exact layout, assets or code.

Implement with native scrolling and:
- subtle hero image parallax, not scroll hijacking;
- IntersectionObserver-based reveal on entry;
- gentle image/card hover movement;
- a small scroll-progress indicator;
- restrained section transitions and marquee/ticker movement;
- reduced-motion fallback using `prefers-reduced-motion`.

Do not replace the browser scrollbar, trap scrolling, or force smooth scrolling when reduced motion is requested. Keep motion subtle and performant on mid-range phones and laptops.

---

## Frontend route map

Implement a small hash-routed single-page application so the project keeps one HTML entry point and one JavaScript file while still presenting distinct pages. The three core files remain the only application source files.

| Route | Screen | Main content |
|---|---|---|
| `#/` | Home | Brand story, hero, curated products, category discovery, maker/creator entry points |
| `#/marketplace` | Marketplace | Search, categories, sort, filters, product grid, empty/loading states |
| `#/product/:id` | Product detail | Image gallery, seller story, price, stock status, make-an-offer panel |
| `#/login` | Login | Email/password form, validation, role-aware entry after sign-in |
| `#/register` | Register | Name, email, password, buyer/seller/creator role choice |
| `#/buyer` | Buyer dashboard | Overview, active offers, order history, saved products |
| `#/seller` | Seller dashboard | Business overview, listing and offer summaries, stock-age indicators |
| `#/seller/products` | Product management | Product table/grid, status, edit and add product actions |
| `#/seller/products/new` | Add product | Product details, images, costs, inventory and negotiation settings |
| `#/seller/products/:id/edit` | Edit product | Pre-filled product form and validation |
| `#/seller/pricing` | Smart pricing | Cost inputs, margin, inventory age, demand, suggested price and explanation |
| `#/seller/offers` | Negotiation management | Pending offers, accept/reject/counter actions, history and expiry |
| `#/creator` | Creator dashboard | Creator profile, collaboration opportunities, active links and referral summary |
| `#/collaborations` | Collaboration marketplace | Seller opportunities, request/accept states and referral link views |
| `#/checkout` | Checkout | Accepted-offer summary, agreed price and payment state; demo only until backend integration |
| `#/order-confirmation` | Order confirmation | Clear pending/paid/failed demo state and order summary |

Use shared components and tabs where appropriate. A route may render a view within a common application shell; do not duplicate the global header/footer across separate HTML pages.

---

# Phase 1 — Brand foundation, application shell and homepage

**Goal:** Establish the visual system and build a polished, responsive homepage that establishes Zuna's identity.

### Deliverables

- Repository inspection and safe Git workflow.
- `phases.md` at repository root, updated to show the current phase.
- `frontend/home.html`, `frontend/index.css`, `frontend/index.js` connected correctly.
- Optional `frontend/vercel.json` to serve `home.html` at `/` when the Vercel project root is `frontend`.
- CSS design tokens for the full palette, typography, spacing, radii, shadows and breakpoints.
- Shared header/navigation, mobile menu, footer, buttons, labels and reusable product-card foundation.
- Homepage sections:
  1. Slim announcement/brand strip.
  2. Editorial navigation with Zuna wordmark.
  3. Immersive hero with headline, short explanation, primary marketplace CTA and secondary maker CTA.
  4. Craft/category discovery row.
  5. Curated product collection with sample products.
  6. Three-value proposition section: price with confidence, negotiate with clarity, grow through collaboration.
  7. Artisan/maker editorial spotlight.
  8. Simple three-step negotiation explainer.
  9. Seller/creator call-to-action.
  10. Brand footer with useful links.
- Responsive layouts for mobile, tablet and desktop.
- Native motion: hero parallax, reveal-on-scroll, hover states and reduced-motion fallback.
- Clear demo data labels where sample inventory is used.

### Acceptance criteria

- `/` loads reliably and no console errors occur.
- All primary navigation and homepage CTAs have meaningful destinations, even if later routes initially show designed placeholder views.
- Visual hierarchy is strong at 360px mobile width, tablet and desktop.
- All buttons/links are keyboard operable; focus is visible.
- Reduced-motion mode disables non-essential motion.
- No external UI framework or JavaScript animation library is introduced.
- The three requested core frontend files exist at the exact paths.
- Add screenshots to the PR description and update this file with implemented sections, decisions and known gaps.

### Git / review

Create branch `manus/phase-01-foundation`. Open one PR into `main`. Do not merge it. Wait for the repository owner to review and merge.

**Status:** Implemented on `manus/phase-01-foundation`; PR pending review  
**PR:** https://github.com/hitakshijoshi20072911/zuna/pull/1  
**Notes / decisions:** Built the responsive editorial homepage, shared shell, mobile navigation, hash router, route placeholders, demo product cards, native reveal/parallax/progress motion, reduced-motion fallback, Vercel root rewrite and local original image assets. Product labels, prices and maker identities are explicitly fictional demo data. Phase 1 intentionally does not implement authentication, backend calls, pricing logic, negotiation persistence or payments. Browser and responsive checks are recorded in the PR description.

---

# Phase 2 — Marketplace discovery and product details

**Goal:** Make the buyer-facing shopping journey complete and convincing.

### Deliverables

- Marketplace route with search, category chips, sort controls and filters (category, price band, availability and open-to-offers status).
- Responsive product grid and reusable product-card component.
- Product detail route with image gallery, price, seller identity/story, product details, stock information and negotiation entry point.
- Wishlist/save interaction in demo state.
- Search, filter, sort, clear-filter and empty-state behaviours.
- Product data kept in one mock-data layer, never duplicated throughout templates.
- API adapter functions prepared for later FastAPI integration; mock mode must be explicit.

### Acceptance criteria

- Search, filters, sorting and wishlist work against local demo data.
- Product cards open the correct product detail route.
- Product information is consistent across marketplace, detail and dashboard views.
- Empty states and missing-image fallbacks are designed.
- All states are usable on mobile and keyboard accessible.

### Git / review

Create branch `manus/phase-02-marketplace` from the latest merged `main`. Open a PR; do not merge.

**Status:** Implemented on `manus/phase-02-marketplace`; PR pending review
**PR:** https://github.com/hitakshijoshi20072911/zuna/pull/2
**Notes / decisions:** Added working local search across product metadata, category/price/availability/open-to-offers filters, featured/price/recent sorting, clear-filter and no-results states, demo wishlist state, loading state, reusable safe-rendered product cards, product detail routes with gallery thumbnails, seller story, stock status and a disabled offer-entry shell. Added missing-image fallback handling and retained the Phase 1 design system. All catalogue data remains illustrative mock data; API adapter functions stay in explicit demo mode and no offer or wishlist state is persisted to a backend.

---

# Phase 3 — Authentication experience and role-based dashboards

**Goal:** Build the interface for buyers, sellers and creators without pretending frontend-only authentication is secure.

### Deliverables

- Login and registration forms with client-side validation and clear error/success states.
- Role selection for buyer, seller and creator during registration.
- Shared navigation that adapts to the selected demo role.
- Buyer dashboard: profile summary, current offers, order history and saved products.
- Seller dashboard: overview cards, product summary, pending offers and inventory ageing.
- Seller product management: list, add and edit product forms, including cost inputs and stock/listing details.
- Creator dashboard: creator profile, available collaboration opportunities and referral-link presentation.
- Demo-only session state that can be reset; no claim of real authentication or authorization.

### Acceptance criteria

- Forms validate required fields and display understandable messages.
- Role switching is consistent in demo mode and does not expose another role's controls accidentally in the UI.
- Dashboard figures are identified as demo/sample data.
- Protected-route behaviour is only a frontend demonstration; backend authorization remains mandatory later.
- Product add/edit flows update mock state consistently until refresh/reset, with the persistence limitation disclosed.

### Git / review

Create branch `manus/phase-03-roles-dashboards`. Open a PR; do not merge.

**Status:** Implemented on `manus/phase-03-roles-dashboards`; PR pending review  
**PR:** —  
**Notes / decisions:** Added in-memory demo sessions for buyer, seller and creator roles; login/register validation with password visibility toggles and understandable inline errors; role-aware shared navigation; buyer, seller and creator dashboards; seller product list/add/edit flows; direct-route guards and role-mismatch states; empty saved-products state; inventory-age indicators; and responsive Phase 3 styling. Password values are validated only during form submission and are never copied into session state or browser storage. Product and wishlist changes are session-only and reset on refresh or the shared Reset control. Validation evidence: `node --check frontend/index.js`, source smoke checks, browser route checks for register, seller dashboard and seller-to-buyer mismatch, no browser console output, plus responsive screenshots in `qa-phase-3/` (`register-desktop.png`, `register-mobile.png`, `seller-dashboard-desktop.webp`, `role-mismatch-desktop.webp`). FastAPI authentication/authorization and persistence remain intentionally out of scope.

---

# Phase 4 — Smart pricing and dynamic negotiation interfaces

**Goal:** Make Zuna's two primary USPs demonstrable through clear, explainable interfaces.

### Deliverables

- Seller smart-pricing screen with material, labour, packaging and other costs; desired margin; inventory age; demand selection.
- Display total cost, initial price, adjusted suggested listing price, seller-entered minimum/negotiation floor and estimated profit.
- Explain the calculation in plain language, including the distinction between the deterministic pricing engine and optional AI explanation.
- Use the documented version-one formula: `C = M + L + P + O`; `Ps = C / (1 - m/100)`; apply inventory-age/demand recommendations only as explainable adjustments.
- Do not invent a trained ML model or imply that Gemini determines the price. Any generated explanation must never override backend-calculated price or seller minimum.
- Buyer offer panel on product detail, with amount validation and offer status.
- Seller offers screen with pending, accepted, rejected, countered and expired states; history and expiry presentation.
- Counteroffer flow and buyer acceptance flow in mock mode.
- Seller minimum-price explanation and long-unsold stock context.
- Checkout entry available only for an accepted offer in demo state.

### Acceptance criteria

- Pricing calculations show inputs and outputs transparently; edge cases (zero/negative cost, margin below 0 or at/above 100, empty values) are handled.
- Displayed sample calculations are labelled illustrative.
- Frontend does not decide final transaction prices; backend will revalidate accepted offers and seller minimums.
- Rejected/expired offers cannot reach the demo checkout state.
- Each offer action visibly updates the mock UI and history.
- No live payment or real AI API call is made in this phase.

### Git / review

Create branch `manus/phase-04-pricing-negotiation`. Open a PR; do not merge.

**Status:** Not started  
**PR:** —  
**Notes / decisions:** —

---

# Phase 5 — Creator collaboration, checkout states, integration readiness and QA

**Goal:** Complete the MVP frontend flows and make the code straightforward to connect to FastAPI.

### Deliverables

- Seller collaboration request interface.
- Creator opportunity discovery and request-to-collaborate flow.
- Seller accept/reject collaboration states.
- Unique referral-code/link presentation and copy-to-clipboard interaction.
- Demo click/conversion metrics clearly marked as sample data; no fabricated Instagram integration or auto-posting.
- Checkout and order-confirmation screens prepared for Razorpay Standard Checkout integration later. No secret key or real payment verification in browser code.
- Central API adapter in `index.js` with configurable `API_BASE_URL`, common `apiRequest()` error handling and named functions for auth, products, offers, pricing, collaborations and orders.
- Document proposed frontend-to-backend API contract in `docs/FRONTEND_API_CONTRACT.md` for backend coordination. Mark endpoint names and request/response shapes as proposed until agreed with the backend owner.
- Loading, empty, error, success, offline and unauthorized states.
- Final accessibility, responsive, performance and cross-browser pass.
- README setup instructions, demo credentials (non-sensitive), route map, architecture overview and known limitations.
- Update `phases.md` with actual status, PRs, decisions, screenshots and unresolved issues.

### Acceptance criteria

- The seller-to-creator collaboration journey is demonstrable end to end in mock mode.
- Referral links can be copied and tracking is clearly a frontend demo until backend storage exists.
- Checkout is reachable only from a valid accepted-offer state in the demo flow.
- API calls are isolated behind named adapter functions; view rendering does not contain raw fetch logic everywhere.
- API base URL is configurable without exposing private credentials.
- No secret keys, passwords or real customer data are committed.
- No console errors, broken navigation or major layout overflow across key viewports.
- Backend integration points and demo limitations are documented honestly.

### Git / review

Create branch `manus/phase-05-integration-readiness`. Open a PR; do not merge.

**Status:** Not started  
**PR:** —  
**Notes / decisions:** —

---

## GitHub, PR and deployment workflow

1. Work only in the repository `hitakshijoshi20072911/zuna`.
2. Inspect the current branch and repository before editing. Never assume files exist.
3. Keep `main` protected by workflow, even if GitHub branch protection is not configured.
4. Create one phase branch per phase using the exact names above. Do not work directly on `main`.
5. Commit coherent changes with descriptive messages. Do not include API keys, `.env` files, credentials, user data or unrelated files.
6. Run available checks before opening the PR: HTML validation or inspection, JavaScript syntax check, CSS review, responsive checks and browser console inspection. Add automated tests only if they can be kept lightweight and do not require a framework.
7. Open a PR to `main` with: summary, screenshots, changed files, test evidence, acceptance checklist, known issues and next phase.
8. **Never merge the PR, force-push, delete branches, or rewrite history.** The repository owner reviews and merges each PR.
9. Start the next phase only after the previous PR is merged, unless the repository owner explicitly authorizes parallel work.
10. Update `phases.md` in the same PR as the phase implementation.

### Vercel deployment setup

- Import the GitHub repository into Vercel after Phase 1 has a reviewable preview.
- Set **Root Directory** to `frontend` and framework preset to **Other**.
- There is no build command and no package installation for this static frontend.
- Use `frontend/vercel.json` to rewrite `/` to `/home.html`; all internal navigation uses hash routes (`#/...`) so it does not require server-side route rewrites.
- Confirm `/`, `/#/marketplace` and static CSS/JS assets load in the Vercel preview.
- Connect production deployment to `main`; PR deployments should be preview deployments.
- Do not configure backend URLs or secrets until the backend exists. A public API base URL can be added later; private keys must stay on the server.
- If the Vercel project UI or account authorization is not available to the agent, provide the owner with exact setup instructions instead of claiming deployment has been completed.

---

## Overall project completion checklist

- [ ] Phase 1 PR reviewed and merged
- [ ] Phase 2 PR reviewed and merged
- [ ] Phase 3 PR reviewed and merged
- [ ] Phase 4 PR reviewed and merged
- [ ] Phase 5 PR reviewed and merged
- [ ] Vercel preview verified
- [ ] Production deployment from `main` verified
- [ ] Frontend API contract reviewed with backend owner
- [ ] No secrets committed
- [ ] Viva walkthrough and known limitations documented
