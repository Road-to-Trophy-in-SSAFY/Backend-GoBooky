from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Q
import logging

logger = logging.getLogger(__name__)
from django.conf import settings
from .models import Book, Thread, Category, Comment, Reply, BookEmbedding
from .serializers import (
    BookListSerializer,
    BookDetailSerializer,
    ThreadListSerializer,
    ThreadCreateSerializer,
    ThreadUpdateSerializer,
    ThreadDetailSerializer,
    CommentSerializer,
    CommentCreateSerializer,
    ReplySerializer,
    ReplyCreateSerializer,
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

        # 검색 기능
        search_query = self.request.query_params.get("search")
        if search_query:
            logger.info(f"🔍 [BookViewSet] 검색어: {search_query}")
            queryset = queryset.filter(
                Q(title__icontains=search_query)
                | Q(author__icontains=search_query)
                | Q(publisher__icontains=search_query)
                | Q(description__icontains=search_query)
            )
            logger.info(f"🔍 [BookViewSet] 검색 결과 수: {queryset.count()}")

        # 카테고리 필터링
        category_pk = self.request.query_params.get("category")
        if category_pk and category_pk != "null":
            try:
                category_pk = int(category_pk)
                queryset = queryset.filter(category_id=category_pk)
                logger.info(
                    f"📂 [BookViewSet] 카테고리 필터링: {category_pk}, 결과 수: {queryset.count()}"
                )
            except (ValueError, TypeError):
                pass  # 잘못된 카테고리 값은 무시

        return queryset

    def list(self, request, *args, **kwargs):
        """캐시된 도서 목록 반환"""
        category_pk = request.GET.get("category", "all")
        search_query = request.GET.get("search", "")
        page = request.GET.get("page", "1")

        logger.info(
            f"📚 [BookViewSet] list 호출 - category: {category_pk}, search: {search_query}, page: {page}"
        )

        # 검색어와 카테고리를 포함한 캐시 키 생성
        cache_key = (
            f"{settings.CACHE_KEY_PREFIX}:book_list:"
            f"cat_{category_pk}:search_{search_query}:page_{page}"
        )

        # 임시로 캐시 비활성화
        # cached = cache.get(cache_key)
        # if cached:
        #     logger.info(f"📚 [CACHE HIT] Book list: {cache_key}")
        #     return Response(cached)

        response = super().list(request, *args, **kwargs)
        logger.info(f"📚 [BookViewSet] 응답 데이터: {response.data}")

        if response.status_code == 200:
            cache.set(cache_key, response.data, settings.CACHE_TTL)
            logger.info(f"📚 [CACHE SET] Book list: {cache_key}")

        return response

    def retrieve(self, request, *args, **kwargs):
        """캐시된 도서 상세 정보 반환 (연관 도서 포함)"""
        book_id = kwargs.get("pk")
        # 연관 도서 정보를 포함하는 캐시 키
        cache_key = f"{settings.CACHE_KEY_PREFIX}:book_detail_with_related:{book_id}"

        cached = cache.get(cache_key)
        if cached:
            logger.info(f"📖 [CACHE HIT] Book detail with related: {cache_key}")
            return Response(cached)

        response = super().retrieve(request, *args, **kwargs)

        if response.status_code == 200:
            cache.set(cache_key, response.data, settings.CACHE_TTL)
            logger.info(f"📖 [CACHE SET] Book detail with related: {cache_key}")

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
        """캐시된 쓰레드 목록 반환 (좋아요 상태 제외)"""
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

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def like_status(self, request):
        """사용자의 모든 쓰레드 좋아요 상태 조회 (캐싱 없음)"""
        user = request.user
        thread_ids = request.GET.get("thread_ids", "").split(",")

        if not thread_ids or thread_ids == [""]:
            return Response({})

        try:
            thread_ids = [int(tid) for tid in thread_ids if tid.strip()]
        except ValueError:
            return Response({"error": "Invalid thread IDs"}, status=400)

        # 사용자가 좋아요한 쓰레드들 조회
        liked_threads = Thread.objects.filter(
            id__in=thread_ids, likes=user
        ).values_list("id", flat=True)

        # 결과 구성
        result = {}
        for thread in Thread.objects.filter(id__in=thread_ids):
            result[str(thread.id)] = {
                "liked": thread.id in liked_threads,
                "likes_count": thread.likes.count(),
            }

        logger.info(f"✅ [ThreadList] 좋아요 상태 실시간 조회: {len(result)}개 쓰레드")
        return Response(result)

    def retrieve(self, request, *args, **kwargs):
        """캐시된 쓰레드 상세 정보 반환 (사용자별 캐시)"""
        thread_id = kwargs.get("pk")
        query_params = request.GET.urlencode()

        logger.info(
            f"🔍 [ThreadRetrieve] 쓰레드 조회 시작 - ID: {thread_id}, 사용자: {request.user.email if request.user.is_authenticated else 'anonymous'}"
        )
        logger.info(f"🔍 [ThreadRetrieve] 쿼리 파라미터: {query_params}")

        # 사용자별 캐시 키 생성 (좋아요 상태가 사용자마다 다르므로)
        user_id = request.user.id if request.user.is_authenticated else "anonymous"
        cache_key = f"{settings.CACHE_KEY_PREFIX}:thread_detail:{thread_id}:user_{user_id}:{query_params}"

        logger.info(f"🔑 [ThreadRetrieve] 캐시 키: {cache_key}")

        cached = cache.get(cache_key)
        if cached:
            logger.info(f"📄 [CACHE HIT] Thread detail: {cache_key}")
            logger.info(f"📄 [CACHE HIT] 캐시된 cover_img: {cached.get('cover_img')}")
            logger.info(
                f"📄 [CACHE HIT] 캐시된 cover_img_url: {cached.get('cover_img_url')}"
            )
            return Response(cached)

        logger.info(f"📄 [CACHE MISS] 캐시 없음, DB에서 조회 - 쓰레드 ID: {thread_id}")
        response = super().retrieve(request, *args, **kwargs)

        if response.status_code == 200:
            logger.info(f"✅ [ThreadRetrieve] DB 조회 성공 - 쓰레드 ID: {thread_id}")
            logger.info(
                f"🖼️ [ThreadRetrieve] DB에서 가져온 cover_img: {response.data.get('cover_img')}"
            )
            logger.info(
                f"🖼️ [ThreadRetrieve] DB에서 가져온 cover_img_url: {response.data.get('cover_img_url')}"
            )

            # 좋아요 상태가 포함된 데이터는 적절한 TTL 사용 (5분)
            # 너무 짧으면 이미지 생성 중에 캐시가 만료되어 문제 발생
            cache_ttl = 300 if request.user.is_authenticated else settings.CACHE_TTL
            cache.set(cache_key, response.data, cache_ttl)
            logger.info(
                f"📄 [CACHE SET] Thread detail: {cache_key} (TTL: {cache_ttl}s)"
            )
        else:
            logger.error(
                f"❌ [ThreadRetrieve] DB 조회 실패 - 쓰레드 ID: {thread_id}, 상태코드: {response.status_code}"
            )

        return response

    def create(self, request, *args, **kwargs):
        """쓰레드 생성 - 응답에 상세 정보 포함"""
        logger.info(
            f"🚀 [ThreadCreate] 쓰레드 생성 시작 - 사용자: {request.user.email}"
        )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # 작성자를 현재 사용자로 설정
        thread = serializer.save(user=request.user)
        logger.info(
            f"💾 [ThreadCreate] 쓰레드 DB 저장 완료 - ID: {thread.id}, 제목: {thread.title}"
        )

        # 관련 캐시 무효화
        self._invalidate_thread_cache()
        logger.info(f"🗑️ [ThreadCreate] 캐시 무효화 완료 - 쓰레드 ID: {thread.id}")

        logger.info(f"✅ 쓰레드 생성 완료: {thread.id} by {request.user.email}")

        # 백그라운드에서 이미지 생성 (비동기)
        import threading

        def generate_image_async():
            try:
                logger.info(
                    f"🎨 [ImageGen] 백그라운드 이미지 생성 시작 - 쓰레드 ID: {thread.id}"
                )
                logger.info(
                    f"📋 [ImageGen] 쓰레드 정보 - 제목: {thread.title}, 도서: {thread.book.title}"
                )

                # 이미지 생성 전 쓰레드 상태 로그
                logger.info(f"🔍 [ImageGen] 생성 전 cover_img 상태: {thread.cover_img}")

                image_path = create_thread_image(thread)
                logger.info(f"🖼️ [ImageGen] create_thread_image 결과: {image_path}")

                if image_path:
                    logger.info(
                        f"💾 [ImageGen] 이미지 경로를 DB에 저장 시작 - 경로: {image_path}"
                    )
                    thread.cover_img = image_path
                    thread.save()
                    logger.info(
                        f"✅ [ImageGen] DB 저장 완료 - 쓰레드 ID: {thread.id}, 이미지 경로: {thread.cover_img}"
                    )

                    # 이미지 생성 완료 후 캐시 무효화 추가
                    logger.info(
                        f"🗑️ [ImageGen] 이미지 생성 완료 후 캐시 무효화 시작 - 쓰레드 ID: {thread.id}"
                    )

                    # 강력한 캐시 무효화 방식 사용
                    try:
                        import redis
                        from django.conf import settings as django_settings

                        # Redis 연결
                        redis_client = redis.Redis.from_url(
                            django_settings.CACHES["default"]["LOCATION"]
                        )

                        # 더 포괄적인 패턴으로 키 찾기 및 삭제
                        cache_patterns = [
                            f"*thread_detail*{thread.id}*",  # 쓰레드 상세 관련 모든 캐시
                            f"*thread_list*",  # 쓰레드 목록 관련 모든 캐시
                            f"*:thread_detail:{thread.id}:*",  # 기존 패턴도 유지
                        ]

                        total_deleted = 0
                        for pattern in cache_patterns:
                            keys = redis_client.keys(pattern)
                            if keys:
                                redis_client.delete(*keys)
                                total_deleted += len(keys)
                                logger.info(
                                    f"🗑️ [ImageGen] Redis 패턴 삭제: {pattern} ({len(keys)}개 키)"
                                )
                                for key in keys:
                                    logger.info(
                                        f"🗑️ [ImageGen] 삭제된 키: {key.decode()}"
                                    )
                            else:
                                logger.info(
                                    f"🗑️ [ImageGen] Redis 패턴 매칭 없음: {pattern}"
                                )

                        logger.info(
                            f"🗑️ [ImageGen] 총 {total_deleted}개 캐시 키 삭제 완료"
                        )

                    except Exception as redis_error:
                        logger.warning(
                            f"⚠️ [ImageGen] Redis 캐시 무효화 실패, 기본 캐시 사용: {redis_error}"
                        )
                        # 기본 Django 캐시 무효화 (fallback)
                        cache.delete(
                            f"{settings.CACHE_KEY_PREFIX}:thread_detail:{thread.id}"
                        )
                        cache.delete(f"{settings.CACHE_KEY_PREFIX}:thread_list")

                    # 기본 캐시 무효화도 실행
                    self._invalidate_thread_cache(thread.id)
                    logger.info(
                        f"🗑️ [ImageGen] 캐시 무효화 완료 - 쓰레드 ID: {thread.id}"
                    )

                    logger.info(
                        f"✅ [ImageGen] 백그라운드 이미지 생성 완료: {thread.id}"
                    )
                else:
                    logger.warning(
                        f"⚠️ [ImageGen] 이미지 생성 실패 - create_thread_image가 None 반환: {thread.id}"
                    )

            except Exception as e:
                logger.error(
                    f"❌ [ImageGen] 백그라운드 이미지 생성 실패: {thread.id}, 에러: {str(e)}",
                    exc_info=True,
                )

        # 별도 스레드에서 이미지 생성
        logger.info(
            f"🧵 [ThreadCreate] 백그라운드 이미지 생성 스레드 시작 - 쓰레드 ID: {thread.id}"
        )
        image_thread = threading.Thread(target=generate_image_async)
        image_thread.daemon = True
        image_thread.start()
        logger.info(
            f"🧵 [ThreadCreate] 백그라운드 스레드 시작됨 - 쓰레드 ID: {thread.id}"
        )

        # 응답에는 상세 시리얼라이저 사용 (이미지 없이 먼저 응답)
        detail_serializer = ThreadDetailSerializer(thread, context={"request": request})
        logger.info(f"📤 [ThreadCreate] 응답 데이터 준비 완료 - 쓰레드 ID: {thread.id}")
        logger.info(
            f"📤 [ThreadCreate] 응답 시점 cover_img: {detail_serializer.data.get('cover_img')}"
        )
        logger.info(
            f"📤 [ThreadCreate] 응답 시점 cover_img_url: {detail_serializer.data.get('cover_img_url')}"
        )

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
        from django.core.cache import cache

        logger.info(
            f"🗑️ [CacheInvalidate] 캐시 무효화 시작 - 쓰레드 ID: {thread_id or 'all'}"
        )

        # 목록 캐시 무효화 (다시 활성화)
        cache_key_list_base = f"{settings.CACHE_KEY_PREFIX}:thread_list"
        cache.delete(cache_key_list_base)
        cache.delete(f"{cache_key_list_base}:")  # 빈 쿼리 파라미터
        logger.info(f"🗑️ [CacheInvalidate] 목록 캐시 무효화 완료")

        # 특정 쓰레드 상세 캐시 무효화 (모든 사용자)
        if thread_id:
            logger.info(f"🗑️ [CacheInvalidate] 쓰레드 {thread_id} 상세 캐시 무효화 시작")
            # Redis 패턴 매칭을 사용하여 해당 쓰레드의 모든 사용자별 캐시 삭제
            try:
                import redis
                from django.conf import settings as django_settings

                # Redis 연결
                redis_client = redis.Redis.from_url(
                    django_settings.CACHES["default"]["LOCATION"]
                )

                # 패턴으로 키 찾기
                pattern = (
                    f"{settings.CACHE_KEY_PREFIX}:thread_detail:{thread_id}:user_*"
                )
                logger.info(f"🔍 [CacheInvalidate] Redis 패턴 검색: {pattern}")
                keys = redis_client.keys(pattern)

                if keys:
                    redis_client.delete(*keys)
                    logger.info(
                        f"🗑️ [CacheInvalidate] Redis 패턴 매칭으로 쓰레드 {thread_id} 캐시 {len(keys)}개 삭제"
                    )
                    for key in keys:
                        logger.info(f"🗑️ [CacheInvalidate] 삭제된 키: {key.decode()}")
                else:
                    logger.info(
                        f"🗑️ [CacheInvalidate] 쓰레드 {thread_id} 관련 캐시 없음"
                    )

            except Exception as e:
                logger.warning(
                    f"⚠️ [CacheInvalidate] Redis 패턴 매칭 실패, 기본 캐시 삭제 사용: {e}"
                )
                # 기본 캐시 삭제 (fallback)
                cache_key_detail_base = (
                    f"{settings.CACHE_KEY_PREFIX}:thread_detail:{thread_id}"
                )
                cache.delete(cache_key_detail_base)
                cache.delete(f"{cache_key_detail_base}:")
                logger.info(
                    f"🗑️ [CacheInvalidate] 기본 캐시 삭제 완료: {cache_key_detail_base}"
                )

        logger.info(
            f"🗑️ [CacheInvalidate] 쓰레드 캐시 무효화 완료: {thread_id or 'all'}"
        )


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

    # 연관 도서 정보를 포함하는 캐시 키
    cache_key = f"{settings.CACHE_KEY_PREFIX}:book_detail_with_related:{book_id}"
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
    """
    쓰레드 좋아요/좋아요 취소
    """
    thread = get_object_or_404(Thread, id=thread_id)

    if thread.likes.filter(id=request.user.id).exists():
        # 좋아요 취소
        thread.likes.remove(request.user)
        liked = False
        message = "좋아요를 취소했습니다."
    else:
        # 좋아요 추가
        thread.likes.add(request.user)
        liked = True
        message = "좋아요를 추가했습니다."

    # 관련 캐시 무효화
    cache_patterns = [
        f"{settings.CACHE_KEY_PREFIX}:thread_list:*",
        f"{settings.CACHE_KEY_PREFIX}:thread_detail:{thread_id}:*",
    ]

    for pattern in cache_patterns:
        cache.delete_many(cache.get_many(pattern))

    return Response(
        {
            "message": message,
            "liked": liked,
            "likes_count": thread.likes.count(),
        },
        status=status.HTTP_200_OK,
    )


# === 댓글/대댓글 ViewSet ===


class CommentViewSet(viewsets.ModelViewSet):
    """
    댓글 ViewSet
    - Thread별 댓글 CRUD
    - 페이지네이션 지원
    - 캐시 최적화
    """

    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        thread_id = self.kwargs.get("thread_pk")
        return (
            Comment.objects.filter(thread_id=thread_id, is_deleted=False)
            .select_related("user")
            .prefetch_related("replies__user")
        )

    def get_serializer_class(self):
        if self.action == "create":
            return CommentCreateSerializer
        return CommentSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            permission_classes = [AllowAny]
        elif self.action in ["create", "reply"]:
            permission_classes = [IsAuthenticated]
        else:  # update, partial_update, destroy
            permission_classes = [IsAuthenticated, IsAuthorOrReadOnly]

        return [permission() for permission in permission_classes]

    def list(self, request, thread_pk=None):
        """댓글 목록 조회 (페이지네이션)"""
        thread = get_object_or_404(Thread, pk=thread_pk)

        # 캐시 키 생성
        page = request.GET.get("page", 1)
        cache_key = f"comments:thread:{thread_pk}:page:{page}"

        cached_data = cache.get(cache_key)
        if cached_data:
            return Response(cached_data)

        queryset = self.get_queryset()

        # 페이지네이션
        paginator = Paginator(queryset, 10)  # 페이지당 10개
        page_obj = paginator.get_page(page)

        serializer = self.get_serializer(page_obj, many=True)

        response_data = {
            "results": serializer.data,
            "pagination": {
                "page": page_obj.number,
                "total_pages": paginator.num_pages,
                "total_count": paginator.count,
                "has_next": page_obj.has_next(),
                "has_previous": page_obj.has_previous(),
            },
        }

        # 캐시 저장 (5분)
        cache.set(cache_key, response_data, 300)

        return Response(response_data)

    def create(self, request, thread_pk=None):
        """댓글 생성"""
        thread = get_object_or_404(Thread, pk=thread_pk)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        comment = serializer.save(user=request.user, thread=thread)

        # 캐시 무효화
        self._invalidate_comment_cache(thread_pk)

        # 응답용 시리얼라이저
        response_serializer = CommentSerializer(comment, context={"request": request})

        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, pk=None, thread_pk=None):
        """댓글 수정"""
        comment = self.get_object()

        serializer = CommentCreateSerializer(comment, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # 캐시 무효화
        self._invalidate_comment_cache(thread_pk)

        # 응답용 시리얼라이저
        response_serializer = CommentSerializer(comment, context={"request": request})

        return Response(response_serializer.data)

    def destroy(self, request, pk=None, thread_pk=None):
        """댓글 소프트 삭제"""
        comment = self.get_object()
        comment.is_deleted = True
        comment.save()

        # 캐시 무효화
        self._invalidate_comment_cache(thread_pk)

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def reply(self, request, pk=None, thread_pk=None):
        """대댓글 생성"""
        comment = self.get_object()

        serializer = ReplyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        reply = serializer.save(user=request.user, comment=comment)

        # 캐시 무효화
        self._invalidate_comment_cache(thread_pk)

        # 응답용 시리얼라이저
        response_serializer = ReplySerializer(reply, context={"request": request})

        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    def _invalidate_comment_cache(self, thread_pk):
        """댓글 관련 캐시 무효화"""
        try:
            # Redis pattern 매칭을 활용한 효율적인 캐시 무효화
            from django_redis import get_redis_connection

            redis_conn = get_redis_connection("default")
            pattern = f"*comments:thread:{thread_pk}:page:*"
            keys = redis_conn.keys(pattern)
            if keys:
                redis_conn.delete(*keys)
                logger.info(f"🗑️ 댓글 캐시 무효화 완료: {len(keys)}개 키 삭제")
        except Exception as e:
            # Redis 연결 실패 시 fallback
            logger.warning(f"⚠️ Redis pattern 삭제 실패, fallback 사용: {e}")
            for page in range(1, 20):  # 축소된 범위
                cache_key = f"comments:thread:{thread_pk}:page:{page}"
                cache.delete(cache_key)


class ReplyViewSet(viewsets.ModelViewSet):
    """
    대댓글 ViewSet
    - 댓글별 대댓글 CRUD
    """

    serializer_class = ReplySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        comment_id = self.kwargs.get("comment_pk")
        return Reply.objects.filter(comment_id=comment_id).select_related(
            "user", "comment", "comment__thread"
        )

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return ReplyCreateSerializer
        return ReplySerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            permission_classes = [AllowAny]
        elif self.action == "create":
            permission_classes = [IsAuthenticated]
        else:  # update, partial_update, destroy
            permission_classes = [IsAuthenticated, IsAuthorOrReadOnly]

        return [permission() for permission in permission_classes]

    def perform_update(self, serializer):
        """대댓글 수정 수행"""
        reply = serializer.save()

        # 댓글 캐시 무효화
        thread_pk = reply.comment.thread.pk
        self._invalidate_comment_cache(thread_pk)

    def perform_destroy(self, instance):
        """대댓글 소프트 삭제 수행"""
        thread_pk = instance.comment.thread.pk

        instance.is_deleted = True
        instance.save()

        # 댓글 캐시 무효화
        self._invalidate_comment_cache(thread_pk)

    def _invalidate_comment_cache(self, thread_pk):
        """댓글 관련 캐시 무효화"""
        try:
            # Redis pattern 매칭을 활용한 효율적인 캐시 무효화
            from django_redis import get_redis_connection

            redis_conn = get_redis_connection("default")
            pattern = f"*comments:thread:{thread_pk}:page:*"
            keys = redis_conn.keys(pattern)
            if keys:
                redis_conn.delete(*keys)
                logger.info(f"🗑️ 대댓글 캐시 무효화 완료: {len(keys)}개 키 삭제")
        except Exception as e:
            # Redis 연결 실패 시 fallback
            logger.warning(f"⚠️ Redis pattern 삭제 실패, fallback 사용: {e}")
            for page in range(1, 20):  # 축소된 범위
                cache_key = f"comments:thread:{thread_pk}:page:{page}"
                cache.delete(cache_key)


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


@api_view(["GET"])
@permission_classes([AllowAny])
def random_books(request):
    """랜덤 도서 10권 조회 API"""
    try:
        count = int(request.GET.get("count", 10))
        count = min(count, 50)  # 최대 50권으로 제한
    except (ValueError, TypeError):
        count = 10

    # 캐시 키 생성
    cache_key = f"{settings.CACHE_KEY_PREFIX}:random_books:{count}"
    cached = cache.get(cache_key)
    if cached:
        return Response(cached)

    # 랜덤하게 도서 선택
    books = Book.objects.order_by("?")[:count]

    serializer = BookListSerializer(books, many=True)

    # 결과 캐싱 (5분)
    cache.set(cache_key, serializer.data, 300)

    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([AllowAny])
def popular_threads(request):
    """좋아요 순으로 쓰레드 조회 API"""
    try:
        count = int(request.GET.get("count", 3))
        count = min(count, 20)  # 최대 20개로 제한
    except (ValueError, TypeError):
        count = 3

    # 캐시 키 생성
    cache_key = f"{settings.CACHE_KEY_PREFIX}:popular_threads:{count}"
    cached = cache.get(cache_key)
    if cached:
        return Response(cached)

    # 좋아요 수가 많은 순으로 정렬, 같으면 제목 가나다순
    from django.db.models import Count

    threads = Thread.objects.annotate(likes_count=Count("likes")).order_by(
        "-likes_count", "title"
    )[:count]

    # 쓰레드 제목과 책 제목만 반환
    result = []
    for thread in threads:
        result.append(
            {
                "id": thread.id,
                "title": thread.title,
                "book_title": thread.book.title,
                "likes_count": thread.likes.count(),
            }
        )

    # 결과 캐싱 (10분)
    cache.set(cache_key, result, 600)

    return Response(result)
