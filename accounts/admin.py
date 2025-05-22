from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Category


# Register your models here.
class CustomUserAdmin(UserAdmin):
    # UserAdmin 커스터마이징
    fieldsets = UserAdmin.fieldsets + (
        (
            "추가 정보",
            {
                "fields": (
                    "gender",
                    "age",
                    "weekly_avg_reading_time",
                    "annual_reading_count",
                    "profile_image",
                    "categories",
                )
            },
        ),
    )
    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "gender",
        "age",
        "annual_reading_count",
    )
    list_filter = UserAdmin.list_filter + ("gender", "age")
    search_fields = UserAdmin.search_fields + ("gender", "age", "annual_reading_count")


# 모델 등록
admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Category)
