from rest_framework import serializers
from dj_rest_auth.registration.serializers import RegisterSerializer
from dj_rest_auth.serializers import UserDetailsSerializer
from .models import CustomUser, Category


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name")


class CustomRegisterSerializer(RegisterSerializer):
    # 기존 RegisterSerializer에 추가 필드 정의
    gender = serializers.ChoiceField(choices=CustomUser.GENDER_CHOICES)
    age = serializers.IntegerField(min_value=0)
    annual_reading_count = serializers.IntegerField(min_value=0)
    weekly_avg_reading_time = serializers.IntegerField(min_value=0, required=False)
    profile_image = serializers.ImageField()
    categories = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Category.objects.all()
    )

    def custom_signup(self, request, user):
        # 기본 회원가입 로직 이후에 추가 필드에 대한 처리
        user.gender = self.validated_data.get("gender", "")
        user.age = self.validated_data.get("age", 0)
        user.annual_reading_count = self.validated_data.get("annual_reading_count", 0)
        user.weekly_avg_reading_time = self.validated_data.get(
            "weekly_avg_reading_time", None
        )
        user.profile_image = self.validated_data.get("profile_image")
        user.save()

        # ManyToMany 관계인 categories 처리
        categories = self.validated_data.get("categories", [])
        user.categories.set(categories)


class CustomUserDetailsSerializer(UserDetailsSerializer):
    categories = CategorySerializer(many=True, read_only=True)

    class Meta(UserDetailsSerializer.Meta):
        model = CustomUser
        fields = UserDetailsSerializer.Meta.fields + (
            "gender",
            "age",
            "weekly_avg_reading_time",
            "annual_reading_count",
            "profile_image",
            "categories",
        )
        read_only_fields = ("email",)
