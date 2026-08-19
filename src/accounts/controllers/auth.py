from ninja_extra import api_controller, http_post
from ninja_jwt.controller import TokenObtainPairController, TokenVerificationController
from pydantic import EmailStr
from accounts.models import User
from ninja import ModelSchema, Schema
from ninja.errors import HttpError
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError


class UserOut(ModelSchema):
    class Meta:
        model = User
        fields = ["id", "email", "is_staff"]


class RegisterSchema(Schema):
    email: EmailStr
    password: str


@api_controller("/auth", tags=["Auth"])
class AuthController(TokenObtainPairController, TokenVerificationController):
    @http_post("/register", response=UserOut)
    def register(self, payload: RegisterSchema):
        email = payload.email
        password = payload.password

        if User.objects.filter(email__iexact=email).exists():
            raise HttpError(409, "Email already exists.")

        try:
            validate_password(password)
        except ValidationError as e:
            raise HttpError(400, " ".join(e.messages))

        user = User.objects.create_user(email, password)  # type: ignore
        return user
        
