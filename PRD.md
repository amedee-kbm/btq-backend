# Mucuruzi Digital — Product Requirements (Backend)

> Companion docs: [`ARCHITECTURE.md`](./ARCHITECTURE.md) (this repo) and the frontend's
> [`PRD.md`](https://github.com/amedee-kbm/btq-frontend-nextjs/blob/main/PRD.md) /
> [`ARCHITECTURE.md`](https://github.com/amedee-kbm/btq-frontend-nextjs/blob/main/ARCHITECTURE.md).

## 1. Product overview (shared with the frontend PRD)

Mucuruzi Digital is a single fashion boutique in Kigali, Rwanda, selling women's clothing: dresses,
matching sets ("completes"), jeans, shorts, boubous and more. Most customers arrive
organically from TikTok videos.

Until now, shoppers screenshotted items they liked, sent them to the seller on WhatsApp, and
asked for more pictures. The Mucuruzi Digital website replaces that back-and-forth:

- Customers **browse the whole catalog themselves**, filtering by **category** (party, casual,
  maxi dresses…), by **occasion/style tags** (wedding guest, church…), and by **hand-picked
  collections** (New Arrivals, Promos).
- Each item shows its **photos**, a **price in RWF** (with a crossed-out price on promo), its
  **material**, a **fit note**, and **which sizes and colors are available or sold out**.
- When a customer wants something, **one tap opens WhatsApp** with a message already naming
  the exact item (code + name), size and color. The sale is finished in conversation with the
  seller: payment by **MoMo or cash**, delivery by **motard** or **pickup at CHIC Building B30A**.
- Shoppers can create an account **only to save favorites**.
- The owner manages products, photos, categories, collections and contact details **in Django
  admin**, without a developer.

### Scope decisions (v1)

| In v1 | Deferred / out |
|---|---|
| Catalog browse, filter, search, sort | Cart, online payments, orders, order tracking |
| Product detail with variant availability | Password reset (until Mucuruzi Digital owns a domain for email) |
| WhatsApp handoff (pre-filled message) | Guest (logged-out) favorites |
| Favorites (login required) | Analytics / WhatsApp-tap lead tracking |
| Owner-editable contact details & WhatsApp template | Kinyarwanda / multilingual content |
| Instant site refresh when the owner saves in admin | Server-side image processing |
| | Automated tests and CI |

The site is **English only**.

## 2. Users

| User | Needs |
|---|---|
| **Shopper** (mostly mobile, arriving from TikTok) | Find the item from the video fast (by browsing or by its code), see real photos, know if their size/color is available, message the seller in one tap. |
| **Registered shopper** | Save favorites and find them again on any device, staying logged in for weeks. |
| **Owner** (non-technical, one person) | Add/edit products, photos, availability, collections and contact details in admin; see changes on the site within seconds. |

## 3. What the backend must provide

### 3.1 Catalog (public, read-only)

- **R1 — Product list** with filters, search, sort and pagination (see
  ARCHITECTURE §4.2 for exact semantics):
  - Category (includes its subcategories), occasion/style tags (any of), size and color
    (only *available* variants match), price range (on the effective price), on-sale, in-stock.
  - Free-text search across name, product code, material, tag and category names, so a code
    like `BQ-0142` quoted in a TikTok caption finds the item.
  - Sort by newest (default), price low→high, price high→low. **Sold-out products always sort
    last** but remain visible.
  - Paginated, with a total count.
- **R2 — Product detail** by slug: all photos (each optionally tied to a color), every
  size×color variant with availability, description, material, fit note, categories, tags.
  Sold-out products remain reachable.
- **R3 — Categories** as a two-level tree with cover images and a "show on home" flag, in the
  owner's order.
- **R4 — Tags** that have at least one published product.
- **R5 — Collections**: list of active collections in the owner's order; a single collection
  with its products in the owner's manual order.
- **R6 — Site settings**: WhatsApp number, WhatsApp message template, phone, email, store
  address, social links. One record, edited in admin.
- **Visibility rule:** unpublished products never appear anywhere in the public API. Inactive
  collections never appear.

### 3.2 Accounts & favorites

- **R7 — Register / log in** with email + password; optional preferred name (exists today).
- **R8 — Sessions last 30 days, sliding**: a shopper who visits at least once every 30 days
  stays logged in.
- **R9 — Favorites**: a logged-in shopper can list, add and remove favorite products. Adding is
  idempotent. Unpublished products drop out of the list.
- No password reset in v1. Locked-out shoppers can register again with another email.

### 3.3 Owner workflow (Django admin)

- **R10** — Everything listed in §1 is editable in admin. Already in place: products (with
  variant and image inlines, publish/unpublish actions, on-sale and sold-out filters),
  categories, collections (with ordered products), tags, sizes, colors; favorites read-only.
- **R11** — Site settings editable as a single record (no "add another").
- **R12 — Instant refresh:** saving or deleting a product, variant, image, category, tag,
  collection or site settings makes the public site reflect the change **within seconds**
  (the backend notifies the frontend; see ARCHITECTURE §6). If the notification fails, the site
  catches up within one hour.

### 3.4 Photo preparation guideline (owner)

Photos are uploaded **as-is**; the backend does no resizing. Before uploading:

- Long edge about **1600 px**, portrait **2:3** framing preferred (the product grid uses 2:3).
- **WebP or JPEG**, ideally **under 400 KB**.
- **Remove location (GPS) metadata** from phone photos.
- Fill in **alt text** (e.g. "Emerald satin maxi dress, front view").
- If a photo shows one specific color, set its **color** so the site can switch photos when a
  shopper picks that color. Leave it blank for shared photos.

## 4. Non-functional requirements

- **Hosting:** Render free plan (Frankfurt), Neon Postgres, Cloudflare R2 for media. The service
  sleeps when idle; the frontend's caching must make that invisible to shoppers.
- **Performance:** list endpoints answer in a bounded number of queries (no N+1); page size
  max 48.
- **Security:** catalog endpoints are read-only and public; favorites require a valid JWT; the
  revalidation webhook carries a shared secret; no customer data beyond email and optional name.
- **No automated tests** in v1 (explicit decision). Verify by hand with the `.rest` files in
  `requests/` and the API docs at `/api/docs`.

## 5. Done when

- [ ] All endpoints in ARCHITECTURE §4 exist and match the documented JSON shapes.
- [ ] `SiteSettings` model + admin exist and are seeded with the current contact details.
- [ ] JWT lifetimes set to 15 min / 30 days with rotation.
- [ ] Admin saves trigger frontend revalidation in production.
- [ ] Deployed on Render with the new env vars set.
