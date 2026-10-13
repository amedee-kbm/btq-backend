"""Public API output shapes. ARCHITECTURE.md §4 is the contract these mirror."""

from typing import Literal, Optional

from ninja import Field, Schema


class ImageOut(Schema):
    url: str
    alt: str
    color: Optional[str]


class ProductColorOut(Schema):
    name: str
    hex: Optional[str]
    is_available: bool


class ProductListItem(Schema):
    slug: str
    code: str
    name: str
    price: int
    sale_price: Optional[int]
    effective_price: int
    is_on_sale: bool
    is_sold_out: bool
    images: list[ImageOut]
    colors: list[ProductColorOut]


class CategoryRef(Schema):
    slug: str
    name: str


class ProductCategoryOut(CategoryRef):
    parent: Optional[CategoryRef]


class TagRef(Schema):
    slug: str
    name: str


class VariantOut(Schema):
    size: str
    color: str
    is_available: bool


class ProductDetail(ProductListItem):
    description: str
    material: str
    fit_note: str
    categories: list[ProductCategoryOut]
    tags: list[TagRef]
    sizes: list[str]
    variants: list[VariantOut]


class ProductPage(Schema):
    count: int
    page: int
    page_size: int
    items: list[ProductListItem]


class CategoryOut(Schema):
    slug: str
    name: str
    cover_image: Optional[str]
    show_on_home: bool
    position: int
    product_count: int
    children: list["CategoryOut"]


class TagOut(TagRef):
    product_count: int


class ColorOut(Schema):
    name: str
    hex: Optional[str]


class CollectionOut(Schema):
    slug: str
    name: str
    description: str


class CollectionDetail(CollectionOut, ProductPage):
    pass


# --- Query parameters ------------------------------------------------------


class PageParams(Schema):
    page: int = Field(1, ge=1)
    page_size: int = Field(24, ge=1, le=48)


class ProductFilters(PageParams):
    category: Optional[str] = None
    tag: list[str] = []
    size: list[str] = []
    color: list[str] = []
    min_price: Optional[int] = None
    max_price: Optional[int] = None
    on_sale: bool = False
    in_stock: bool = False
    q: Optional[str] = None
    sort: Literal["newest", "price_asc", "price_desc"] = "newest"
