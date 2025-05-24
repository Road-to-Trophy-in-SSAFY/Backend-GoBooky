from django.contrib.auth import get_user_model, authenticate
from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.password_validation import validate_password
from .models import User
from books.models import Category

User = get_user_model()


# 닉네임 중복 확인 시리얼라이저
class CheckNicknameSerializer(serializers.Serializer):
    username = serializers.CharField(min_length=2, max_length=20)


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
    profile_picture = serializers.ImageField(read_only=True)
    profile_picture_url = serializers.SerializerMethodField()
    followers_count = serializers.SerializerMethodField()
    following_count = serializers.SerializerMethodField()
    is_following = serializers.SerializerMethodField()

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
            "profile_picture",
            "profile_picture_url",
            "followers_count",
            "following_count",
            "is_following",
        ]
        extra_kwargs = {
            "password": {"write_only": True},
            "email": {"required": True},
            "username": {"required": True},
            "first_name": {"required": True},
            "last_name": {"required": True},
            "gender": {"required": True},
        }

    def get_profile_picture_url(self, obj):
        return (
            obj.get_profile_picture_url()
            if hasattr(obj, "get_profile_picture_url")
            else None
        )

    def get_followers_count(self, obj):
        return obj.followers.count()

    def get_following_count(self, obj):
        return obj.following.count()

    def get_is_following(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return obj.followers.filter(id=request.user.id).exists()
        return False

    def create(self, validated_data):
        category_ids = validated_data.pop("category_ids", [])
        user = User.objects.create_user(**validated_data)
        if category_ids:
            user.categories.set(category_ids)
        return user


class ProfileUpdateSerializer(UserSerializer):
    # Override fields that are not directly editable via this serializer
    email = serializers.EmailField(read_only=True)
    username = serializers.CharField(read_only=True)
    first_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)
    # password is not included in fields, so it's not updated by default

    # Make profile_picture writable for updates
    profile_picture = serializers.ImageField(required=False, allow_null=True)

    class Meta(UserSerializer.Meta):
        # Inherit fields from UserSerializer, exclude password
        fields = [f for f in UserSerializer.Meta.fields if f != "password"]
        # Ensure profile_picture is included and writable status is handled above
        # Make categories writable via category_ids
        extra_kwargs = {
            "weekly_read_time": {"required": False, "allow_null": True},
            "yearly_read_count": {"required": False, "allow_null": True},
            "categories": {"read_only": True},  # Exclude categories from direct update
            "category_ids": {"write_only": True, "required": False},
            "profile_picture": {"required": False, "allow_null": True},
        }

    def update(self, instance, validated_data):
        category_ids = validated_data.pop("category_ids", None)
        profile_picture = validated_data.pop("profile_picture", None)

        # Update user fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Update categories if category_ids is provided
        if category_ids is not None:
            instance.categories.set(category_ids)

        # Update profile picture
        if profile_picture is not None:
            instance.profile_picture = profile_picture
        elif (
            profile_picture is None
            and "profile_picture" in self.initial_data
            and self.initial_data["profile_picture"] is None
        ):
            # Handle case where user explicitly sets profile_picture to null to remove it
            instance.profile_picture = None

        instance.save()
        return instance
