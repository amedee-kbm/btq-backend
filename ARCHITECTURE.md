# Mucuruzi Digital — Backend Architecture

> Product scope and requirements: [`PRD.md`](./PRD.md). Frontend:
> [`btq-frontend-nextjs/ARCHITECTURE.md`](https://github.com/amedee-kbm/btq-frontend-nextjs/blob/main/ARCHITECTURE.md).
>
> **This file is the single source of truth for the HTTP API contract (§4).** The frontend's
> types and fixtures mirror it.

Legend: ✅ exists today · 🆕 to build for v1

## 1. Stack

| Concern | Choice |
|---|---|
| Language / runtime | Python ≥ 3.12, managed with **uv** |
| Framework | **Django 6** + **Django Ninja** / **ninja-extra** controllers |
| Auth | **django-ninja-jwt** (Bearer JWT) |
| DB | **Neon Postgres** in prod (`DATABASE_URL`), SQLite locally |
| Media | **Cloudflare R2** via django-storages (S3 API) in prod; `./media` locally |
| Static | WhiteNoise |
| Hosting | **Render** free web service, Frankfurt (`render.yaml`, `build.sh`) |
| Tooling | `justfile` recipes, **ruff** formatting, `.rest` files in `requests/` |
| Tests | **None in v1** (explicit decision) |

## 2. Layout

```
src/
  config/            settings, urls (admin/ + api/)                         ✅
  api/api.py         NinjaExtraAPI; registers controllers; docs at /api/docs ✅
  accounts/          custom User (UUID pk, email login, optional username)  ✅
    controllers/auth.py   /auth/* (ninja-jwt pair/refresh/verify + register) ✅
    controllers/me.py     /me                                              ✅
    controllers/favorites.py  /me/favorites                                 🆕
  catalog/
    models.py        Category, Tag, Size, Color, Product, Variant,
                     ProductImage, Collection, CollectionProduct, Favorite  ✅
    admin.py         full owner admin                                      ✅
    schemas.py       Ninja output schemas (§4)                              🆕
    queries.py       published-product queryset, annotations, filters (§4.2) 🆕
    serializers.py   prefetched models → §4 JSON dicts (no queries)          🆕
    controllers/products.py     /products, /products/{slug}                  🆕
    controllers/categories.py   /categories                                  🆕
    controllers/collections.py  /collections, /collections/{slug}            🆕
    controllers/lookups.py      /tags, /sizes, /colors                       🆕
    signals.py       revalidation triggers (§6)                             🆕
    revalidate.py    webhook client (§6)                                    🆕
  store/             🆕 app for SiteSettings singleton (+ admin)
    controllers/settings.py     /settings                                    🆕
```

## 3. Domain model

Existing (✅) — see `src/catalog/models.py`:

- **Category** — `name`, `slug` (unique), optional `parent` (max **two levels**, e.g.
  Dresses › Party), `cover_image`, `show_on_home`, `position`.
- **Tag** — occasion/style: `name`, `slug`.
- **Size** — managed list (`XS…XL`, `36`, `Free size`), ordered by `position`.
- **Color** — `name` (unique), optional `hex_code`.
- **Product** — `name`, `slug`, `code` (e.g. `BQ-0142`, unique, customer-quotable),
  `description`, `material`, `fit_note`, `price` / `sale_price` (whole RWF; DB constraint
  `sale_price < price`), M2M `categories`, M2M `tags`, `is_published`, timestamps.
  - *Sold out* = no variant with `is_available=True`.
  - *Effective price* = `sale_price` if set, else `price`.
- **Variant** — one `size` × one `color` of a product, `is_available` flag (no stock counts).
- **ProductImage** — `image`, optional `color` (null = shared/collage photo), `alt_text`,
  `position`.
- **Collection** — `name`, `slug`, `description`, `is_active`, `position`; products ordered via
  **CollectionProduct.position**.
- **Favorite** — (`user`, `product`) unique.
- **User** — UUID pk, `email` (login), optional `username` (shown as "preferred name").

New (🆕):

- **store.SiteSettings** — singleton (always `pk=1`; admin hides "add" once it exists and
  disallows delete; a `SiteSettings.load()` classmethod does `get_or_create(pk=1)`).

  | Field | Type | Notes |
  |---|---|---|
  | `whatsapp_number` | Char(20) | digits only, international, e.g. `250781427209` (used in `wa.me/…`) |
  | `whatsapp_template` | Text | order message; placeholders below |
  | `whatsapp_restock_template` | Text | message for sold-out items ("Ask if it's coming back") |
  | `phone` | Char(20) | display + `tel:` link |
  | `email` | Email, blank | |
  | `address` | Char(200) | e.g. "CHIC Building B30A, Kigali" |
  | `instagram_url`, `tiktok_url`, `x_url`, `facebook_url` | URL, blank | blank = hidden |
  | `updated_at` | auto | |

  Template placeholders: `{code}`, `{name}`, `{size}`, `{color}`, `{price}`, `{url}`. Defaults:
  - order: `Hi Mucuruzi Digital! I'd like {code} – {name}, size {size}, colour {color} ({price}). Is it available? {url}`
  - restock: `Hi Mucuruzi Digital! Is {code} – {name} coming back in size {size}, colour {color}? {url}`

  The **frontend** fills the placeholders. The backend only stores the text.

## 4. HTTP API contract

Base: `{DJANGO_BASE_URL}/api`. JSON. Errors use Ninja's default `{"detail": "…"}`.
Image URLs are **absolute** (R2 custom domain in prod; locally build with
`request.build_absolute_uri`). Money is an **integer number of RWF**.

### 4.1 Endpoint index

| Method | Path | Auth | Status |
|---|---|---|---|
| GET | `/health` | – | ✅ |
| POST | `/auth/pair` → `{email, access, refresh}` | – | ✅ |
| POST | `/auth/refresh` `{refresh}` → `{access, refresh}` | – | ✅ (rotation 🆕) |
| POST | `/auth/verify` `{token}` | – | ✅ |
| POST | `/auth/register` `{email, password, username?}` → `User` | – | ✅ |
| GET | `/me` → `User` | JWT | ✅ |
| GET | `/products` | – | 🆕 |
| GET | `/products/{slug}` | – | 🆕 |
| GET | `/categories` | – | 🆕 |
| GET | `/tags` | – | 🆕 |
| GET | `/sizes` | – | 🆕 |
| GET | `/colors` | – | 🆕 |
| GET | `/collections` | – | 🆕 |
| GET | `/collections/{slug}` | – | 🆕 |
| GET | `/settings` | – | 🆕 |
| GET | `/me/favorites` | JWT | 🆕 |
| PUT | `/me/favorites/{slug}` | JWT | 🆕 |
| DELETE | `/me/favorites/{slug}` | JWT | 🆕 |

`/sizes` and `/colors` are tiny lookup lists the frontend needs to render the size and color
filters. They were not in the original endpoint list; they were added while writing this doc.

**Public visibility rule (every public endpoint):** only `Product.is_published=True`; only
`Collection.is_active=True`.

### 4.2 `GET /products`

Query parameters (all optional, all combinable; **AND across parameters**):

| Param | Semantics |
|---|---|
| `category` | category slug; **includes its subcategories** (`categories__slug=s OR categories__parent__slug=s`) |
| `tag` (repeatable) | tag slugs; **OR** among values (`tags__slug__in=[…]`) |
| `size` (repeatable) | size names, case-insensitive; matches products with an **available** variant in any of these sizes |
| `color` (repeatable) | color names, case-insensitive; matches an **available** variant in any of these colors |
| | if both `size` and `color` are given, the **same available variant** must match both |
| `min_price`, `max_price` | integers, on **effective price** |
| `on_sale` | `true` → `sale_price IS NOT NULL` |
| `in_stock` | `true` → has an available variant (default off; sold-out items are shown) |
| `q` | `icontains` over `name`, `code`, `material`, `tags__name`, `categories__name` |
| `sort` | `newest` (default, `-created_at`), `price_asc`, `price_desc` (effective price) |
| `page` | 1-based, default 1 |
| `page_size` | default **24**, max **48** |

**Ordering:** always `in_stock DESC` first (**sold-out last**), then the chosen sort, then `id`
as a tiebreaker.

Implementation sketch (`catalog/queries.py`):

```python
available = Variant.objects.filter(product=OuterRef("pk"), is_available=True)
qs = (Product.objects.filter(is_published=True)
      .annotate(effective_price=Coalesce("sale_price", "price"),
                in_stock=Exists(available))
      # filters…, then .distinct() when joining M2M (category/tag/q)
      .order_by("-in_stock", <sort>, "id")
      .prefetch_related(images_for_card, variants_with_size_color))
```

Response:

```json
{
  "count": 86,
  "page": 1,
  "page_size": 24,
  "items": [ProductListItem]
}
```

`ProductListItem`:

```json
{
  "slug": "emerald-satin-maxi",
  "code": "BQ-0142",
  "name": "Emerald Satin Maxi",
  "price": 25000,
  "sale_price": 19000,
  "effective_price": 19000,
  "is_on_sale": true,
  "is_sold_out": false,
  "images": [
    {"url": "https://…/products/a.webp", "alt": "Emerald satin maxi, front", "color": "Emerald"},
    {"url": "https://…/products/b.webp", "alt": "Back view", "color": null}
  ],
  "colors": [
    {"name": "Emerald", "hex": "#0F6B4F", "is_available": true},
    {"name": "Black", "hex": "#000000", "is_available": false}
  ]
}
```

- `images`: the **first two** by `position` (the 2nd one is shown on hover).
- `colors`: distinct colors across the product's variants; `is_available` = any available
  variant in that color. `hex` may be `null`.

### 4.3 `GET /products/{slug}`

404 if missing or unpublished. Sold-out products return normally.

`ProductDetail` = `ProductListItem` fields, with `images` containing **all** images, plus:

```json
{
  "description": "Floor-length satin…",
  "material": "Satin (polyester)",
  "fit_note": "Runs small",
  "categories": [{"slug": "party-dresses", "name": "Party", "parent": {"slug": "dresses", "name": "Dresses"}}],
  "tags": [{"slug": "wedding-guest", "name": "Wedding guest"}],
  "sizes": ["S", "M", "L"],
  "variants": [
    {"size": "S", "color": "Emerald", "is_available": true},
    {"size": "M", "color": "Emerald", "is_available": false}
  ]
}
```

- `sizes`: distinct sizes of this product's variants, in `Size.position` order.
- A size×color pair with **no variant row** does not exist; the frontend greys it out.

### 4.4 `GET /categories`

Two-level tree, ordered by `position, name`. `product_count` counts **published** products
(including those in its children for a parent).

```json
[
  {
    "slug": "dresses", "name": "Dresses",
    "cover_image": "https://…/categories/dresses.webp",
    "show_on_home": true, "position": 0, "product_count": 54,
    "children": [
      {"slug": "party-dresses", "name": "Party", "cover_image": null,
       "show_on_home": false, "position": 0, "product_count": 18, "children": []}
    ]
  }
]
```

### 4.5 `GET /tags`, `GET /sizes`, `GET /colors`

Only values used by at least one **published** product (tags), or by at least one **available
variant of a published product** (sizes, colors).

```json
[{"slug": "wedding-guest", "name": "Wedding guest", "product_count": 12}]
["XS", "S", "M", "L", "XL", "Free size"]
[{"name": "Emerald", "hex": "#0F6B4F"}]
```

### 4.6 `GET /collections`, `GET /collections/{slug}`

List (active only, ordered by `position, name`):

```json
[{"slug": "new-arrivals", "name": "New Arrivals", "description": "Fresh this week"}]
```

Detail: 404 if missing or inactive. Accepts `page` / `page_size` like `/products`. Items are
ordered **sold-out last, then `CollectionProduct.position`**.

```json
{
  "slug": "new-arrivals", "name": "New Arrivals", "description": "Fresh this week",
  "count": 14, "page": 1, "page_size": 24,
  "items": [ProductListItem]
}
```

### 4.7 `GET /settings`

```json
{
  "whatsapp_number": "250781427209",
  "whatsapp_template": "Hi Mucuruzi Digital! I'd like {code} – {name}, size {size}, colour {color} ({price}). Is it available? {url}",
  "whatsapp_restock_template": "Hi Mucuruzi Digital! Is {code} – {name} coming back in size {size}, colour {color}? {url}",
  "phone": "+250781427209",
  "email": "",
  "address": "CHIC Building B30A, Kigali",
  "socials": {"instagram": "https://instagram.com/btq.", "tiktok": "https://www.tiktok.com/@btq.", "x": "", "facebook": ""}
}
```

### 4.8 Favorites (JWT)

- `GET /me/favorites` → `[ProductListItem]`, newest favorite first, **published products
  only**, not paginated (small lists).
- `PUT /me/favorites/{slug}` → `204`. Idempotent (`get_or_create`). `404` if the product is
  missing or unpublished.
- `DELETE /me/favorites/{slug}` → `204`, also when it wasn't a favorite.
- Missing or expired token → `401`.

## 5. Auth

- ninja-jwt with `USERNAME_FIELD = "email"`. Register validates with Django's password
  validators; duplicate email → `409`.
- 🆕 `settings.py`:

  ```python
  NINJA_JWT = {
      "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
      "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
      "ROTATE_REFRESH_TOKENS": True,
  }
  ```

  Rotation means every refresh returns a new refresh token, so the session **slides**: active
  within 30 days means you stay logged in. There's no blacklist app in v1 (logout = the
  frontend deletes its cookies).
