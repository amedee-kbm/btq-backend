from django.db.models import Count, Q
from ninja_extra import api_controller, http_get

from catalog.models import Color, Size, Tag
from catalog.schemas import ColorOut, TagOut

# Sizes and colors only count when a published product has them available.
# Both conditions sit in one filter() so they apply to the same variant.
IN_AVAILABLE_VARIANT = Q(variants__is_available=True) & Q(
    variants__product__is_published=True
)


@api_controller("", tags=["Catalog"])
class LookupsController:
    @http_get("/tags", response=list[TagOut])
    def list_tags(self, request):
        return (
            Tag.objects.annotate(
                product_count=Count(
                    "products", filter=Q(products__is_published=True), distinct=True
                )
            )
            .filter(product_count__gt=0)
            .values("slug", "name", "product_count")
        )

    @http_get("/sizes", response=list[str])
    def list_sizes(self, request):
        return list(
            Size.objects.filter(IN_AVAILABLE_VARIANT)
            .distinct()
            .values_list("name", flat=True)
        )

    @http_get("/colors", response=list[ColorOut])
    def list_colors(self, request):
        colors = Color.objects.filter(IN_AVAILABLE_VARIANT).distinct()
        return [{"name": c.name, "hex": c.hex_code or None} for c in colors]
