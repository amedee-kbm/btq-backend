from ninja_extra import api_controller, http_get

from catalog.models import Category
from catalog.schemas import CategoryOut
from catalog.serializers import absolute_url


@api_controller("/categories", tags=["Catalog"])
class CategoriesController:
    @http_get("", response=list[CategoryOut])
    def list_categories(self, request):
        categories = list(Category.objects.all())  # ordered by position, name

        # Published product ids per category, so a parent can count the
        # union of its own and its children's products without double counting.
        product_ids = {c.pk: set() for c in categories}
        links = Category.products.through.objects.filter(
            product__is_published=True
        ).values_list("category_id", "product_id")
        for category_id, product_id in links:
            product_ids[category_id].add(product_id)

        def node(category, children):
            ids = set(product_ids[category.pk])
            for child in children:
                ids |= product_ids[child.pk]
            return {
                "slug": category.slug,
                "name": category.name,
                "cover_image": absolute_url(request, category.cover_image),
                "show_on_home": category.show_on_home,
                "position": category.position,
                "product_count": len(ids),
                "children": [node(child, []) for child in children],
            }

        children = {}
        for c in categories:
            if c.parent_id:
                children.setdefault(c.parent_id, []).append(c)
        return [
            node(c, children.get(c.pk, [])) for c in categories if c.parent_id is None
        ]
