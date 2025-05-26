from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from django.core.cache import cache
from django.conf import settings
from .models import Book, Thread, Category
from .serializers import (
    BookListSerializer,
    BookDetailSerializer,
    ThreadListSerializer,
    ThreadCreateSerializer,
    ThreadUpdateSerializer,
    ThreadDetailSerializer,
)
from .utils import create_thread_image
from accounts.permissions import IsAuthorOrReadOnly
import logging

logger = logging.getLogger(__name__)


class BookViewSet(viewsets.ReadOnlyModelViewSet):
    """
    지침에 따른 Book ViewSet
    - 읽기 전용 (목록, 상세)
    - 캐시 최적화
    - 카테고리 필터링
    """

    queryset = Book.objects.all()
    permission_classes = [AllowAny]

    def get_serializer_class(self):
        if self.action == "list":
            return BookListSerializer
        return BookDetailSerializer

    def get_queryset(self):
        queryset = Book.objects.all()
        category_pk = self.request.query_params.get("category")

        if category_pk:
            queryset = queryset.filter(category_id=category_pk)

        return queryset

    def list(self, request, *args, **kwargs):
        """캐시된 도서 목록 반환"""
        category_pk = request.GET.get("category")
        cache_key = f"{settings.CACHE_KEY_PREFIX}:book_list:{category_pk or 'all'}"

        cached = cache.get(cache_key)
        if cached:
            logger.info(f"📚 [CACHE HIT] Book list: {cache_key}")
            return Response(cached)

        response = super().list(request, *args, **kwargs)

        if response.status_code == 200:
            cache.set(cache_key, response.data, settings.CACHE_TTL)
            logger.info(f"📚 [CACHE SET] Book list: {cache_key}")

        return response

    def retrieve(self, request, *args, **kwargs):
        """캐시된 도서 상세 정보 반환"""
        book_id = kwargs.get("pk")
        cache_key = f"{settings.CACHE_KEY_PREFIX}:book_detail:{book_id}"

        cached = cache.get(cache_key)
        if cached:
            logger.info(f"📖 [CACHE HIT] Book detail: {cache_key}")
            return Response(cached)

        response = super().retrieve(request, *args, **kwargs)

        if response.status_code == 200:
            cache.set(cache_key, response.data, settings.CACHE_TTL)
            logger.info(f"📖 [CACHE SET] Book detail: {cache_key}")

        return response


