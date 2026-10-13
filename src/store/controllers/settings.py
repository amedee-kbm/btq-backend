from ninja import Schema
from ninja_extra import api_controller, http_get

from store.models import SiteSettings


class SocialsOut(Schema):
    instagram: str
    tiktok: str
    x: str
    facebook: str


class SiteSettingsOut(Schema):
    whatsapp_number: str
    whatsapp_template: str
    whatsapp_restock_template: str
    phone: str
    email: str
    address: str
    socials: SocialsOut


@api_controller("/settings", tags=["Store"])
class SettingsController:
    @http_get("", response=SiteSettingsOut)
    def get_settings(self, request):
        s = SiteSettings.load()
        return {
            "whatsapp_number": s.whatsapp_number,
            "whatsapp_template": s.whatsapp_template,
            "whatsapp_restock_template": s.whatsapp_restock_template,
            "phone": s.phone,
            "email": s.email,
            "address": s.address,
            "socials": {
                "instagram": s.instagram_url,
                "tiktok": s.tiktok_url,
                "x": s.x_url,
                "facebook": s.facebook_url,
            },
        }