- The browser never talks to Django for auth; the Next.js BFF holds the tokens in httpOnly
  cookies (see the frontend ARCHITECTURE).
- No password reset in v1. It needs a sending domain, which Mucuruzi Digital doesn't have yet.

## 6. Frontend revalidation webhook 🆕

The frontend caches catalog pages (ISR). When the owner saves in admin, the backend tells
Vercel to drop those caches.

- **Triggers** (`catalog/signals.py`, `store/signals.py`): `post_save` / `post_delete` on
  Product, Variant, ProductImage, Category, Tag, Size, Color, Collection, CollectionProduct,
  SiteSettings; `m2m_changed` on `Product.categories` and `Product.tags`.
- **Batching:** handlers add cache tags to a per-transaction set and register **one**
  `transaction.on_commit` callback. A product save with inlines then sends **one** request.
- **Tags:** coarse on purpose, since the catalog is small:
  - `catalog`: any catalog model change (all product, category, tag and collection pages).
  - `settings`: SiteSettings change.
- **Request:** `POST {FRONTEND_REVALIDATE_URL}` with header
  `Authorization: Bearer {REVALIDATE_SECRET}`, body `{"tags": ["catalog"]}`.
- **Fire-and-forget:** sent from a daemon thread with a **3 s timeout**. Errors are logged,
  never raised, so an admin save never fails or hangs because of Vercel.