class ThreadViewSet(viewsets.ModelViewSet):
    """
    지침에 따른 Thread ViewSet
    - CRUD 전체 지원
    - 권한 기반 접근 제어
    - 캐시 최적화
    - 좋아요 기능
    """

    queryset = Thread.objects.all().order_by("-created_at")
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == "list":
            return ThreadListSerializer
        elif self.action == "create":
            return ThreadCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return ThreadUpdateSerializer
        return ThreadDetailSerializer

    def get_permissions(self):
        """액션별 권한 설정"""
        if self.action == "list":
            # 목록 조회는 모든 사용자 허용
            permission_classes = [AllowAny]
        elif self.action == "retrieve":
            # 상세 조회는 모든 사용자 허용
            permission_classes = [AllowAny]
        elif self.action == "create":
            # 생성은 인증된 사용자만
            permission_classes = [IsAuthenticated]
        elif self.action in ["update", "partial_update", "destroy"]:
            # 수정/삭제는 작성자만
            permission_classes = [IsAuthenticated, IsAuthorOrReadOnly]
        elif self.action == "like":
            # 좋아요는 인증된 사용자만
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [IsAuthenticated]

        return [permission() for permission in permission_classes]

    def list(self, request, *args, **kwargs):
        """캐시된 쓰레드 목록 반환"""
        query_params = request.GET.urlencode()
        cache_key = f"{settings.CACHE_KEY_PREFIX}:thread_list:{query_params}"

        cached = cache.get(cache_key)
        if cached:
            logger.info(f"🧵 [CACHE HIT] Thread list: {cache_key}")
            return Response(cached)

        response = super().list(request, *args, **kwargs)

        if response.status_code == 200:
            cache.set(cache_key, response.data, settings.CACHE_TTL)
            logger.info(f"🧵 [CACHE SET] Thread list: {cache_key}")

        return response

    def retrieve(self, request, *args, **kwargs):
        """캐시된 쓰레드 상세 정보 반환"""
        thread_id = kwargs.get("pk")
        query_params = request.GET.urlencode()
        cache_key = (
            f"{settings.CACHE_KEY_PREFIX}:thread_detail:{thread_id}:{query_params}"
        )

        cached = cache.get(cache_key)
        if cached:
            logger.info(f"📄 [CACHE HIT] Thread detail: {cache_key}")
            return Response(cached)

        response = super().retrieve(request, *args, **kwargs)

        if response.status_code == 200:
            cache.set(cache_key, response.data, settings.CACHE_TTL)
            logger.info(f"📄 [CACHE SET] Thread detail: {cache_key}")

        return response

    def create(self, request, *args, **kwargs):
        """쓰레드 생성 - 응답에 상세 정보 포함"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # 작성자를 현재 사용자로 설정
        thread = serializer.save(user=request.user)

        # 관련 캐시 무효화
        self._invalidate_thread_cache()

        logger.info(f"✅ 쓰레드 생성 완료: {thread.id} by {request.user.email}")

        # 백그라운드에서 이미지 생성 (비동기)
        import threading

        def generate_image_async():
            try:
                logger.info(f"🎨 백그라운드 이미지 생성 시작: {thread.id}")
                image_path = create_thread_image(thread)
                if image_path:
                    thread.cover_img = image_path
                    thread.save()
                    logger.info(f"✅ 백그라운드 이미지 생성 완료: {thread.id}")
                    # 이미지 생성 후 캐시 무효화
                    self._invalidate_thread_cache(thread.id)
            except Exception as e:
                logger.error(f"❌ 백그라운드 이미지 생성 실패: {thread.id}, {str(e)}")

        # 별도 스레드에서 이미지 생성
        image_thread = threading.Thread(target=generate_image_async)
        image_thread.daemon = True
        image_thread.start()

        # 응답에는 상세 시리얼라이저 사용 (이미지 없이 먼저 응답)
        detail_serializer = ThreadDetailSerializer(thread, context={"request": request})
        headers = self.get_success_headers(detail_serializer.data)
        return Response(
            detail_serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )

    def perform_update(self, serializer):
        """쓰레드 수정 시 캐시 무효화"""
        thread = serializer.save()

        # 관련 캐시 무효화
        self._invalidate_thread_cache(thread.id)

        logger.info(f"✅ 쓰레드 수정 완료: {thread.id} by {self.request.user.email}")

    def perform_destroy(self, instance):
        """쓰레드 삭제 시 캐시 무효화"""
        thread_id = instance.id

        # 관련 캐시 무효화
        self._invalidate_thread_cache(thread_id)

        super().perform_destroy(instance)

        logger.info(f"✅ 쓰레드 삭제 완료: {thread_id} by {self.request.user.email}")

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def like(self, request, pk=None):
        """
        쓰레드 좋아요/좋아요 취소
        지침에 따른 멱등(idempotent) 처리
        """
        thread = self.get_object()
        user = request.user

        if thread.likes.filter(id=user.id).exists():
            thread.likes.remove(user)
            liked = False
            action = "unlike"
        else:
            thread.likes.add(user)
            liked = True
            action = "like"

        # 좋아요 변경 후 관련 캐시 무효화
        self._invalidate_thread_cache(thread.id)

        logger.info(f"✅ 쓰레드 {action}: {thread.id} by {user.email}")

        return Response(
            {"liked": liked, "likes_count": thread.likes.count(), "action": action},
            status=status.HTTP_200_OK,
        )

    def _invalidate_thread_cache(self, thread_id=None):
        """쓰레드 관련 캐시 무효화"""
        # 목록 캐시 무효화
        cache_key_list_base = f"{settings.CACHE_KEY_PREFIX}:thread_list"
        cache.delete(cache_key_list_base)
        cache.delete(f"{cache_key_list_base}:")  # 빈 쿼리 파라미터

        # 특정 쓰레드 상세 캐시 무효화
        if thread_id:
            cache_key_detail_base = (
                f"{settings.CACHE_KEY_PREFIX}:thread_detail:{thread_id}"
            )
            cache.delete(cache_key_detail_base)
            cache.delete(f"{cache_key_detail_base}:")  # 빈 쿼리 파라미터

        logger.info(f"🗑️ 쓰레드 캐시 무효화 완료: {thread_id or 'all'}")


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    카테고리 ViewSet
    - 읽기 전용 (목록만 제공)
    - 캐시 최적화
    """

    queryset = Category.objects.all()
    permission_classes = [AllowAny]

    def list(self, request, *args, **kwargs):
        """캐시된 카테고리 목록 반환"""
        cache_key = f"{settings.CACHE_KEY_PREFIX}:category_list"

        cached = cache.get(cache_key)
        if cached:
            logger.info(f"📂 [CACHE HIT] Category list: {cache_key}")
            return Response(cached)

        categories = Category.objects.all()
        data = [{"pk": cat.pk, "fields": {"name": cat.name}} for cat in categories]

        cache.set(cache_key, data, settings.CACHE_TTL)
        logger.info(f"📂 [CACHE SET] Category list: {cache_key}")

        return Response(data)


# 기존 함수 기반 뷰들 (호환성 유지용)
from rest_framework.decorators import api_view, permission_classes


