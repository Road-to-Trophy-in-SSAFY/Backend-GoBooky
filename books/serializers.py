from rest_framework import serializers
from .models import Book


class BookListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Book
        fields = (
            "id",
            "title",
            "cover",
            "author",
            "publisher",
            "pub_date",
            'subTitle',
        )

class BookDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Book
        fields = "__all__"