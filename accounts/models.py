from django.db import models
from django.contrib.auth.models import AbstractUser


# Create your models here.
class Category(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


class CustomUser(AbstractUser):
    GENDER_CHOICES = (
        ("M", "남성"),
        ("F", "여성"),
    )
    gender = models.CharField(
        max_length=1,
        choices=GENDER_CHOICES,
        null=False,
        blank=False,
        help_text="성별을 선택하세요.",
    )
    age = models.PositiveIntegerField(
        null=False, blank=False, help_text="나이를 입력하세요."
    )
    weekly_avg_reading_time = models.PositiveIntegerField(
        null=True, blank=True, help_text="주간 평균 독서 시간(시간 단위)을 입력하세요."
    )
    annual_reading_count = models.PositiveIntegerField(
        null=False, blank=False, help_text="연간 독서 권수를 입력하세요."
    )
    profile_image = models.ImageField(
        upload_to="profiles/",
        default="profiles/default.png",  # 기본 이미지 설정
        null=False,
        blank=True,  # 폼에서는 빈 값 허용
        help_text="프로필 이미지를 업로드하세요. 없을 경우 기본 이미지가 사용됩니다.",
    )
    categories = models.ManyToManyField(
        Category, help_text="관심 있는 장르를 선택하세요."
    )