@api_view(["GET"])
@permission_classes([AllowAny])
def book_list(request):
    """호환성 유지용 - ViewSet 사용 권장"""
    logger.warning("⚠️ 레거시 book_list 함수 사용됨 - ViewSet 사용 권장")

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
@permission_classes([AllowAny])
def book_detail(request, book_id):
    """호환성 유지용 - ViewSet 사용 권장"""
    logger.warning("⚠️ 레거시 book_detail 함수 사용됨 - ViewSet 사용 권장")

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
    # 쿼리 파라미터를 포함한 캐시 키 생성 (타임스탬프 포함)
    query_params = request.GET.urlencode()
    cache_key = f"{settings.CACHE_KEY_PREFIX}:thread_list:{query_params}"
    cached = cache.get(cache_key)
    if cached:
        return Response(cached)
    threads = Thread.objects.all().order_by("-created_at")
    serializer = ThreadListSerializer(threads, many=True, context={"request": request})
    cache.set(cache_key, serializer.data, settings.CACHE_TTL)
    return Response(serializer.data)


@api_view(["GET"])
def thread_detail(request, thread_id):
    # 쿼리 파라미터를 포함한 캐시 키 생성 (타임스탬프 포함)
    query_params = request.GET.urlencode()
    cache_key = f"{settings.CACHE_KEY_PREFIX}:thread_detail:{thread_id}:{query_params}"
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
    # 쓰레드 저장
    thread.save()

    try:
        # 이미지 생성 및 쓰레드에 설정
        image_path = create_thread_image(thread)
        if image_path:
            thread.cover_img = image_path
            thread.save()
    except Exception as e:
        # 이미지 생성 실패해도 쓰레드는 생성
        print(f"이미지 생성 중 오류 발생: {e}")

    # 쓰레드 목록 캐시 무효화
    cache_key_base = f"{settings.CACHE_KEY_PREFIX}:thread_list"
    cache.delete(cache_key_base)
    # 쿼리 파라미터가 있는 캐시 키도 삭제 시도
    cache.delete(f"{cache_key_base}:")  # 빈 쿼리 파라미터

    serializer = ThreadDetailSerializer(thread, context={"request": request})
    return Response(serializer.data, status=201)


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def thread_update(request, thread_id):
    thread = get_object_or_404(Thread, id=thread_id)
    # 권한 체크를 수동으로 수행 (함수 기반 뷰에서는 필요)
    if thread.user != request.user:
        return Response({"error": "자신의 쓰레드만 수정할 수 있습니다."}, status=403)
    thread.title = request.data.get("title", thread.title)
    thread.content = request.data.get("content", thread.content)
    thread.reading_date = request.data.get("reading_date", thread.reading_date)
    thread.save()

    # 쓰레드 목록 및 상세 캐시 무효화
    cache_key_list_base = f"{settings.CACHE_KEY_PREFIX}:thread_list"
    cache_key_detail_base = f"{settings.CACHE_KEY_PREFIX}:thread_detail:{thread_id}"

    # 기본 캐시 키 삭제
    cache.delete(cache_key_list_base)
    cache.delete(cache_key_detail_base)

    # 쿼리 파라미터가 있는 캐시 키도 삭제 시도
    cache.delete(f"{cache_key_list_base}:")  # 빈 쿼리 파라미터
    cache.delete(f"{cache_key_detail_base}:")  # 빈 쿼리 파라미터

    serializer = ThreadDetailSerializer(thread)
    return Response(serializer.data)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def thread_delete(request, thread_id):
    thread = get_object_or_404(Thread, id=thread_id)
    # 권한 체크를 수동으로 수행 (함수 기반 뷰에서는 필요)
    if thread.user != request.user:
        return Response({"error": "자신의 쓰레드만 삭제할 수 있습니다."}, status=403)

    # 쓰레드 목록 및 상세 캐시 무효화
    cache_key_list_base = f"{settings.CACHE_KEY_PREFIX}:thread_list"
    cache_key_detail_base = f"{settings.CACHE_KEY_PREFIX}:thread_detail:{thread_id}"

    # 기본 캐시 키 삭제
    cache.delete(cache_key_list_base)
    cache.delete(cache_key_detail_base)

    # 쿼리 파라미터가 있는 캐시 키도 삭제 시도
    cache.delete(f"{cache_key_list_base}:")  # 빈 쿼리 파라미터
    cache.delete(f"{cache_key_detail_base}:")  # 빈 쿼리 파라미터

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


@api_view(["GET"])
def search_books(request):
    """도서 검색 API"""
    query = request.GET.get("q", "")

    if not query:
        return Response([])

    # 캐시 키 생성
    cache_key = f"{settings.CACHE_KEY_PREFIX}:book_search:{query}"
    cached = cache.get(cache_key)
    if cached:
        return Response(cached)

    # 제목, 저자, 출판사, 설명에서 검색
    books = Book.objects.filter(
        Q(title__icontains=query)
        | Q(author__icontains=query)
        | Q(publisher__icontains=query)
        # | Q(description__icontains=query)
    )

    serializer = BookListSerializer(books, many=True)

    # 결과 캐싱
    cache.set(cache_key, serializer.data, settings.CACHE_TTL)

    return Response(serializer.data)
