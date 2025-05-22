from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.shortcuts import get_object_or_404, get_list_or_404
from .models import Book
from .serializers import BookListSerializer, BookDetailSerializer


# Create your views here.
@api_view(["GET"])
def book_list(request):
    books = get_list_or_404(Book)
    serializer = BookListSerializer(books, many=True)
    return Response(serializer.data)

@api_view(["GET"])
def book_detail(request, book_id):
    book = get_object_or_404(Book, id=book_id)
    serializer = BookDetailSerializer(book)
    return Response(serializer.data)