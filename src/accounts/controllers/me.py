from ninja import ModelSchema
from ninja_extra import api_controller, http_get
from ninja_jwt.authentication import JWTAuth
from accounts.models import User


class UserOut(ModelSchema):
    class Meta:
        model = User
        fields = ["id", "email", "username", "is_staff"]


@api_controller("/me", auth=JWTAuth(), tags=["Me"])
class MeController:
    @http_get("/", response=UserOut)
    def me(self, request):
        return request.user

    @http_get("", response=UserOut)
    def me_no_slash(self, request):
        return request.user