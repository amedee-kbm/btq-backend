from django.db.models import OuterRef, Subquery
from django.shortcuts import get_object_or_404
from ninja_extra import api_controller, http_delete, http_get, http_put
from ninja_jwt.authentication import JWTAuth

from catalog.models import Favorite
from catalog.queries import published_products, with_card_data
from catalog.schemas import ProductListItem
from catalog.serializers import product_card


@api_controller("/me/favorites", auth=JWTAuth(), tags=["Me"])
class FavoritesController:
    @http_get("", response=list[ProductListItem])
    def list_favorites(self, request):
        favorites = Favorite.objects.filter(user=request.user)
        products = with_card_data(
            published_products()
            .annotate(
                favorited_at=Subquery(
                    favorites.filter(product=OuterRef("pk")).values("created_at")
                )
            )
            .filter(favorited_at__isnull=False)
            .order_by("-favorited_at", "id")
        )
        return [product_card(request, p) for p in products]

    @http_put("/{slug}", response={204: None})
    def add_favorite(self, request, slug: str):
        product = get_object_or_404(published_products(), slug=slug)
        Favorite.objects.get_or_create(user=request.user, product=product)
        return 204, None

    @http_delete("/{slug}", response={204: None})
    def remove_favorite(self, request, slug: str):
        Favorite.objects.filter(user=request.user, product__slug=slug).delete()
        return 204, None
