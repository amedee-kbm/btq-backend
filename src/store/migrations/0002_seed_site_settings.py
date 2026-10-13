from django.db import migrations


def seed(apps, schema_editor):
    SiteSettings = apps.get_model("store", "SiteSettings")
    SiteSettings.objects.get_or_create(
        pk=1,
        defaults={
            "whatsapp_number": "250781427209",
            "phone": "+250781427209",
            "address": "CHIC Building B30A, Kigali",
            "instagram_url": "https://instagram.com/btq.",
            "tiktok_url": "https://www.tiktok.com/@btq.",
        },
    )


class Migration(migrations.Migration):
    dependencies = [("store", "0001_initial")]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
