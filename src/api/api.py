from ninja_extra import NinjaExtraAPI
from ninja import Redoc
from accounts.controllers.auth import AuthController
from accounts.controllers.me import MeController

api = NinjaExtraAPI(docs_url="/docs", docs=Redoc())


@api.get("/health", tags=["health"])
def health(request):
    return {"message": "success"}


api.register_controllers(AuthController)
api.register_controllers(MeController)

