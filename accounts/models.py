from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)
    # 프로필 이미지, 추가 필드 등 필요시 확장
    # profile_image = models.ImageField(upload_to='profiles/', blank=True, null=True)
    # 기타 필드 추가 가능

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    def __str__(self):
        return self.email


class Category(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name
