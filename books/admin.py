from django.contrib import admin
from .models import Book, Category, Thread, Comment, Reply

# Register your models here.


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "thread",
        "user",
        "content_preview",
        "created_at",
        "is_deleted",
    ]
    list_filter = ["created_at", "is_deleted", "thread"]
    search_fields = ["content", "user__email", "thread__title"]
    readonly_fields = ["created_at", "updated_at"]

    def content_preview(self, obj):
        return obj.content[:50] + "..." if len(obj.content) > 50 else obj.content

    content_preview.short_description = "내용 미리보기"


@admin.register(Reply)
class ReplyAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "comment",
        "user",
        "content_preview",
        "created_at",
        "is_deleted",
    ]
    list_filter = ["created_at", "is_deleted"]
    search_fields = ["content", "user__email", "comment__content"]
    readonly_fields = ["created_at", "updated_at"]

    def content_preview(self, obj):
        return obj.content[:50] + "..." if len(obj.content) > 50 else obj.content

    content_preview.short_description = "내용 미리보기"
