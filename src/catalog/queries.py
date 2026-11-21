"""Published-product querysets and the /products filters (ARCHITECTURE.md §4.2)."""

from django.db.models import Exists, F, OuterRef, Prefetch, Q
from django.db.models.functions import Coalesce

from .models import Category, Product, ProductImage, Variant
from .schemas import ProductFilters

SORTS = {
    "newest": "-created_at",
    # Unpriced products go last either way.
    "price_asc": F("effective_price").asc(nulls_last=True),
    "price_desc": F("effective_price").desc(nulls_last=True),
}


def published_products():
    """Every public product query starts here: published only, with the
    `effective_price` and `in_stock` annotations the filters and sorts use."""
    return Product.objects.filter(is_published=True).annotate(
        effective_price=Coalesce("sale_price", "price"),
        in_stock=in_stock(),
    )


def in_stock():
    """Has an available variant, or has no variants at all (stock not tracked)."""
    variants = Variant.objects.filter(product=OuterRef("pk"))
    return Exists(variants.filter(is_available=True)) | ~Exists(variants)


def with_card_data(qs, all_images=False):
    """Prefetch what a ProductListItem needs: the first two images (or all of
    them for the detail page) and the variants' colors."""
    images = ProductImage.objects.select_related("color")
    if not all_images:
        images = images[:2]
    return qs.prefetch_related(
        Prefetch("images", queryset=images, to_attr="shown_images"),
        Prefetch(
            "variants",
            queryset=Variant.objects.select_related("size", "color"),
            to_attr="all_variants",
        ),
    )


def with_detail_data(qs):
    return with_card_data(qs, all_images=True).prefetch_related(
        Prefetch("categories", queryset=Category.objects.select_related("parent")),
        "tags",
    )


def _any_iexact(field, values):
    q = Q()
    for value in values:
        q |= Q(**{f"{field}__iexact": value})
    return q


def filter_products(qs, f: ProductFilters):
    # M2M filters go through `pk__in` subqueries so rows never duplicate.
    if f.category:
        in_category = Product.objects.filter(
            Q(categories__slug=f.category) | Q(categories__parent__slug=f.category)
        )
        qs = qs.filter(pk__in=in_category.values("pk"))

    if f.tag:
        qs = qs.filter(pk__in=Product.objects.filter(tags__slug__in=f.tag).values("pk"))

    if f.size or f.color:
        # Size and color must match the same available variant.
        variants = Variant.objects.filter(product=OuterRef("pk"), is_available=True)
        if f.size:
            variants = variants.filter(_any_iexact("size__name", f.size))
        if f.color:
            variants = variants.filter(_any_iexact("color__name", f.color))
        qs = qs.filter(Exists(variants))

    if f.min_price is not None:
        qs = qs.filter(effective_price__gte=f.min_price)
    if f.max_price is not None:
        qs = qs.filter(effective_price__lte=f.max_price)
    if f.on_sale:
        qs = qs.filter(sale_price__isnull=False)
    if f.in_stock:
        qs = qs.filter(in_stock=True)

    if f.q and f.q.strip():
        term = f.q.strip()
        matches = Product.objects.filter(
            Q(name__icontains=term)
            | Q(code__icontains=term)
            | Q(material__icontains=term)
            | Q(tags__name__icontains=term)
            | Q(categories__name__icontains=term)
        )
        qs = qs.filter(pk__in=matches.values("pk"))

    # Sold-out products always sort last.
    return qs.order_by("-in_stock", SORTS[f.sort], "id")


def paginate(qs, page, page_size):
    start = (page - 1) * page_size
    return qs.count(), list(qs[start : start + page_size])
