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

    class Meta:
        model = Thread
        fields = ("id", "title", "book", "likes_count", "liked")

    def get_likes_count(self, obj):
        return obj.likes.count()

    def get_liked(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return obj.likes.filter(id=request.user.id).exists()
        return False


# 쓰레드 상세
class ThreadSerializer(serializers.ModelSerializer):
    book = BookTitleSerializer(read_only=True)
    likes_count = serializers.SerializerMethodField()
    liked = serializers.SerializerMethodField()

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
    likes_count = serializers.SerializerMethodField()
    liked = serializers.SerializerMethodField()

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
        if request and request.user.is_authenticated:
            return obj.likes.filter(id=request.user.id).exists()
        return False
