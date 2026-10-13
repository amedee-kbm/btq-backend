"""Turn prefetched models into the §4 JSON shapes. Expects querysets built
with queries.with_card_data / with_detail_data, so nothing here queries."""


def absolute_url(request, file):
    # R2 URLs are already absolute; build_absolute_uri leaves them unchanged.
    return request.build_absolute_uri(file.url) if file else None


def product_card(request, product):
    colors = {}
    for variant in product.all_variants:
        entry = colors.setdefault(
            variant.color.name,
            {
                "name": variant.color.name,
                "hex": variant.color.hex_code or None,
                "is_available": False,
            },
        )
        entry["is_available"] |= variant.is_available

    return {
        "slug": product.slug,
        "code": product.code,
        "name": product.name,
        "price": product.price,
        "sale_price": product.sale_price,
        "effective_price": product.effective_price,
        "is_on_sale": product.sale_price is not None,
        "is_sold_out": not product.in_stock,
        "images": [
            {
                "url": absolute_url(request, image.image),
                "alt": image.alt_text,
                "color": image.color.name if image.color else None,
            }
            for image in product.shown_images
        ],
        "colors": sorted(colors.values(), key=lambda c: c["name"]),
    }


def product_detail(request, product):
    sizes = []
    for variant in product.all_variants:  # already in Size.position order
        if variant.size.name not in sizes:
            sizes.append(variant.size.name)

    return {
        **product_card(request, product),
        "description": product.description,
        "material": product.material,
        "fit_note": product.fit_note,
        "categories": [
            {
                "slug": category.slug,
                "name": category.name,
                "parent": (
                    {"slug": category.parent.slug, "name": category.parent.name}
                    if category.parent
                    else None
                ),
            }
            for category in product.categories.all()
        ],
        "tags": [{"slug": tag.slug, "name": tag.name} for tag in product.tags.all()],
        "sizes": sizes,
        "variants": [
            {
                "size": variant.size.name,
                "color": variant.color.name,
                "is_available": variant.is_available,
            }
            for variant in product.all_variants
        ],
    }


def product_page(request, count, items, page, page_size):
    return {
        "count": count,
        "page": page,
        "page_size": page_size,
        "items": [product_card(request, p) for p in items],
    }
