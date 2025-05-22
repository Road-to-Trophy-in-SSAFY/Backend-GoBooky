from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Category


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ("id", "email", "username", "is_active", "is_staff")
    search_fields = ("email", "username")
    ordering = ("id",)
    fieldsets = UserAdmin.fieldsets + ((None, {"fields": ()}),)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
