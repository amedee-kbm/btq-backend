from django.shortcuts import get_object_or_404
from ninja import Query
from ninja_extra import api_controller, http_get

from catalog.models import Collection
from catalog.queries import paginate, published_products, with_card_data
from catalog.schemas import CollectionDetail, CollectionOut, PageParams
from catalog.serializers import product_page


@api_controller("/collections", tags=["Catalog"])
class CollectionsController:
    @http_get("", response=list[CollectionOut])
    def list_collections(self, request):
        return Collection.objects.filter(is_active=True).values(
            "slug", "name", "description"
        )

    @http_get("/{slug}", response=CollectionDetail)
    def get_collection(self, request, slug: str, paging: Query[PageParams]):
        collection = get_object_or_404(Collection, slug=slug, is_active=True)
        qs = with_card_data(
            published_products()
            .filter(collectionproduct__collection=collection)
            .order_by("-in_stock", "collectionproduct__position", "id")
        )
        count, items = paginate(qs, paging.page, paging.page_size)
        return {
            "slug": collection.slug,
            "name": collection.name,
            "description": collection.description,
            **product_page(request, count, items, paging.page, paging.page_size),
        }
