from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404, get_list_or_404
from .models import Book, Thread
from .serializers import (
    BookListSerializer,
    BookDetailSerializer,
    ThreadListSerializer,
    ThreadSerializer,
    ThreadDetailSerializer,
)


# Create your views here.
@api_view(["GET"])
def book_list(request):
    category_pk = request.GET.get("category")
    if category_pk:
        books = Book.objects.filter(category_id=category_pk)
    else:
        books = Book.objects.all()
    serializer = BookListSerializer(books, many=True)
    return Response(serializer.data)


@api_view(["GET"])
def book_detail(request, book_id):
    book = get_object_or_404(Book, id=book_id)
    serializer = BookDetailSerializer(book)
    return Response(serializer.data)


@api_view(["GET"])
def thread_list(request):
    threads = Thread.objects.all().order_by("-created_at")
    serializer = ThreadListSerializer(threads, many=True)
    return Response(serializer.data)


@api_view(["GET"])
def thread_detail(request, thread_id):
    thread = get_object_or_404(Thread, id=thread_id)
    serializer = ThreadDetailSerializer(thread)
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def thread_create(request):
    book_id = request.data.get("book")
    if not book_id:
        return Response({"error": "book 필드는 필수입니다."}, status=400)
    book = get_object_or_404(Book, id=book_id)
    thread = Thread(
        book=book,
        user=request.user,
        title=request.data.get("title", ""),
        content=request.data.get("content", ""),
        reading_date=request.data.get("reading_date"),
    )
    thread.save()
    serializer = ThreadDetailSerializer(thread)
    return Response(serializer.data, status=201)


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def thread_update(request, thread_id):
    thread = get_object_or_404(Thread, id=thread_id)
    if thread.user != request.user:
        return Response({"error": "자신의 쓰레드만 수정할 수 있습니다."}, status=403)
    thread.title = request.data.get("title", thread.title)
    thread.content = request.data.get("content", thread.content)
    thread.reading_date = request.data.get("reading_date", thread.reading_date)
    thread.save()
    serializer = ThreadDetailSerializer(thread)
    return Response(serializer.data)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def thread_delete(request, thread_id):
    thread = get_object_or_404(Thread, id=thread_id)
    if thread.user != request.user:
        return Response({"error": "자신의 쓰레드만 삭제할 수 있습니다."}, status=403)
    thread.delete()
    return Response({"message": "Thread deleted."}, status=204)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def thread_like(request, thread_id):
    thread = get_object_or_404(Thread, id=thread_id)
    user = request.user
    if thread.likes.filter(id=user.id).exists():
        thread.likes.remove(user)
        liked = False
    else:
        thread.likes.add(user)
        liked = True
    return Response({"liked": liked, "likes_count": thread.likes.count()})
