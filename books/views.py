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
from django.core.cache import cache
from django.conf import settings


# Create your views here.
@api_view(["GET"])
def book_list(request):
    category_pk = request.GET.get("category")
    cache_key = f"{settings.CACHE_KEY_PREFIX}:book_list:{category_pk or 'all'}"
    cached = cache.get(cache_key)
    if cached:
        return Response(cached)
    if category_pk:
        books = Book.objects.filter(category_id=category_pk)
    else:
        books = Book.objects.all()
    serializer = BookListSerializer(books, many=True)
    cache.set(cache_key, serializer.data, settings.CACHE_TTL)
    return Response(serializer.data)


@api_view(["GET"])
def book_detail(request, book_id):
    cache_key = f"{settings.CACHE_KEY_PREFIX}:book_detail:{book_id}"
    cached = cache.get(cache_key)
    if cached:
        return Response(cached)
    book = get_object_or_404(Book, id=book_id)
    serializer = BookDetailSerializer(book)
    cache.set(cache_key, serializer.data, settings.CACHE_TTL)
    return Response(serializer.data)


@api_view(["GET"])
def thread_list(request):
    cache_key = f"{settings.CACHE_KEY_PREFIX}:thread_list"
    cached = cache.get(cache_key)
    if cached:
        return Response(cached)
    threads = Thread.objects.all().order_by("-created_at")
    serializer = ThreadListSerializer(threads, many=True, context={"request": request})
    cache.set(cache_key, serializer.data, settings.CACHE_TTL)
    return Response(serializer.data)


@api_view(["GET"])
def thread_detail(request, thread_id):
    cache_key = f"{settings.CACHE_KEY_PREFIX}:thread_detail:{thread_id}"
    cached = cache.get(cache_key)
    if cached:
        return Response(cached)
    thread = get_object_or_404(Thread, id=thread_id)
    serializer = ThreadDetailSerializer(thread, context={"request": request})
    cache.set(cache_key, serializer.data, settings.CACHE_TTL)
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
    serializer = ThreadDetailSerializer(thread, context={"request": request})
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
    serializer = ThreadDetailSerializer(thread, context={"request": request})
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

    # 좋아요 변경 후 관련 캐시 무효화
    cache_key_thread_list = f"{settings.CACHE_KEY_PREFIX}:thread_list"
    cache_key_thread_detail = f"{settings.CACHE_KEY_PREFIX}:thread_detail:{thread_id}"
    cache.delete(cache_key_thread_list)
    cache.delete(cache_key_thread_detail)
    cache_key_thread_detail = f"{settings.CACHE_KEY_PREFIX}:thread_detail:{thread_id}"
    cache.delete(cache_key_thread_list)
    cache.delete(cache_key_thread_detail)

    return Response({"liked": liked, "likes_count": thread.likes.count()})
