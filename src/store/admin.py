from django.contrib import admin
from django.shortcuts import redirect
from unfold.admin import ModelAdmin

from .models import SiteSettings


@admin.register(SiteSettings)
class SiteSettingsAdmin(ModelAdmin):
    """One record: the list page jumps straight to it; no add or delete."""

    fieldsets = [
        (
            "Storefront",
            {"fields": ["show_prices", "show_product_names", "show_color_swatches"]},
        ),
        (
            "WhatsApp",
            {
                "fields": [
                    "whatsapp_number",
                    "whatsapp_template",
                    "whatsapp_restock_template",
                ]
            },
        ),
        ("Contact", {"fields": ["phone", "email", "address"]}),
        (
            "Social links",
            {"fields": ["instagram_url", "tiktok_url", "x_url", "facebook_url"]},
        ),
    ]

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        settings = SiteSettings.objects.first()
        if settings:
            return redirect("admin:store_sitesettings_change", settings.pk)
        return super().changelist_view(request, extra_context)
