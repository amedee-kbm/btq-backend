from ninja import ModelSchema
from ninja_extra import api_controller, api_controller, http_get
from ninja_jwt.authentication import JWTAuth
from accounts.models import User
import api


class UserOut(ModelSchema):
    class Meta:
        model = User
        fields = ["id", "email", "username", "is_staff"]
        
@api_controller("/me", auth=JWTAuth(),tags=["Me"])
class MeController:
    @http_get("/", response=UserOut)
    def me(self, request):
        return request.user