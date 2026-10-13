from django.db.models.signals import post_delete, post_save

from catalog import revalidate

from .models import SiteSettings


def settings_changed(sender, **kwargs):
    revalidate.schedule("settings")


post_save.connect(settings_changed, sender=SiteSettings)
post_delete.connect(settings_changed, sender=SiteSettings)