- **Disabled** when `FRONTEND_REVALIDATE_URL` is unset (local dev).
- **Safety net:** the frontend also revalidates on a 1-hour timer.

## 7. Configuration

| Env var | Purpose | Status |
|---|---|---|
| `DEBUG`, `SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` | Django basics | ✅ |
| `DATABASE_URL` | Neon Postgres (unset → SQLite) | ✅ |
| `CORS_ALLOWED_ORIGINS` | browser CORS; the frontend calls Django server-side, so mainly for local tools | ✅ |
| `R2_ACCOUNT_ID`, `R2_BUCKET_NAME`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_PUBLIC_DOMAIN` | media storage | ✅ |
| `FRONTEND_REVALIDATE_URL` | e.g. `https://btq-frontend-nextjs.vercel.app/api/revalidate` | 🆕 |
| `REVALIDATE_SECRET` | shared with Vercel's `REVALIDATE_SECRET` | 🆕 |

Add the new vars to `.env.example` and `render.yaml` (`sync: false`).

## 8. Deployment & operations

- Render builds with `build.sh` (install, `collectstatic`, `migrate`) and runs gunicorn (2 workers).
- **Cold starts:** the free plan sleeps after inactivity, and the first request can take 30 s+.
  Shoppers are shielded by frontend ISR. Webhooks sent while the backend is cold still fire
  (it's the backend that's awake when the owner saves). Auth and favorites calls may hit a cold
  backend; the frontend shows a loading state.
- Images are uploaded as-is to R2 (owner pre-processes; PRD §3.4). The frontend serves them
  through `next/image` with the R2 domain in `remotePatterns`.
- Verification: `/api/docs` (Redoc) and the `.rest` files in `requests/` (add ones for each new
  endpoint).

## 9. Build order

1. `NINJA_JWT` lifetimes and rotation.
2. `catalog/schemas.py` + `queries.py` + `/products`, `/products/{slug}`.
3. `/categories`, `/tags`, `/sizes`, `/colors`, `/collections[/{slug}]`.
4. `store` app: `SiteSettings` model, singleton admin, data migration seeding current contact
   details, `/settings`.
5. `/me/favorites` endpoints.
6. Revalidation signals and webhook; new env vars in `.env.example` and `render.yaml`.
7. `.rest` request files for every new endpoint; deploy.
