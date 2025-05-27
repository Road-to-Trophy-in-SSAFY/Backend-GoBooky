from django.urls import path
from .views import (
    RegisterView,
    VerifyEmailView,
    ResendEmailView,
    ProfileCompleteView,
    AccountDeleteView,
    get_categories,
    CheckNicknameView,
    ProfileDetailView,
    FollowToggleView,
    UserBooksView,
    UserCommentsView,
    UserThreadsView,
    BookSaveToggleView,
)

# 새로운 JWT 뷰들 import
from .jwt_views import (
    CustomTokenObtainPairView,
    CustomTokenRefreshView,
    CustomTokenBlacklistView,
)

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/register/verify/", VerifyEmailView.as_view(), name="verify-email"),
    path(
        "auth/verify-email/<str:uuid>/",
        VerifyEmailView.as_view(),
        name="verify-email-link",
    ),
    path("auth/resend-email/", ResendEmailView.as_view(), name="resend-email"),
    path(
        "auth/register/complete/",
        ProfileCompleteView.as_view(),
        name="profile-complete",
    ),
    # JWT 인증 엔드포인트 (지침 권장 방식)
    path("auth/jwt/login/", CustomTokenObtainPairView.as_view(), name="jwt-login"),
    path("auth/jwt/refresh/", CustomTokenRefreshView.as_view(), name="jwt-refresh"),
    path("auth/jwt/logout/", CustomTokenBlacklistView.as_view(), name="jwt-logout"),
    path("auth/account/", AccountDeleteView.as_view(), name="account-delete"),
    path("auth/categories/", get_categories, name="get-categories"),
    path("auth/check-nickname/", CheckNicknameView.as_view(), name="check-nickname"),
    path(
        "auth/profile/<str:username>/",
        ProfileDetailView.as_view(),
        name="profile-detail",
    ),
    path(
        "auth/profile/<str:username>/follow/",
        FollowToggleView.as_view(),
        name="profile-follow-toggle",
    ),
    # 사용자별 데이터 조회 API
    path(
        "auth/profile/<str:username>/books/",
        UserBooksView.as_view(),
        name="user-books",
    ),
    path(
        "auth/profile/<str:username>/comments/",
        UserCommentsView.as_view(),
        name="user-comments",
    ),
    path(
        "auth/profile/<str:username>/threads/",
        UserThreadsView.as_view(),
        name="user-threads",
    ),
    # 책 저장 토글 API
    path(
        "auth/books/<int:book_id>/save/",
        BookSaveToggleView.as_view(),
        name="book-save-toggle",
    ),
]
