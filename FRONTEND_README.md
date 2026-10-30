# LUXÉ / Fashion Store — Reference Design Frontend

This is a complete replacement React frontend designed around the supplied references: warm ivory and beige palette, luxury editorial photography, an all-products catalogue, a two-column product detail page, and a mobile-first home/bag experience.

## Install

From the root project folder:

```powershell
cd frontend
npm install
npm run dev
```

## Django API

The frontend requests products from `http://127.0.0.1:8000/api/products/`. Keep the Django backend running on port 8000. If the API is unavailable, the UI falls back to the included sample catalogue.

## Important status

The product catalogue is wired to the existing Django products endpoint. Cart, wishlist and demo orders are stored in browser localStorage. Checkout is a front-end demonstration and does not yet charge payments or create server-side orders. Auth is also a front-end demo and is not secure Django authentication yet; these are later backend milestones.

## Files

- `src/App.jsx` — complete storefront, product detail, bag, wishlist, account, order history and order tracking UI.
- `src/main.jsx` — React entry point.
- `src/styles.css` — responsive styling for desktop and mobile.
- `index.html` — document title, viewport and font loading.
