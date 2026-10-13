from ninja_extra import NinjaExtraAPI
from ninja import Redoc
from accounts.controllers.auth import AuthController
from accounts.controllers.favorites import FavoritesController
from accounts.controllers.me import MeController
from catalog.controllers.categories import CategoriesController
from catalog.controllers.collections import CollectionsController
from catalog.controllers.lookups import LookupsController
from catalog.controllers.products import ProductsController
from store.controllers.settings import SettingsController

api = NinjaExtraAPI(docs_url="/docs", docs=Redoc())


@api.get("/health", tags=["health"])
def health(request):
    return {"message": "success"}


api.register_controllers(AuthController)
api.register_controllers(MeController)
api.register_controllers(FavoritesController)
api.register_controllers(ProductsController)
api.register_controllers(CategoriesController)
api.register_controllers(LookupsController)
api.register_controllers(CollectionsController)
api.register_controllers(SettingsController)
