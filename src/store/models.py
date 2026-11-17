from django.core.validators import RegexValidator
from django.db import models

DEFAULT_WHATSAPP_TEMPLATE = (
    "Hi Btq! I'd like {code} – {name}, size {size}, colour {color} ({price}). "
    "Is it available? {url}"
)
DEFAULT_WHATSAPP_RESTOCK_TEMPLATE = (
    "Hi Btq! Is {code} – {name} coming back in size {size}, colour {color}? {url}"
)
PLACEHOLDERS_HELP = "Placeholders: {code}, {name}, {size}, {color}, {price}, {url}"


class SiteSettings(models.Model):
    """Storefront options, contact and WhatsApp details. A single row, always pk=1."""

    show_prices = models.BooleanField(
        default=True, help_text="Untick to hide prices across the website"
    )
    whatsapp_number = models.CharField(
        max_length=20,
        validators=[RegexValidator(r"^\d+$", "Digits only, e.g. 250781427209.")],
        help_text="International format, digits only, e.g. 250781427209",
    )
    whatsapp_template = models.TextField(
        default=DEFAULT_WHATSAPP_TEMPLATE, help_text=PLACEHOLDERS_HELP
    )
    whatsapp_restock_template = models.TextField(
        default=DEFAULT_WHATSAPP_RESTOCK_TEMPLATE,
        help_text=f"Sent for sold-out items. {PLACEHOLDERS_HELP}",
    )
    phone = models.CharField(max_length=20, help_text="e.g. +250781427209")
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=200)
    instagram_url = models.URLField(blank=True, help_text="Leave blank to hide")
    tiktok_url = models.URLField(blank=True, help_text="Leave blank to hide")
    x_url = models.URLField(blank=True, help_text="Leave blank to hide")
    facebook_url = models.URLField(blank=True, help_text="Leave blank to hide")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "site settings"
        verbose_name_plural = "site settings"

    def __str__(self):
        return "Site settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        return cls.objects.get_or_create(pk=1)[0]
