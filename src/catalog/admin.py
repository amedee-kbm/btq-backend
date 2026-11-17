import itertools

from django.contrib import admin
from django.db.models import Count, Exists, F, Max, OuterRef
from django.db.models.functions import Coalesce
from django.utils.html import format_html
from unfold.admin import ModelAdmin, StackedInline, TabularInline

from . import revalidate
from .forms import ProductAdminForm
from .models import (
    Category,
    Collection,
    CollectionProduct,
    Color,
    Favorite,
    Product,
    ProductImage,
    Size,
    Tag,
    Variant,
)


def thumbnail(image, size):
    if not image:
        return "-"
    return format_html(
        '<img src="{}" style="width:{}px;height:{}px;object-fit:cover;border-radius:4px">',
        image.url,
        size,
        size,
    )


def plain_select(formfield, label):
    """Size/color dropdown that names itself and drops the add/edit buttons.

    Inline column headers are hidden on phones, and the buttons squeeze the row.
    Sizes and colors have their own admin pages.
    """
    formfield.empty_label = label
    widget = formfield.widget
    widget.can_add_related = widget.can_change_related = False
    widget.can_delete_related = widget.can_view_related = False
    return formfield


def available_variants():
    return Variant.objects.filter(product=OuterRef("pk"), is_available=True)


# --- Product ---------------------------------------------------------------


class OnSaleFilter(admin.SimpleListFilter):
    title = "on sale"
    parameter_name = "on_sale"

    def lookups(self, request, model_admin):
        return [("yes", "Yes"), ("no", "No")]

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(sale_price__isnull=False)
        if self.value() == "no":
            return queryset.filter(sale_price__isnull=True)
        return queryset


class SoldOutFilter(admin.SimpleListFilter):
    """Sold out = no available variant (same rule as Product.is_sold_out)."""

    title = "sold out"
    parameter_name = "sold_out"

    def lookups(self, request, model_admin):
        return [("yes", "Yes"), ("no", "No")]

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(~Exists(available_variants()))
        if self.value() == "no":
            return queryset.filter(Exists(available_variants()))
        return queryset


class VariantInline(TabularInline):
    """Existing variants. New ones usually come from "Add variants"."""

    model = Variant
    extra = 0
    show_title = False  # "BQ-0100 / M / Black" repeats the row's own dropdowns

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name in ("size", "color"):
            return plain_select(formfield, db_field.verbose_name.capitalize())
        return formfield


class ProductImageInline(StackedInline):
    """Stacked: as a table it scrolls sideways on phones. Drag to reorder.

    The image widget shows its own thumbnail. New photos usually come from
    "Add photos".
    """

    model = ProductImage
    extra = 0
    fields = ["image", "color", "alt_text", "position"]
    ordering_field = "position"
    hide_ordering_field = True

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name == "color":
            return plain_select(formfield, "All colors")
        return formfield


@admin.register(Product)
class ProductAdmin(ModelAdmin):
    form = ProductAdminForm
    list_display = [
        "code",
        "name",
        "list_thumbnail",
        "price",
        "sale_price",
        "is_published",
        "sold_out",
        "updated_at",
    ]
    list_display_links = ["code", "name"]
    list_editable = ["price", "sale_price", "is_published"]
    list_filter = ["is_published", OnSaleFilter, SoldOutFilter, "categories", "tags"]
    list_per_page = 50
    search_fields = ["code", "name", "material", "categories__name", "tags__name"]
    save_on_top = True
    prepopulated_fields = {"slug": ("name",)}
    # Search boxes, not filter_horizontal: those take a third of a phone screen.
    autocomplete_fields = ["categories", "tags"]
    readonly_fields = ["created_at", "updated_at"]
    actions = ["publish", "unpublish", "mark_sold_out", "mark_available", "end_sale"]
    inlines = [ProductImageInline, VariantInline]
    fieldsets = [
        ("Basics", {"fields": ["name", "slug", "code", "is_published"]}),
        ("Pricing", {"fields": ["price", "sale_price"]}),
        ("Details", {"fields": ["description", "material", "fit_note"]}),
        ("Classification", {"fields": ["categories", "tags"]}),
        ("Add photos", {"fields": ["new_photos", "new_photos_color"]}),
        ("Add variants", {"fields": ["variant_sizes", "variant_colors"]}),
        (
            "Timestamps",
            {"fields": ["created_at", "updated_at"], "classes": ["collapse"]},
        ),
    ]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(has_available_variant=Exists(available_variants()))
            .prefetch_related("images")
        )

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if obj:
            return fieldsets
        # Nothing to show before the first save.
        return [fs for fs in fieldsets if fs[0] != "Timestamps"]

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        product, data = form.instance, form.cleaned_data

        if data["new_photos"]:
            last = product.images.aggregate(last=Max("position"))["last"]
            start = 0 if last is None else last + 1
            for offset, photo in enumerate(data["new_photos"]):
                product.images.create(
                    image=photo, color=data["new_photos_color"], position=start + offset
                )

        pairs = itertools.product(data["variant_sizes"], data["variant_colors"])
        Variant.objects.bulk_create(
            [Variant(product=product, size=s, color=c) for s, c in pairs],
            ignore_conflicts=True,  # keeps existing variants as they are
        )
        if data["variant_sizes"]:
            revalidate.schedule("catalog")  # bulk_create skips post_save signals

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name in ("price", "sale_price"):
            # Digit keypad on phones; RWF has no decimals.
            formfield.widget.attrs["inputmode"] = "numeric"
        return formfield

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "categories":
            # Category.__str__ reads the parent.
            kwargs["queryset"] = Category.objects.select_related("parent")
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    @admin.display(description="Image")
    def list_thumbnail(self, obj):
        # Uses the prefetched images; .first() would query again.
        first = next(iter(obj.images.all()), None)
        return thumbnail(first.image if first else None, 48)

    @admin.display(
        description="Sold out", boolean=True, ordering="has_available_variant"
    )
    def sold_out(self, obj):
        return not obj.has_available_variant

    @admin.action(description="Publish selected products")
    def publish(self, request, queryset):
        count = queryset.update(is_published=True)
        revalidate.schedule("catalog")  # update() skips post_save signals
        self.message_user(request, f"{count} product(s) published.")

    @admin.action(description="Unpublish selected products")
    def unpublish(self, request, queryset):
        count = queryset.update(is_published=False)
        revalidate.schedule("catalog")  # update() skips post_save signals
        self.message_user(request, f"{count} product(s) unpublished.")

    @admin.action(description="Mark selected products sold out (all variants)")
    def mark_sold_out(self, request, queryset):
        count = Variant.objects.filter(product__in=queryset).update(is_available=False)
        revalidate.schedule("catalog")  # update() skips post_save signals
        self.message_user(request, f"{count} variant(s) marked unavailable.")

    @admin.action(description="Mark selected products available (all variants)")
    def mark_available(self, request, queryset):
        count = Variant.objects.filter(product__in=queryset).update(is_available=True)
        revalidate.schedule("catalog")  # update() skips post_save signals
        self.message_user(request, f"{count} variant(s) marked available.")

    @admin.action(description="End sale on selected products")
    def end_sale(self, request, queryset):
        count = queryset.filter(sale_price__isnull=False).update(sale_price=None)
        revalidate.schedule("catalog")  # update() skips post_save signals
        self.message_user(request, f"Sale ended on {count} product(s).")


