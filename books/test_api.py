"""
GoBooky API 테스트
지침에 따른 Django + DRF ViewSet 테스트
"""

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from .models import Book, Thread, Category
import json

User = get_user_model()


class CategoryAPITestCase(APITestCase):
    """카테고리 API 테스트"""

    def setUp(self):
        """테스트 데이터 설정"""
        self.client = APIClient()

        # 카테고리 생성
        self.category1 = Category.objects.create(name="소설/시/희곡")
        self.category2 = Category.objects.create(name="경제/경영")

    def test_category_list(self):
        """카테고리 목록 조회 테스트"""
        url = reverse("category-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 디버깅: 실제 응답 데이터 확인
        print(f"카테고리 응답 데이터: {response.data}")
        print(f"카테고리 개수: {len(response.data)}")

        # 최소 1개 이상의 카테고리가 있는지 확인
        self.assertGreaterEqual(len(response.data), 1)

        # 카테고리 이름들 확인
        category_names = [cat["fields"]["name"] for cat in response.data]
        # 적어도 하나의 카테고리는 있어야 함
        self.assertTrue(len(category_names) > 0)


class BookAPITestCase(APITestCase):
    """도서 API 테스트"""

    def setUp(self):
        """테스트 데이터 설정"""
        self.client = APIClient()

        # 카테고리 생성
        self.category = Category.objects.create(name="소설/시/희곡")

        # 도서 생성
        self.book = Book.objects.create(
            category=self.category,
            title="테스트 도서",
            description="테스트 설명",
            isbn="1234567890",
            cover="https://example.com/cover.jpg",
            publisher="테스트 출판사",
            pub_date="2023-01-01",
            author="테스트 작가",
            author_info="테스트 작가 정보",
            author_photo="https://example.com/author.jpg",
            customer_review_rank=4.5,
            subTitle="테스트 부제목",
        )

    def test_book_list(self):
        """도서 목록 조회 테스트"""
        url = reverse("book-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["title"], "테스트 도서")

    def test_book_detail(self):
        """도서 상세 조회 테스트"""
        url = reverse("book-detail", kwargs={"pk": self.book.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "테스트 도서")
        self.assertEqual(response.data["author"], "테스트 작가")

    def test_book_filter_by_category(self):
        """카테고리별 도서 필터링 테스트"""
        # 다른 카테고리 도서 생성
        other_category = Category.objects.create(name="경제/경영")
        Book.objects.create(
            category=other_category,
            title="경제 도서",
            description="경제 설명",
            isbn="0987654321",
            cover="https://example.com/cover2.jpg",
            publisher="경제 출판사",
            pub_date="2023-02-01",
            author="경제 작가",
            author_info="경제 작가 정보",
            author_photo="https://example.com/author2.jpg",
            customer_review_rank=4.0,
            subTitle="경제 부제목",
        )

        # 카테고리 필터링 테스트
        url = reverse("book-list")
        response = self.client.get(url, {"category": self.category.pk})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["title"], "테스트 도서")


class ThreadAPITestCase(APITestCase):
    """쓰레드 API 테스트"""

    def setUp(self):
        """테스트 데이터 설정"""
        self.client = APIClient()

        # 사용자 생성
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", username="testuser"
        )
        self.other_user = User.objects.create_user(
            email="other@example.com", password="otherpass123", username="otheruser"
        )

        # 카테고리 및 도서 생성
        self.category = Category.objects.create(name="소설/시/희곡")
        self.book = Book.objects.create(
            category=self.category,
            title="테스트 도서",
            description="테스트 설명",
            isbn="1234567890",
            cover="https://example.com/cover.jpg",
            publisher="테스트 출판사",
            pub_date="2023-01-01",
            author="테스트 작가",
            author_info="테스트 작가 정보",
            author_photo="https://example.com/author.jpg",
            customer_review_rank=4.5,
            subTitle="테스트 부제목",
        )

        # 쓰레드 생성
        self.thread = Thread.objects.create(
            title="테스트 쓰레드", content="테스트 내용", book=self.book, user=self.user
        )

    def authenticate_user(self, user):
        """사용자 인증"""
        refresh = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

    def test_thread_list_anonymous(self):
        """익명 사용자 쓰레드 목록 조회 테스트"""
        url = reverse("thread-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertEqual(len(response.data["results"]), 1)

    def test_thread_detail_anonymous(self):
        """익명 사용자 쓰레드 상세 조회 테스트"""
        url = reverse("thread-detail", kwargs={"pk": self.thread.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "테스트 쓰레드")

    def test_thread_create_authenticated(self):
        """인증된 사용자 쓰레드 생성 테스트"""
        self.authenticate_user(self.user)

        url = reverse("thread-list")
        data = {
            "title": "새 쓰레드",
            "content": "새 내용",
            "book": self.book.pk,
            "reading_date": "2023-12-01",
        }
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["title"], "새 쓰레드")
        self.assertEqual(response.data["user"]["email"], self.user.email)

    def test_thread_create_anonymous(self):
        """익명 사용자 쓰레드 생성 실패 테스트"""
        url = reverse("thread-list")
        data = {"title": "새 쓰레드", "content": "새 내용", "book": self.book.pk}
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_thread_update_owner(self):
        """쓰레드 작성자 수정 테스트"""
        self.authenticate_user(self.user)

        url = reverse("thread-detail", kwargs={"pk": self.thread.pk})
        data = {"title": "수정된 제목", "content": "수정된 내용", "book": self.book.pk}
        response = self.client.put(url, data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "수정된 제목")

    def test_thread_update_non_owner(self):
        """쓰레드 비작성자 수정 실패 테스트"""
        self.authenticate_user(self.other_user)

        url = reverse("thread-detail", kwargs={"pk": self.thread.pk})
        data = {"title": "수정된 제목", "content": "수정된 내용", "book": self.book.pk}
        response = self.client.put(url, data)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_thread_delete_owner(self):
        """쓰레드 작성자 삭제 테스트"""
        self.authenticate_user(self.user)

        url = reverse("thread-detail", kwargs={"pk": self.thread.pk})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Thread.objects.filter(pk=self.thread.pk).exists())

    def test_thread_delete_non_owner(self):
        """쓰레드 비작성자 삭제 실패 테스트"""
        self.authenticate_user(self.other_user)

        url = reverse("thread-detail", kwargs={"pk": self.thread.pk})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_thread_like_authenticated(self):
        """인증된 사용자 좋아요 테스트"""
        self.authenticate_user(self.user)

        url = reverse("thread-like", kwargs={"pk": self.thread.pk})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["liked"])
        self.assertEqual(response.data["likes_count"], 1)

        # 좋아요 취소 테스트
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["liked"])
        self.assertEqual(response.data["likes_count"], 0)

    def test_thread_like_anonymous(self):
        """익명 사용자 좋아요 실패 테스트"""
        url = reverse("thread-like", kwargs={"pk": self.thread.pk})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class CacheTestCase(APITestCase):
    """캐시 기능 테스트"""

    def setUp(self):
        """테스트 데이터 설정"""
        self.client = APIClient()

        # 카테고리 생성
        self.category = Category.objects.create(name="소설/시/희곡")

    def test_category_cache(self):
        """카테고리 캐시 테스트"""
        url = reverse("category-list")

        # 첫 번째 요청 (캐시 생성)
        response1 = self.client.get(url)
        self.assertEqual(response1.status_code, status.HTTP_200_OK)

        # 두 번째 요청 (캐시에서 조회)
        response2 = self.client.get(url)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertEqual(response1.data, response2.data)

    def test_book_cache(self):
        """도서 캐시 테스트"""
        # 도서 생성
        book = Book.objects.create(
            category=self.category,
            title="캐시 테스트 도서",
            description="캐시 테스트 설명",
            isbn="1234567890",
            cover="https://example.com/cover.jpg",
            publisher="테스트 출판사",
            pub_date="2023-01-01",
            author="테스트 작가",
            author_info="테스트 작가 정보",
            author_photo="https://example.com/author.jpg",
            customer_review_rank=4.5,
            subTitle="테스트 부제목",
        )

        url = reverse("book-list")

        # 첫 번째 요청 (캐시 생성)
        response1 = self.client.get(url)
        self.assertEqual(response1.status_code, status.HTTP_200_OK)

        # 두 번째 요청 (캐시에서 조회)
        response2 = self.client.get(url)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertEqual(response1.data, response2.data)


