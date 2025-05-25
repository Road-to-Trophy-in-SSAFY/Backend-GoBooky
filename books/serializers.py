from rest_framework import serializers
from .models import Book, Category, Thread


class BookListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = Book
        fields = (
            "id",
            "title",
            "cover",
            "author",
            "publisher",
            "pub_date",
            "subTitle",
            "category_name",
        )


class BookDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Book
        fields = "__all__"


class BookTitleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Book
        fields = ("title",)


class BookTitleWithCategorySerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = Book
        fields = ("title", "category_name")


# 전체 쓰레드
class ThreadListSerializer(serializers.ModelSerializer):
    book = BookTitleWithCategorySerializer()
    likes_count = serializers.SerializerMethodField()
    liked = serializers.SerializerMethodField()
    cover_img_url = serializers.SerializerMethodField()

    class Meta:
        model = Thread
        fields = (
            "id",
            "title",
            "book",
            "likes_count",
            "liked",
            "cover_img",
            "cover_img_url",
        )

    def get_likes_count(self, obj):
        return obj.likes.count()

    def get_liked(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return obj.likes.filter(id=request.user.id).exists()
        return False

    def get_cover_img_url(self, obj):
        if obj.cover_img:
            request = self.context.get("request")
            if request is not None:
                return request.build_absolute_uri(obj.cover_img.url)
            return obj.cover_img.url
        return None


# 쓰레드 생성/수정용
class ThreadSerializer(serializers.ModelSerializer):
    book = serializers.PrimaryKeyRelatedField(queryset=Book.objects.all())
    likes_count = serializers.SerializerMethodField(read_only=True)
    liked = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Thread
        fields = (
            "id",
            "book",
            "title",
            "content",
            "reading_date",
            "created_at",
            "updated_at",
            "likes_count",
            "liked",
        )

    def get_likes_count(self, obj):
        return obj.likes.count()

    def get_liked(self, obj):
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            print(
                f"[DRF][get_liked] user: {request.user}, authenticated: {request.user.is_authenticated}, thread_id: {obj.id}"
            )
            print(f"[DRF][get_liked] likes: {[u.id for u in obj.likes.all()]}")
            if request.user.is_authenticated:
                liked = obj.likes.filter(id=request.user.id).exists()
                print(f"[DRF][get_liked] liked: {liked}")
                return liked
        return False


# 단일 쓰레드
class ThreadDetailSerializer(serializers.ModelSerializer):
    book = BookTitleSerializer(read_only=True)
    user = serializers.SerializerMethodField()
    likes_count = serializers.SerializerMethodField()
    liked = serializers.SerializerMethodField()
    cover_img_url = serializers.SerializerMethodField()

    class Meta:
        model = Thread
        fields = (
            "id",
            "book",
            "user",
            "title",
            "content",
            "cover_img",
            "cover_img_url",
            "reading_date",
            "created_at",
            "updated_at",
            "likes_count",
            "liked",
        )

    def get_user(self, obj):
        return {
            "id": obj.user.id,
            "email": obj.user.email,
            "username": obj.user.username,
        }

    def get_likes_count(self, obj):
        return obj.likes.count()

    def get_liked(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return obj.likes.filter(id=request.user.id).exists()
        return False

    def get_cover_img_url(self, obj):
        if obj.cover_img:
            request = self.context.get("request")
            if request is not None:
                return request.build_absolute_uri(obj.cover_img.url)
            return obj.cover_img.url
        return None
