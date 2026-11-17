from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group
from django.db.models import Count
from unfold.admin import ModelAdmin
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm

from .models import User


class UserCreateForm(UserCreationForm):
    class Meta:
        model = User
        fields = ["email", "username"]


class UserEditForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"


# Re-register Group so it picks up the Unfold styling too.
admin.site.unregister(Group)


@admin.register(Group)
class GroupAdmin(BaseGroupAdmin, ModelAdmin):
    pass


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    """Shoppers and staff. Email is the login; username is the display name."""

    add_form = UserCreateForm
    form = UserEditForm
    change_password_form = AdminPasswordChangeForm
    list_display = [
        "email",
        "username",
        "is_staff",
        "is_active",
        "favorite_count",
        "date_joined",
        "last_login",
    ]
    list_filter = ["is_staff", "is_superuser", "is_active", "groups"]
    search_fields = ["email", "username"]
    ordering = ["-date_joined"]
    date_hierarchy = "date_joined"
    readonly_fields = ["date_joined", "last_login"]
    fieldsets = [
        (None, {"fields": ["email", "username", "password"]}),
        (
            "Permissions",
            {
                "fields": [
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ],
                "classes": ["collapse"],
            },
        ),
        ("Dates", {"fields": ["date_joined", "last_login"]}),
    ]
    add_fieldsets = [
        (
            None,
            {
                "classes": ["wide"],
                "fields": [
                    "email",
                    "username",
                    "usable_password",
                    "password1",
                    "password2",
                ],
            },
        ),
    ]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(favorite_count=Count("favorites", distinct=True))
        )

    @admin.display(description="Favorites", ordering="favorite_count")
    def favorite_count(self, obj):
        return obj.favorite_count
