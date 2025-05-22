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

    class Meta:
        model = Thread
        fields = ("id", "title", "book")


# 쓰레드 상세
class ThreadSerializer(serializers.ModelSerializer):
    book = BookTitleSerializer(read_only=True)

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
        )


# 단일 쓰레드
class ThreadDetailSerializer(serializers.ModelSerializer):
    book = BookTitleSerializer(read_only=True)

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
        )
