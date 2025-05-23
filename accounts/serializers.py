from django.contrib.auth import get_user_model, authenticate
from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.password_validation import validate_password
from .models import User
from books.models import Category

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        write_only=True, required=True, validators=[validate_password]
    )
    username = serializers.CharField(required=False)
    first_name = serializers.CharField(required=False)
    last_name = serializers.CharField(required=False)
    gender = serializers.CharField(required=False)
    weekly_read_time = serializers.IntegerField(
        required=False, allow_null=True, help_text="주간 평균 독서 시간 (시간 단위)"
    )
    yearly_read_count = serializers.IntegerField(required=False, allow_null=True)
    category_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False
    )

    class Meta:
        model = User
        fields = (
            "email",
            "password",
            "username",
            "first_name",
            "last_name",
            "gender",
            "weekly_read_time",
            "yearly_read_count",
            "category_ids",
        )

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("이미 가입된 이메일입니다.")
        return value

    def create(self, validated_data):
        category_ids = validated_data.pop("category_ids", [])
        user = User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            username=validated_data.get("username", ""),
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
            gender=validated_data.get("gender", ""),
            weekly_read_time=validated_data.get("weekly_read_time"),
            yearly_read_count=validated_data.get("yearly_read_count"),
            is_active=False,  # 이메일 인증 전까지 비활성
        )
        if category_ids:
            user.categories.set(category_ids)
        return user


class VerifyEmailSerializer(serializers.Serializer):
    uuid = serializers.CharField()


class ProfileCompleteSerializer(serializers.ModelSerializer):
    category_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=True
    )

    class Meta:
        model = User
        fields = (
            "username",
            "first_name",
            "last_name",
            "gender",
            "weekly_read_time",
            "yearly_read_count",
            "category_ids",
        )

    def validate_category_ids(self, value):
        if not value:
            raise serializers.ValidationError("최소 하나의 관심 장르를 선택해주세요.")
        return value


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(email=data["email"], password=data["password"])
        if not user:
            raise serializers.ValidationError(_("이메일 혹은 비밀번호가 틀렸습니다."))
        if not user.is_active:
            raise serializers.ValidationError(_("이메일 인증이 필요합니다."))
        data["user"] = user
        return data


class AccountDeleteSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True)

    def validate_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("비밀번호가 일치하지 않습니다.")
        return value


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name"]


class UserSerializer(serializers.ModelSerializer):
    categories = CategorySerializer(many=True, read_only=True)
    category_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False
    )

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "username",
            "first_name",
            "last_name",
            "gender",
            "weekly_read_time",
            "yearly_read_count",
            "categories",
            "category_ids",
        ]
        extra_kwargs = {
            "password": {"write_only": True},
            "email": {"required": True},
            "username": {"required": True},
            "first_name": {"required": True},
            "last_name": {"required": True},
            "gender": {"required": True},
        }

    def create(self, validated_data):
        category_ids = validated_data.pop("category_ids", [])
        user = User.objects.create_user(**validated_data)
        if category_ids:
            user.categories.set(category_ids)
        return user
