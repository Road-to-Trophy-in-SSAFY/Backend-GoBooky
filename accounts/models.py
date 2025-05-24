from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from books.models import Category
from django.utils import timezone
from django.conf import settings


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=150, unique=True)
    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    gender = models.CharField(max_length=10, blank=True)
    weekly_read_time = models.IntegerField(null=True, blank=True)
    yearly_read_count = models.IntegerField(null=True, blank=True)
    categories = models.ManyToManyField(
        "books.Category", related_name="users", blank=True
    )
    date_joined = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(auto_now=True)
    # Added profile picture field
    profile_picture = models.ImageField(
        upload_to="profile_pictures/",
        blank=True,
        null=True,
        default="profile_pictures/default-profile.jpg",
    )
    # 팔로우/팔로잉 관계 필드 추가
    following = models.ManyToManyField(
        "self", symmetrical=False, related_name="followers", blank=True
    )

    objects = CustomUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email

    def get_profile_picture_url(self):
        if self.profile_picture:
            return self.profile_picture.url
        return f"{settings.MEDIA_URL}profile_pictures/default-profile.jpg"


class AuditLog(models.Model):
    ACTION_CHOICES = [
        ("login", "Login"),
        ("logout", "Logout"),
        ("refresh_token", "Refresh Token"),
        ("failed_login", "Failed Login"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now)
    details = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.action} - {self.user.email if self.user else 'Anonymous'} - {self.timestamp}"
