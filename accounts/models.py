from django.contrib.auth.models import AbstractUser
from django.db import models
from books.models import Category


class User(AbstractUser):
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    gender = models.CharField(max_length=10)
    weekly_read_time = models.IntegerField(
        null=True, blank=True
    )  # 주간 평균 독서 시간 (시간 단위)
    yearly_read_count = models.IntegerField(null=True, blank=True)  # 연간 독서량
    categories = models.ManyToManyField(Category, related_name="users")
    # 프로필 이미지, 추가 필드 등 필요시 확장
    # profile_image = models.ImageField(upload_to='profiles/', blank=True, null=True)
    # 기타 필드 추가 가능

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username", "first_name", "last_name", "gender"]

    def __str__(self):
        return self.email
