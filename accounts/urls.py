from django.urls import path
from .views import (
    RegisterView,
    VerifyEmailView,
    ResendEmailView,
    ProfileCompleteView,
    LoginView,
    LogoutView,
    AccountDeleteView,
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
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/account/", AccountDeleteView.as_view(), name="account-delete"),
]
