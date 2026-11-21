from django import forms
from django.forms.models import BaseInlineFormSet
from django.utils.html import format_html, format_html_join
from unfold.widgets import (
    UnfoldAdminCheckboxSelectMultipleWidget,
    UnfoldAdminImageSmallFieldWidget,
    UnfoldAdminSelectWidget,
)

from .models import Category, Color, Product, ProductImage, Size


class MultipleImageInput(UnfoldAdminImageSmallFieldWidget):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    """Validates each picked file as an image; cleans to a list."""

    widget = MultipleImageInput

    def clean(self, data, initial=None):
        clean_one = super().clean
        if isinstance(data, (list, tuple)):
            return [clean_one(f, initial) for f in data]
        return [clean_one(data, initial)] if data else []


class ProductAdminForm(forms.ModelForm):
    """Adds bulk photo upload and size x colour variant generation.

    ProductAdmin.save_related turns these into ProductImage and Variant rows.
    """

    new_photos = MultipleImageField(
        required=False,
        label="Photos",
        help_text="Pick several at once. They go after any existing photos.",
    )
    new_photos_color = forms.ModelChoiceField(
        Color.objects.all(),
        required=False,
        empty_label="All colors",
        widget=UnfoldAdminSelectWidget,
        label="Colour shown in these photos",
    )
    variant_sizes = forms.ModelMultipleChoiceField(
        Size.objects.all(),
        required=False,
        widget=UnfoldAdminCheckboxSelectMultipleWidget,
        label="Sizes",
    )
    variant_colors = forms.ModelMultipleChoiceField(
        Color.objects.all(),
        required=False,
        widget=UnfoldAdminCheckboxSelectMultipleWidget,
        label="Colours",
        help_text="Creates every size and colour combination. Existing ones are kept.",
    )

    class Meta:
        model = Product
        fields = "__all__"
        help_texts = {"slug": "Leave blank to auto-generate."}

    def clean(self):
        cleaned = super().clean()
        sizes, colors = cleaned.get("variant_sizes"), cleaned.get("variant_colors")
        if sizes and not colors:
            self.add_error("variant_colors", "Pick at least one colour.")
        if colors and not sizes:
            self.add_error("variant_sizes", "Pick at least one size.")
        return cleaned


class ProductImageFormSet(BaseInlineFormSet):
    """A product needs at least one photo: kept inline rows or new uploads."""

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        kept = [
            f
            for f in self.forms
            if f.cleaned_data
            and not f.cleaned_data.get("DELETE")
            and f.cleaned_data.get("image")
        ]
        uploads = self.files.getlist("new_photos") if self.files else []
        if not kept and not uploads:
            raise forms.ValidationError("Add at least one photo.")


class CoverPickerWidget(forms.RadioSelect):
    """Product photos as a grid of clickable thumbnails; choices are
    (storage name, url) pairs."""

    def render(self, name, value, attrs=None, renderer=None):
        if not self.choices:
            return format_html(
                '<p class="cover-picker-empty">No product photos in this category yet.</p>'
            )
        tiles = format_html_join(
            "",
            '<label class="cover-picker-tile">'
            '<input type="radio" name="{}" value="{}"{}>'
            '<img src="{}" loading="lazy" alt="">'
            "</label>",
            (
                (name, key, " checked" if key == value else "", url)
                for key, url in self.choices
            ),
        )
        return format_html('<div class="cover-picker">{}</div>', tiles)


class CategoryAdminForm(forms.ModelForm):
    """Adds a picker to reuse one of the category's product photos as its cover."""

    cover_from_products = forms.ChoiceField(
        required=False,
        label="Choose from product photos",
        help_text="Click a photo to make it the cover. Uses the same file; nothing is uploaded.",
        widget=CoverPickerWidget,
    )

    class Meta:
        model = Category
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        field = self.fields["cover_from_products"]
        if not self.instance.pk:
            field.help_text = (
                "Save the category first; its product photos show up here."
            )
            return
        # Products of a parent category are also linked to the parent, so
        # this covers subcategories too.
        images = (
            ProductImage.objects.filter(product__categories=self.instance)
            .order_by("-product__created_at", "position")
            .distinct()
        )
        seen, choices = set(), []
        for image in images:
            if image.image.name not in seen:
                seen.add(image.image.name)
                choices.append((image.image.name, image.image.url))
        field.choices = choices
        field.initial = self.instance.cover_image.name or None

    def save(self, commit=True):
        chosen = self.cleaned_data.get("cover_from_products")
        # A freshly uploaded cover file wins over a picked photo.
        if chosen and "cover_image" not in self.changed_data:
            self.instance.cover_image.name = chosen
        return super().save(commit)