# --- Category / Collection -------------------------------------------------


@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    list_display = [
        "__str__",
        "parent",
        "cover",
        "show_on_home",
        "position",
        "product_count",
    ]
    list_editable = ["show_on_home", "position"]
    list_filter = ["show_on_home", ("parent", admin.RelatedOnlyFieldListFilter)]
    # parent__name: searching "dress" also finds "Dresses > Party".
    search_fields = ["name", "parent__name"]
    prepopulated_fields = {"slug": ("name",)}
    # Each parent, then its children. Set here because the product_count
    # annotation (GROUP BY) drops Meta.ordering.
    ordering = [
        Coalesce("parent__position", "position"),
        Coalesce("parent__name", "name"),
        F("parent").asc(nulls_first=True),
        "position",
        "name",
    ]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("parent")
            .annotate(product_count=Count("products", distinct=True))
        )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "parent":
            # Only top-level parents: keeps nesting at two levels.
            kwargs["queryset"] = Category.objects.filter(parent__isnull=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    @admin.display(description="Cover")
    def cover(self, obj):
        return thumbnail(obj.cover_image, 48)

    @admin.display(description="Products", ordering="product_count")
    def product_count(self, obj):
        return obj.product_count


class CollectionProductInline(TabularInline):
    model = CollectionProduct
    extra = 1
    fields = ["product", "position"]
    autocomplete_fields = ["product"]


@admin.register(Collection)
class CollectionAdmin(ModelAdmin):
    list_display = ["name", "description", "is_active", "position", "product_count"]
    list_editable = ["is_active", "position"]
    list_filter = ["is_active"]
    search_fields = ["name"]
    ordering = ["position", "name"]  # the product_count annotation drops Meta.ordering
    save_on_top = True
    prepopulated_fields = {"slug": ("name",)}
    inlines = [CollectionProductInline]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(product_count=Count("products", distinct=True))
        )

    @admin.display(description="Products", ordering="product_count")
    def product_count(self, obj):
        return obj.product_count


# --- Lookup lists ----------------------------------------------------------


@admin.register(Tag)
class TagAdmin(ModelAdmin):
    list_display = ["name", "slug", "product_count"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ("name",)}
    ordering = ["name"]  # the product_count annotation drops Meta.ordering

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(product_count=Count("products", distinct=True))
        )

    @admin.display(description="Products", ordering="product_count")
    def product_count(self, obj):
        return obj.product_count


@admin.register(Size)
class SizeAdmin(ModelAdmin):
    list_display = ["name", "position"]
    list_editable = ["position"]
    search_fields = ["name"]


@admin.register(Color)
class ColorAdmin(ModelAdmin):
    list_display = ["name", "swatch", "hex_code"]
    list_editable = ["hex_code"]
    search_fields = ["name", "hex_code"]

    @admin.display(description="Swatch")
    def swatch(self, obj):
        if not obj.hex_code:
            return "-"
        return format_html(
            '<span style="display:inline-block;width:24px;height:24px;'
            'border:1px solid #ccc;border-radius:4px;background:{}"></span>',
            obj.hex_code,
        )


# --- Customer data ---------------------------------------------------------


@admin.register(Favorite)
class FavoriteAdmin(ModelAdmin):
    """Read-only: favorites belong to customers."""

    list_display = ["user", "product", "created_at"]
    list_filter = ["created_at"]
    date_hierarchy = "created_at"
    list_select_related = ["user", "product"]
    search_fields = ["user__email", "product__code", "product__name"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
