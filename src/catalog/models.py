import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import F, Q
from django.utils.text import slugify

CODE_PREFIX = "MD"


class Category(models.Model):
    """What the item is. Nestable: Dresses > Party, Casual, Maxi."""

    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
    )
    cover_image = models.ImageField(upload_to="categories/", blank=True)
    show_on_home = models.BooleanField(default=False)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return f"{self.parent} > {self.name}" if self.parent else self.name

    def clean(self):
        # Max two levels (Dresses > Party). Also rules out cycles.
        if self.parent_id is None:
            return
        if self.pk is not None and self.parent_id == self.pk:
            raise ValidationError({"parent": "A category can't be its own parent."})
        if self.parent.parent_id is not None:
            raise ValidationError(
                {"parent": "Categories can only be nested two levels deep."}
            )
        if self.pk is not None and self.children.exists():
            raise ValidationError(
                {
                    "parent": "This category has subcategories, so it must stay top-level."
                }
            )


class Tag(models.Model):
    """What it's for or what it's like: 'wedding guest', 'church', 'linen'."""

    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Size(models.Model):
    """Managed list: XS, S, M, L, XL, 36, 38, Free size..."""

    name = models.CharField(max_length=20, unique=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "name"]

    def __str__(self):
        return self.name


class Color(models.Model):
    name = models.CharField(max_length=50, unique=True)
    hex_code = models.CharField(
        max_length=7,
        blank=True,
        validators=[RegexValidator(r"^#[0-9A-Fa-f]{6}$", "Use a format like #A1B2C3.")],
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Product(models.Model):
    """Only a photo and a category are required; everything else is optional.

    code and slug fill themselves in on save when left blank.
    """

    name = models.CharField(max_length=200, blank=True)
    slug = models.SlugField(unique=True, blank=True)
    code = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        help_text="Short code customers can quote, e.g. MD-0142. Leave blank to auto-generate.",
    )
    description = models.TextField(blank=True)
    material = models.CharField(max_length=150, blank=True)
    fit_note = models.CharField(
        max_length=200, blank=True, help_text="e.g. 'Runs small', 'Stretchy'"
    )

    # Whole RWF, no decimals.
    price = models.PositiveIntegerField(null=True, blank=True)
    sale_price = models.PositiveIntegerField(null=True, blank=True)

    categories = models.ManyToManyField(Category, related_name="products")
    tags = models.ManyToManyField(Tag, related_name="products", blank=True)

    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(sale_price__isnull=True)
                | Q(price__isnull=False, sale_price__lt=F("price")),
                name="product_sale_price_lt_price",
            )
        ]

    def __str__(self):
        return f"{self.code} - {self.name}" if self.name else self.code

    def save(self, *args, **kwargs):
        if not self.code:
            # The code is built from the pk, so insert under a placeholder first.
            slug = self.slug
            self.code = f"tmp-{uuid.uuid4().hex[:12]}"
            self.slug = slug or self.code
            super().save(*args, **kwargs)
            self.code = f"{CODE_PREFIX}-{self.pk:04d}"
            self.slug = slug
            kwargs = {"update_fields": ["code", "slug"]}
        if not self.slug:
            base = f"{slugify(self.name)}-" if self.name else ""
            self.slug = f"{base}{self.code}".lower()
        super().save(*args, **kwargs)

    @property
    def is_on_sale(self):
        return self.sale_price is not None

    @property
    def is_sold_out(self):
        # No variants at all = not tracked, so not sold out.
        return (
            self.variants.exists()
            and not self.variants.filter(is_available=True).exists()
        )


class Variant(models.Model):
    """One size + one color of a product. Availability is a flag, not a count."""

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="variants"
    )
    size = models.ForeignKey(Size, on_delete=models.PROTECT, related_name="variants")
    color = models.ForeignKey(Color, on_delete=models.PROTECT, related_name="variants")
    is_available = models.BooleanField(default=True)

    class Meta:
        ordering = ["size__position", "color__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "size", "color"], name="unique_variant_per_product"
            )
        ]

    def __str__(self):
        return f"{self.product.code} / {self.size} / {self.color}"


class ProductImage(models.Model):
    """color = null means a shared photo or a collage showing all colors."""

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="images"
    )
    color = models.ForeignKey(
        Color, null=True, blank=True, on_delete=models.SET_NULL, related_name="images"
    )
    image = models.ImageField(upload_to="products/")
    alt_text = models.CharField(max_length=200, blank=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return f"{self.product.code} image {self.position}"


class Collection(models.Model):
    """Hand-picked groups you control: New Arrivals, Promos."""

    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.CharField(max_length=300, blank=True)
    is_active = models.BooleanField(default=True)
    position = models.PositiveIntegerField(default=0)
    products = models.ManyToManyField(
        Product, through="CollectionProduct", related_name="collections", blank=True
    )

    class Meta:
        ordering = ["position", "name"]

    def __str__(self):
        return self.name


class CollectionProduct(models.Model):
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["collection", "product"], name="unique_product_per_collection"
            )
        ]

    def __str__(self):
        return f"{self.collection} / {self.product.code}"


class Favorite(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favorites"
    )
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="favorited_by"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "product"], name="unique_favorite")
        ]

    def __str__(self):
        return f"{self.user} -> {self.product.code}"