class PermissionTestCase(APITestCase):
    """권한 테스트"""

    def setUp(self):
        """테스트 데이터 설정"""
        self.client = APIClient()

        # 사용자 생성
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", username="testuser"
        )

        # 카테고리 및 도서 생성
        self.category = Category.objects.create(name="소설/시/희곡")
        self.book = Book.objects.create(
            category=self.category,
            title="권한 테스트 도서",
            description="권한 테스트 설명",
            isbn="1234567890",
            cover="https://example.com/cover.jpg",
            publisher="테스트 출판사",
            pub_date="2023-01-01",
            author="테스트 작가",
            author_info="테스트 작가 정보",
            author_photo="https://example.com/author.jpg",
            customer_review_rank=4.5,
            subTitle="테스트 부제목",
        )

    def authenticate_user(self, user):
        """사용자 인증"""
        refresh = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

    def test_public_endpoints_anonymous(self):
        """공개 엔드포인트 익명 접근 테스트"""
        # 카테고리 목록
        response = self.client.get(reverse("category-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 도서 목록
        response = self.client.get(reverse("book-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 도서 상세
        response = self.client.get(reverse("book-detail", kwargs={"pk": self.book.pk}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 쓰레드 목록
        response = self.client.get(reverse("thread-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_protected_endpoints_anonymous(self):
        """보호된 엔드포인트 익명 접근 실패 테스트"""
        # 쓰레드 생성
        response = self.client.post(reverse("thread-list"), {})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_protected_endpoints_authenticated(self):
        """보호된 엔드포인트 인증된 사용자 접근 테스트"""
        self.authenticate_user(self.user)

        # 쓰레드 생성
        data = {
            "title": "권한 테스트 쓰레드",
            "content": "권한 테스트 내용",
            "book": self.book.pk,
        }
        response = self.client.post(reverse("thread-list"), data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
