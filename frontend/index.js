/* Zuna Phase 1 — readable, backend-ready vanilla JavaScript */
'use strict';

// Configuration
const CONFIG = { apiBaseUrl: '', demoMode: true };

// Central demo data. These are illustrative products, not real inventory.
const PRODUCTS = [
  { id: 'gulnaar-studs', name: 'Gulnaar Studs', maker: 'Demo maker · Jaipur', price: 1450, image: './assets/images/jewellery.webp', offers: true, category: 'Jewellery' },
  { id: 'rekhta-lamp', name: 'Rekhta Table Lamp', maker: 'Demo maker · Saharanpur', price: 3200, image: './assets/images/lamp.webp', offers: true, category: 'Home & Living' },
  { id: 'neel-block-print', name: 'Neel Block Print', maker: 'Demo maker · Bagru', price: 1800, image: './assets/images/textile.webp', offers: false, category: 'Textiles' },
  { id: 'mitti-vessel', name: 'Mitti Quiet Vessel', maker: 'Demo maker · Kutch', price: 950, image: './assets/images/hero-craft.webp', offers: true, category: 'Art & Decor' }
];
const CATEGORIES = ['Jewellery', 'Home & Living', 'Textiles', 'Art & Decor', 'Gifts'];
const ROUTE_LABELS = { marketplace: 'Marketplace', product: 'Product detail', login: 'Login', register: 'Register', buyer: 'Buyer dashboard', seller: 'Seller dashboard', creator: 'Creator dashboard', collaborations: 'Collaboration marketplace', checkout: 'Checkout', 'order-confirmation': 'Order confirmation', story: 'Our story' };

// Safe rendering helpers
function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[character]));
}
function formatPrice(value) { return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(value); }
function productCard(product) {
  return `<article class="product-card reveal"><a href="#/product/${encodeURIComponent(product.id)}" aria-label="View ${escapeHtml(product.name)}"><div class="product-image-wrap"><img class="product-image" src="${escapeHtml(product.image)}" alt="${escapeHtml(product.name)} handmade craft sample" loading="lazy"><span class="product-badge">${product.offers ? 'Open to offers' : 'Sample edit'}</span></div><div class="product-info"><h3>${escapeHtml(product.name)}</h3><div class="product-meta"><span>${escapeHtml(product.maker)}</span><span class="product-price">${formatPrice(product.price)}</span></div></div></a></article>`;
}

// API adapter placeholder: future FastAPI calls should stay behind named functions.
async function apiRequest(path, options = {}) {
  if (CONFIG.demoMode || !CONFIG.apiBaseUrl) return { demo: true, data: null };
  const response = await fetch(`${CONFIG.apiBaseUrl}${path}`, { headers: { 'Content-Type': 'application/json', ...(options.headers || {}) }, ...options });
  if (!response.ok) throw new Error(`Request failed with status ${response.status}`);
  return response.json();
}
const api = { listProducts: () => Promise.resolve(PRODUCTS), getProduct: id => Promise.resolve(PRODUCTS.find(product => product.id === id) || null) };

