from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from .models import Thread, Comment, Reply, Book, Category

User = get_user_model()


class CommentAPITestCase(APITestCase):
    def setUp(self):
        """테스트 데이터 설정"""
        self.user1 = User.objects.create_user(
            email="user1@test.com", password="testpass123"
        )
        self.user2 = User.objects.create_user(
            email="user2@test.com", password="testpass123"
        )

        self.category = Category.objects.create(name="소설")
        self.book = Book.objects.create(
            title="테스트 책",
            category=self.category,
            description="테스트 설명",
            isbn="1234567890",
            cover="http://example.com/cover.jpg",
            publisher="테스트 출판사",
            pub_date="2024-01-01",
            author="테스트 작가",
            author_info="테스트 작가 정보",
            author_photo="http://example.com/author.jpg",
            customer_review_rank=4.5,
            subTitle="테스트 부제목",
        )
        self.thread = Thread.objects.create(
            title="테스트 쓰레드",
            content="테스트 내용",
            book=self.book,
            user=self.user1,
        )

    def test_comment_list_anonymous(self):
        """비로그인 사용자도 댓글 목록 조회 가능"""
        url = f"/api/threads/{self.thread.id}/comments/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertIn("pagination", response.data)

    def test_comment_create_authenticated(self):
        """로그인 사용자 댓글 생성"""
        self.client.force_authenticate(user=self.user1)
        url = f"/api/threads/{self.thread.id}/comments/"
        data = {"content": "좋은 글이네요!"}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Comment.objects.count(), 1)
        self.assertEqual(response.data["content"], "좋은 글이네요!")
        self.assertEqual(response.data["user"]["id"], self.user1.id)

    def test_comment_create_unauthenticated(self):
        """비로그인 사용자 댓글 생성 실패"""
        url = f"/api/threads/{self.thread.id}/comments/"
        data = {"content": "좋은 글이네요!"}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_comment_update_author_only(self):
        """작성자만 댓글 수정 가능"""
        comment = Comment.objects.create(
            thread=self.thread, user=self.user1, content="원본 댓글"
        )

        # 작성자로 수정
        self.client.force_authenticate(user=self.user1)
        url = f"/api/threads/{self.thread.id}/comments/{comment.id}/"
        data = {"content": "수정된 댓글"}
        response = self.client.put(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["content"], "수정된 댓글")

        # 다른 사용자로 수정 시도
        self.client.force_authenticate(user=self.user2)
        response = self.client.put(url, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_comment_delete_author_only(self):
        """작성자만 댓글 삭제 가능"""
        comment = Comment.objects.create(
            thread=self.thread, user=self.user1, content="삭제할 댓글"
        )

        # 다른 사용자로 삭제 시도
        self.client.force_authenticate(user=self.user2)
        url = f"/api/threads/{self.thread.id}/comments/{comment.id}/"
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # 작성자로 삭제
        self.client.force_authenticate(user=self.user1)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # 소프트 삭제 확인
        comment.refresh_from_db()
        self.assertTrue(comment.is_deleted)

    def test_reply_create(self):
        """대댓글 생성"""
        comment = Comment.objects.create(
            thread=self.thread, user=self.user1, content="원본 댓글"
        )

        self.client.force_authenticate(user=self.user2)
        url = f"/api/threads/{self.thread.id}/comments/{comment.id}/reply/"
        data = {"content": "답글입니다"}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Reply.objects.count(), 1)
        self.assertEqual(response.data["content"], "답글입니다")

    def test_comment_content_validation(self):
        """댓글 내용 검증"""
        self.client.force_authenticate(user=self.user1)
        url = f"/api/threads/{self.thread.id}/comments/"

        # 빈 내용
        response = self.client.post(url, {"content": ""})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # 너무 짧은 내용
        response = self.client.post(url, {"content": "a"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # 너무 긴 내용
        long_content = "a" * 1001
        response = self.client.post(url, {"content": long_content})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # 동일 문자 반복
        response = self.client.post(url, {"content": "aaaa"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_comment_pagination(self):
        """댓글 페이지네이션"""
        # 15개 댓글 생성
        for i in range(15):
            Comment.objects.create(
                thread=self.thread, user=self.user1, content=f"댓글 {i}"
            )

        url = f"/api/threads/{self.thread.id}/comments/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 10)  # 페이지당 10개
        self.assertTrue(response.data["pagination"]["has_next"])

        # 2페이지 조회
        response = self.client.get(url, {"page": 2})
        self.assertEqual(len(response.data["results"]), 5)  # 나머지 5개
        self.assertFalse(response.data["pagination"]["has_next"])

    def test_reply_update_and_delete(self):
        """대댓글 수정 및 삭제"""
        comment = Comment.objects.create(
            thread=self.thread, user=self.user1, content="원본 댓글"
        )
        reply = Reply.objects.create(
            comment=comment, user=self.user2, content="원본 답글"
        )

        # 대댓글 수정
        self.client.force_authenticate(user=self.user2)
        url = f"/api/threads/{self.thread.id}/comments/{comment.id}/replies/{reply.id}/"
        data = {"content": "수정된 답글"}
        response = self.client.put(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["content"], "수정된 답글")

        # 대댓글 삭제
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # 소프트 삭제 확인
        reply.refresh_from_db()
        self.assertTrue(reply.is_deleted)

    def test_nested_serializer_structure(self):
        """중첩 시리얼라이저 구조 확인"""
        comment = Comment.objects.create(
            thread=self.thread, user=self.user1, content="댓글"
        )
        Reply.objects.create(comment=comment, user=self.user2, content="답글")

        url = f"/api/threads/{self.thread.id}/comments/"
        response = self.client.get(url)

        comment_data = response.data["results"][0]
        self.assertIn("replies", comment_data)
        self.assertIn("replies_count", comment_data)
        self.assertIn("is_author", comment_data)
        self.assertEqual(comment_data["replies_count"], 1)
        self.assertEqual(len(comment_data["replies"]), 1)

    def test_is_author_field(self):
        """is_author 필드 정확성 확인"""
        comment = Comment.objects.create(
            thread=self.thread, user=self.user1, content="댓글"
        )

        # 작성자로 조회
        self.client.force_authenticate(user=self.user1)
        url = f"/api/threads/{self.thread.id}/comments/"
        response = self.client.get(url)
        self.assertTrue(response.data["results"][0]["is_author"])

        # 다른 사용자로 조회
        self.client.force_authenticate(user=self.user2)
        response = self.client.get(url)
        self.assertFalse(response.data["results"][0]["is_author"])

        # 비로그인으로 조회
        self.client.force_authenticate(user=None)
        response = self.client.get(url)
        self.assertFalse(response.data["results"][0]["is_author"])


class CommentModelTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="test@test.com", password="testpass123"
        )
        self.category = Category.objects.create(name="소설")
        self.book = Book.objects.create(
            title="테스트 책",
            category=self.category,
            description="테스트 설명",
            isbn="1234567890",
            cover="http://example.com/cover.jpg",
            publisher="테스트 출판사",
            pub_date="2024-01-01",
            author="테스트 작가",
            author_info="테스트 작가 정보",
            author_photo="http://example.com/author.jpg",
            customer_review_rank=4.5,
            subTitle="테스트 부제목",
        )
        self.thread = Thread.objects.create(
            title="테스트 쓰레드", content="테스트 내용", book=self.book, user=self.user
        )

    def test_comment_str_method(self):
        """Comment 모델의 __str__ 메서드 테스트"""
        comment = Comment.objects.create(
            thread=self.thread, user=self.user, content="테스트 댓글"
        )
        expected = f"Comment by {self.user.email} on {self.thread.title}"
        self.assertEqual(str(comment), expected)

    def test_reply_str_method(self):
        """Reply 모델의 __str__ 메서드 테스트"""
        comment = Comment.objects.create(
            thread=self.thread, user=self.user, content="테스트 댓글"
        )
        reply = Reply.objects.create(
            comment=comment, user=self.user, content="테스트 답글"
        )
        expected = f"Reply by {self.user.email} to comment {comment.id}"
        self.assertEqual(str(reply), expected)

    def test_comment_ordering(self):
        """댓글 정렬 순서 테스트"""
        comment1 = Comment.objects.create(
            thread=self.thread, user=self.user, content="첫 번째 댓글"
        )
        comment2 = Comment.objects.create(
            thread=self.thread, user=self.user, content="두 번째 댓글"
        )

        comments = Comment.objects.all()
        self.assertEqual(comments[0], comment2)  # 최신순
        self.assertEqual(comments[1], comment1)

    def test_reply_ordering(self):
        """답글 정렬 순서 테스트"""
        comment = Comment.objects.create(
            thread=self.thread, user=self.user, content="댓글"
        )
        reply1 = Reply.objects.create(
            comment=comment, user=self.user, content="첫 번째 답글"
        )
        reply2 = Reply.objects.create(
            comment=comment, user=self.user, content="두 번째 답글"
        )

        replies = Reply.objects.all()
        self.assertEqual(replies[0], reply1)  # 시간순
        self.assertEqual(replies[1], reply2)
