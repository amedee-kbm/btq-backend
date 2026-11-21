from django import forms
from django.forms.models import BaseInlineFormSet
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
