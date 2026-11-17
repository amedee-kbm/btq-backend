from django import forms
from unfold.widgets import (
    UnfoldAdminCheckboxSelectMultipleWidget,
    UnfoldAdminImageSmallFieldWidget,
    UnfoldAdminSelectWidget,
)

from .models import Color, Product, Size


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

    def clean(self):
        cleaned = super().clean()
        sizes, colors = cleaned.get("variant_sizes"), cleaned.get("variant_colors")
        if sizes and not colors:
            self.add_error("variant_colors", "Pick at least one colour.")
        if colors and not sizes:
            self.add_error("variant_sizes", "Pick at least one size.")
        return cleaned
