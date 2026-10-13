from django.db.models.signals import m2m_changed, post_delete, post_save

from . import revalidate
from .models import (
    Category,
    Collection,
    CollectionProduct,
    Color,
    Product,
    ProductImage,
    Size,
    Tag,
    Variant,
)

CATALOG_MODELS = [
    Product,
    Variant,
    ProductImage,
    Category,
    Tag,
    Size,
    Color,
    Collection,
    CollectionProduct,
]


def catalog_changed(sender, **kwargs):
    revalidate.schedule("catalog")


for model in CATALOG_MODELS:
    post_save.connect(catalog_changed, sender=model)
    post_delete.connect(catalog_changed, sender=model)

for through in [Product.categories.through, Product.tags.through]:
    m2m_changed.connect(catalog_changed, sender=through)