// View templates
function renderHome() {
  return `<section class="hero"><div class="hero-copy reveal"><p class="eyebrow">The thoughtful marketplace</p><h1 class="display">A marketplace of stories, not just things.</h1><p>Discover handcrafted goods, make a thoughtful offer, and help independent makers grow — one considered purchase at a time.</p><div class="hero-actions"><a class="button button-dark" href="#/marketplace">Explore the marketplace <span aria-hidden="true">↗</span></a><a class="button" href="#/seller">Sell on Zuna</a></div><div class="hero-stamp">Made with patience · Chosen with intent</div></div><div class="hero-art reveal"><img class="hero-image" src="./assets/images/hero-craft.webp" alt="Art-directed still life of handmade Indian craft objects" fetchpriority="high"><div class="hero-note">Objects with a point of view<small>Editorial selection · 01</small></div></div></section><section class="category-band" aria-label="Illustrative craft categories"><div class="category-list">${CATEGORIES.map(category => `<a class="category-link" href="#/marketplace">${escapeHtml(category)}</a>`).join('')}</div></section><section class="section collection"><div class="section-inner"><div class="collection-heading reveal"><div><p class="eyebrow">A considered edit</p><h2 class="section-title">Small batches.<br>Long stories.</h2></div><a class="text-link" href="#/marketplace">View all pieces ↗</a></div><p class="section-copy reveal">A few illustrative pieces from our demo collection — chosen for their material honesty, quiet detail and the makers behind them.</p><div class="product-grid" style="margin-top:2.5rem">${PRODUCTS.map(productCard).join('')}</div></div></section><section class="section promise"><div class="section-inner promise-grid"><div class="reveal"><p class="eyebrow eyebrow-light">The Zuna promise</p><h2 class="section-title">Commerce, with a little more care.</h2></div><div class="reveal"><p class="promise-copy">We are building a marketplace that makes room for the nuance behind a price — and for the people who make, choose and share what belongs in your home.</p><div class="promise-points"><article class="promise-point"><span class="promise-number">01</span><h3>Price with confidence</h3><p>Clearer cost thinking for makers, without hiding the human judgement behind a number.</p></article><article class="promise-point"><span class="promise-number">02</span><h3>Negotiate with clarity</h3><p>Thoughtful offers and clear responses, rather than a discount carousel.</p></article><article class="promise-point"><span class="promise-number">03</span><h3>Grow through collaboration</h3><p>Connect makers and creators through links made for sharing.</p></article></div></div></div></section><section class="section spotlight"><div class="section-inner spotlight-grid"><div class="spotlight-image-wrap reveal"><img class="spotlight-image" src="./assets/images/artisan.webp" alt="Fictional demo maker shaping a terracotta vessel in a workshop" loading="lazy"></div><div class="spotlight-copy reveal"><p class="eyebrow">From the worktable</p><h2 class="section-title">Make room for the hands behind the object.</h2><blockquote>“A good object keeps a little of the time it took to make it.”</blockquote><p class="section-copy">This fictional demo maker profile is a glimpse of the stories Zuna hopes to help surface: material, process and a person making something with intention.</p></div></div></section><section class="section steps"><div class="section-inner"><p class="eyebrow reveal">A better way to make an offer</p><h2 class="section-title reveal">The pause between wanting<br>and owning.</h2><div class="steps-grid"><article class="step reveal"><div class="step-number"><span>01</span><span>→</span></div><h3>Make an offer</h3><p>Find a piece you love and suggest a price that feels considered.</p></article><article class="step reveal"><div class="step-number"><span>02</span><span>→</span></div><h3>Seller responds</h3><p>The maker can accept, decline or meet you somewhere in between.</p></article><article class="step reveal"><div class="step-number"><span>03</span><span>✦</span></div><h3>Checkout after agreement</h3><p>Only an accepted offer can move to the future checkout flow.</p></article></div></div></section><section class="section join"><div class="section-inner join-panel"><div class="join-card reveal"><p class="eyebrow eyebrow-light">For makers</p><h2>Bring your work<br>to the table.</h2><p>List thoughtfully, understand your costs and meet buyers with confidence.</p><a class="button button-light" href="#/seller">Explore the maker space ↗</a></div><div class="join-card reveal"><p class="eyebrow eyebrow-light">For creators</p><h2>Share what<br>stays with you.</h2><p>Discover collaborations and help good work travel further, without the noise.</p><a class="button button-light" href="#/creator">Discover collaborations ↗</a></div></div></section>`;
}
function renderPlaceholder(route, detail = '') {
  const label = ROUTE_LABELS[route] || 'This Zuna route';
  return `<section class="route-placeholder"><p class="eyebrow">${escapeHtml(label)}</p><h1 class="section-title">A thoughtful next step is taking shape.</h1><p>${detail ? escapeHtml(detail) : 'This screen is reserved for the next build phase. The navigation is live so the experience can be explored without broken links.'}</p><a class="button button-dark" href="#/">Return home ↗</a></section>`;
}
function renderMarketplace() {
  return `<section class="route-placeholder"><p class="eyebrow">Marketplace · demo preview</p><h1 class="section-title">Find something made to stay.</h1><p>Search, filters and product detail are coming in Phase 2. For now, browse the first illustrative collection from the homepage.</p><div class="product-grid" style="margin-top:2.5rem">${PRODUCTS.map(productCard).join('')}</div></section>`;
}

// Hash router
function getRoute() { return window.location.hash.replace(/^#\/?/, '').split('/').filter(Boolean); }
function renderRoute() {
  const [route, id] = getRoute();
  const app = document.querySelector('#app');
  if (!route) app.innerHTML = renderHome();
  else if (route === 'marketplace') app.innerHTML = renderMarketplace();
  else if (route === 'product') app.innerHTML = renderPlaceholder('product', id ? `Product detail for ${id} will be available in Phase 2.` : 'Choose a product from the marketplace to view its details.');
  else app.innerHTML = renderPlaceholder(route);
  window.scrollTo({ top: 0, behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
  document.querySelector('#app').focus({ preventScroll: true });
  closeMobileMenu();
  initialiseReveals();
}

// Shared interactions
function closeMobileMenu() { document.querySelector('.primary-navigation')?.classList.remove('is-open'); document.querySelector('.menu-toggle')?.setAttribute('aria-expanded', 'false'); document.body.classList.remove('menu-open'); }
function initialiseReveals() { const items = document.querySelectorAll('.reveal'); if (!('IntersectionObserver' in window)) { items.forEach(item => item.classList.add('is-visible')); return; } const observer = new IntersectionObserver(entries => entries.forEach(entry => { if (entry.isIntersecting) { entry.target.classList.add('is-visible'); observer.unobserve(entry.target); } }), { threshold: .12 }); items.forEach(item => observer.observe(item)); }
function initialiseMotion() { const bar = document.querySelector('#scroll-progress-bar'); let ticking = false; const update = () => { const total = document.documentElement.scrollHeight - window.innerHeight; bar.style.width = `${total > 0 ? (window.scrollY / total) * 100 : 0}%`; ticking = false; }; window.addEventListener('scroll', () => { if (!ticking) { window.requestAnimationFrame(update); ticking = true; } }, { passive: true }); update(); const art = document.querySelector('.hero-image'); if (!art || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return; window.addEventListener('scroll', () => { if (window.scrollY < window.innerHeight * 1.1) art.style.transform = `translateY(${Math.min(window.scrollY * .08, 22)}px)`; }, { passive: true }); }

document.addEventListener('click', event => { const toggle = event.target.closest('.menu-toggle'); if (toggle) { const nav = document.querySelector('.primary-navigation'); const open = nav.classList.toggle('is-open'); toggle.setAttribute('aria-expanded', String(open)); document.body.classList.toggle('menu-open', open); } if (event.target.closest('.primary-navigation a')) closeMobileMenu(); });
window.addEventListener('hashchange', renderRoute);
document.addEventListener('DOMContentLoaded', () => { renderRoute(); initialiseMotion(); });
