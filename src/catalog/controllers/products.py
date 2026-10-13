from django.shortcuts import get_object_or_404
from ninja import Query
from ninja_extra import api_controller, http_get

from catalog.queries import (
    filter_products,
    paginate,
    published_products,
    with_card_data,
    with_detail_data,
)
from catalog.schemas import ProductDetail, ProductFilters, ProductPage
from catalog.serializers import product_detail, product_page


@api_controller("/products", tags=["Catalog"])
class ProductsController:
    @http_get("", response=ProductPage)
    def list_products(self, request, filters: Query[ProductFilters]):
        qs = with_card_data(filter_products(published_products(), filters))
        count, items = paginate(qs, filters.page, filters.page_size)
        return product_page(request, count, items, filters.page, filters.page_size)

    @http_get("/{slug}", response=ProductDetail)
    def get_product(self, request, slug: str):
        product = get_object_or_404(with_detail_data(published_products()), slug=slug)
        return product_detail(request, product)
