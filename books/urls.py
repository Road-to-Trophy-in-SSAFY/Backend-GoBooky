from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers
from . import views

# ViewSet을 위한 라우터 설정 (지침 권장 방식)
router = DefaultRouter()
router.register(r"books", views.BookViewSet, basename="book")
router.register(r"threads", views.ThreadViewSet, basename="thread")
router.register(r"categories", views.CategoryViewSet, basename="category")

# 중첩 라우터 - Thread > Comments
threads_router = routers.NestedDefaultRouter(router, r"threads", lookup="thread")
threads_router.register(r"comments", views.CommentViewSet, basename="thread-comments")

# 중첩 라우터 - Comment > Replies
comments_router = routers.NestedDefaultRouter(
    threads_router, r"comments", lookup="comment"
)
comments_router.register(r"replies", views.ReplyViewSet, basename="comment-replies")

# 기존 함수 기반 뷰 URL 패턴 (호환성 유지)
legacy_urlpatterns = [
    path("books/", views.book_list, name="book-list-legacy"),
    path("books/<int:book_id>/", views.book_detail, name="book-detail-legacy"),
    # 기존 함수 기반 뷰들은 레거시로 유지
]

urlpatterns = [
    # 새로운 API 엔드포인트 (ViewSet보다 먼저 처리되도록)
    path("api/books/random/", views.random_books, name="random-books"),
    path("api/threads/popular/", views.popular_threads, name="popular-threads"),
    path("api/books/search/", views.search_books, name="search-books"),
    # ViewSet 기반 URL (권장)
    path("api/", include(router.urls)),
    path("api/", include(threads_router.urls)),
    path("api/", include(comments_router.urls)),
    # 레거시 URL 패턴 (호환성 유지)
    path("legacy/", include(legacy_urlpatterns)),
]
