from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# ViewSet을 위한 라우터 설정 (지침 권장 방식)
router = DefaultRouter()
router.register(r"books", views.BookViewSet, basename="book")
router.register(r"threads", views.ThreadViewSet, basename="thread")
router.register(r"categories", views.CategoryViewSet, basename="category")

# 기존 함수 기반 뷰 URL 패턴 (호환성 유지)
legacy_urlpatterns = [
    path("books/", views.book_list, name="book-list-legacy"),
    path("books/<int:book_id>/", views.book_detail, name="book-detail-legacy"),
    # 기존 함수 기반 뷰들은 레거시로 유지
]

urlpatterns = [
    # ViewSet 기반 URL (권장)
    path("api/", include(router.urls)),
    # 레거시 URL 패턴 (호환성 유지)
    path("legacy/", include(legacy_urlpatterns)),
]
