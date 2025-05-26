# 📝 댓글/대댓글 기능 구현 가이드

## 📋 목차

1. [개요](#-개요)
2. [아키텍처 설계](#️-아키텍처-설계)
3. [백엔드 구현](#-백엔드-구현)
4. [프론트엔드 구현](#-프론트엔드-구현)
5. [API 명세](#-api-명세)
6. [데이터베이스 설계](#️-데이터베이스-설계)
7. [보안 및 권한](#-보안-및-권한)
8. [테스트 계획](#-테스트-계획)
9. [배포 체크리스트](#-배포-체크리스트)

---

## 🎯 개요

### 목표

ThreadDetail 페이지에 댓글/대댓글 CRUD 기능을 구현하여 사용자 간 상호작용을 강화합니다.

### 핵심 요구사항

- **댓글 CRUD**: 생성, 조회, 수정, 삭제
- **대댓글 CRUD**: 댓글에 대한 답글 기능
- **실시간 업데이트**: Optimistic UI 적용
- **권한 관리**: 작성자만 수정/삭제 가능
- **무한 스크롤**: 댓글 페이지네이션
- **성능 최적화**: 캐시 및 지연 로딩

### 기술 스택 준수

- **백엔드**: Django REST Framework + PostgreSQL + Redis
- **프론트엔드**: Vue 3 + Pinia + Composition API
- **인증**: Access Token (메모리) + Refresh JWT (HttpOnly Cookie)

---

## 🏗️ 아키텍처 설계

### 데이터 모델 관계

```text
Thread (1) ←→ (N) Comment (1) ←→ (N) Reply
User (1) ←→ (N) Comment
User (1) ←→ (N) Reply
```

### 컴포넌트 계층 구조

```
ThreadDetail.vue
├── CommentSection.vue
│   ├── CommentForm.vue
│   ├── CommentList.vue
│   │   └── CommentItem.vue
│   │       ├── ReplyForm.vue
│   │       └── ReplyList.vue
│   │           └── ReplyItem.vue
│   └── CommentPagination.vue
```

### 상태 관리 흐름

```
API Layer → Composable → Pinia Store → Components
```

---

## 🔧 백엔드 구현

### 1. 모델 설계

#### Comment 모델

```python
# Backend-GoBooky/books/models.py

class Comment(models.Model):
    """댓글 모델"""
    thread = models.ForeignKey(
        'Thread',
        on_delete=models.CASCADE,
        related_name='comments'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='comments'
    )
    content = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)  # 소프트 삭제

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['thread', '-created_at']),
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        return f"Comment by {self.user.email} on {self.thread.title}"

class Reply(models.Model):
    """대댓글 모델"""
    comment = models.ForeignKey(
        'Comment',
        on_delete=models.CASCADE,
        related_name='replies'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='replies'
    )
    content = models.TextField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)  # 소프트 삭제

    class Meta:
        ordering = ['created_at']  # 대댓글은 시간순 정렬
        indexes = [
            models.Index(fields=['comment', 'created_at']),
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        return f"Reply by {self.user.email} to comment {self.comment.id}"
```

### 2. 시리얼라이저 설계

```python
# Backend-GoBooky/books/serializers.py

from rest_framework import serializers
from .models import Comment, Reply
from accounts.serializers import UserProfileSerializer

class ReplySerializer(serializers.ModelSerializer):
    """대댓글 시리얼라이저"""
    user = UserProfileSerializer(read_only=True)
    is_author = serializers.SerializerMethodField()

    class Meta:
        model = Reply
        fields = [
            'id', 'content', 'created_at', 'updated_at',
            'user', 'is_author'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'user']

    def get_is_author(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.user == request.user
        return False

class CommentSerializer(serializers.ModelSerializer):
    """댓글 시리얼라이저"""
    user = UserProfileSerializer(read_only=True)
    replies = ReplySerializer(many=True, read_only=True)
    replies_count = serializers.SerializerMethodField()
    is_author = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            'id', 'content', 'created_at', 'updated_at',
            'user', 'replies', 'replies_count', 'is_author'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'user']

    def get_replies_count(self, obj):
        return obj.replies.filter(is_deleted=False).count()

    def get_is_author(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.user == request.user
        return False

class CommentCreateSerializer(serializers.ModelSerializer):
    """댓글 생성 시리얼라이저"""
    class Meta:
        model = Comment
        fields = ['content']

    def validate_content(self, value):
        if len(value.strip()) < 1:
            raise serializers.ValidationError("댓글 내용을 입력해주세요.")
        if len(value) > 1000:
            raise serializers.ValidationError("댓글은 1000자 이내로 작성해주세요.")
        return value.strip()

class ReplyCreateSerializer(serializers.ModelSerializer):
    """대댓글 생성 시리얼라이저"""
    class Meta:
        model = Reply
        fields = ['content']

    def validate_content(self, value):
        if len(value.strip()) < 1:
            raise serializers.ValidationError("답글 내용을 입력해주세요.")
        if len(value) > 500:
            raise serializers.ValidationError("답글은 500자 이내로 작성해주세요.")
        return value.strip()
```

### 3. ViewSet 설계

```python
# Backend-GoBooky/books/views.py

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from django.core.cache import cache
from django.core.paginator import Paginator
from .models import Comment, Reply, Thread
from .serializers import (
    CommentSerializer, CommentCreateSerializer,
    ReplySerializer, ReplyCreateSerializer
)
from accounts.permissions import IsAuthorOrReadOnly

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
        thread_id = self.kwargs.get('thread_pk')
        return Comment.objects.filter(
            thread_id=thread_id,
            is_deleted=False
        ).select_related('user').prefetch_related('replies__user')

    def get_serializer_class(self):
        if self.action == 'create':
            return CommentCreateSerializer
        return CommentSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [AllowAny]
        elif self.action == 'create':
            permission_classes = [IsAuthenticated]
        else:  # update, partial_update, destroy
            permission_classes = [IsAuthenticated, IsAuthorOrReadOnly]

        return [permission() for permission in permission_classes]

    def list(self, request, thread_pk=None):
        """댓글 목록 조회 (페이지네이션)"""
        thread = get_object_or_404(Thread, pk=thread_pk)

        # 캐시 키 생성
        page = request.GET.get('page', 1)
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
            'results': serializer.data,
            'pagination': {
                'page': page_obj.number,
                'total_pages': paginator.num_pages,
                'total_count': paginator.count,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous(),
            }
        }

        # 캐시 저장 (5분)
        cache.set(cache_key, response_data, 300)

        return Response(response_data)

    def create(self, request, thread_pk=None):
        """댓글 생성"""
        thread = get_object_or_404(Thread, pk=thread_pk)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        comment = serializer.save(
            user=request.user,
            thread=thread
        )

        # 캐시 무효화
        self._invalidate_comment_cache(thread_pk)

        # 응답용 시리얼라이저
        response_serializer = CommentSerializer(
            comment,
            context={'request': request}
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED
        )

    def update(self, request, pk=None, thread_pk=None):
        """댓글 수정"""
        comment = self.get_object()

        serializer = CommentCreateSerializer(
            comment,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # 캐시 무효화
        self._invalidate_comment_cache(thread_pk)

        # 응답용 시리얼라이저
        response_serializer = CommentSerializer(
            comment,
            context={'request': request}
        )

        return Response(response_serializer.data)

    def destroy(self, request, pk=None, thread_pk=None):
        """댓글 소프트 삭제"""
        comment = self.get_object()
        comment.is_deleted = True
        comment.save()

        # 캐시 무효화
        self._invalidate_comment_cache(thread_pk)

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def reply(self, request, pk=None, thread_pk=None):
        """대댓글 생성"""
        comment = self.get_object()

        serializer = ReplyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        reply = serializer.save(
            user=request.user,
            comment=comment
        )

        # 캐시 무효화
        self._invalidate_comment_cache(thread_pk)

        # 응답용 시리얼라이저
        response_serializer = ReplySerializer(
            reply,
            context={'request': request}
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED
        )

    def _invalidate_comment_cache(self, thread_pk):
        """댓글 관련 캐시 무효화"""
        # 모든 페이지 캐시 삭제
        for page in range(1, 100):  # 최대 100페이지까지
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
        comment_id = self.kwargs.get('comment_pk')
        return Reply.objects.filter(
            comment_id=comment_id,
            is_deleted=False
        ).select_related('user')

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ReplyCreateSerializer
        return ReplySerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [AllowAny]
        elif self.action == 'create':
            permission_classes = [IsAuthenticated]
        else:  # update, partial_update, destroy
            permission_classes = [IsAuthenticated, IsAuthorOrReadOnly]

        return [permission() for permission in permission_classes]

    def update(self, request, pk=None, comment_pk=None):
        """대댓글 수정"""
        reply = self.get_object()

        serializer = self.get_serializer(
            reply,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # 댓글 캐시 무효화
        thread_pk = reply.comment.thread.pk
        self._invalidate_comment_cache(thread_pk)

        # 응답용 시리얼라이저
        response_serializer = ReplySerializer(
            reply,
            context={'request': request}
        )

        return Response(response_serializer.data)

    def destroy(self, request, pk=None, comment_pk=None):
        """대댓글 소프트 삭제"""
        reply = self.get_object()
        reply.is_deleted = True
        reply.save()

        # 댓글 캐시 무효화
        thread_pk = reply.comment.thread.pk
        self._invalidate_comment_cache(thread_pk)

        return Response(status=status.HTTP_204_NO_CONTENT)

    def _invalidate_comment_cache(self, thread_pk):
        """댓글 관련 캐시 무효화"""
        for page in range(1, 100):
            cache_key = f"comments:thread:{thread_pk}:page:{page}"
            cache.delete(cache_key)
```

### 4. URL 설계

```python
# Backend-GoBooky/books/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers
from . import views

# 메인 라우터
router = DefaultRouter()
router.register(r'threads', views.ThreadViewSet)

# 중첩 라우터 - Thread > Comments
threads_router = routers.NestedDefaultRouter(
    router,
    r'threads',
    lookup='thread'
)
threads_router.register(
    r'comments',
    views.CommentViewSet,
    basename='thread-comments'
)

# 중첩 라우터 - Comment > Replies
comments_router = routers.NestedDefaultRouter(
    threads_router,
    r'comments',
    lookup='comment'
)
comments_router.register(
    r'replies',
    views.ReplyViewSet,
    basename='comment-replies'
)

urlpatterns = [
    path('api/', include(router.urls)),
    path('api/', include(threads_router.urls)),
    path('api/', include(comments_router.urls)),
]
```

---

## 🎨 프론트엔드 구현

### 1. Pinia Store 설계

```javascript
// Frontend-GoBooky/go-booky-project/src/stores/comment.js

import { ref, computed } from "vue";
import { defineStore } from "pinia";

export const useCommentStore = defineStore("comment", () => {
  // === State ===
  const comments = ref([]);
  const pagination = ref({
    page: 1,
    totalPages: 1,
    totalCount: 0,
    hasNext: false,
    hasPrevious: false,
  });
  const loading = ref(false);
  const error = ref(null);

  // === Getters ===
  const hasComments = computed(() => comments.value.length > 0);

  const getCommentById = computed(() => {
    return (id) =>
      comments.value.find((comment) => comment.id === parseInt(id));
  });

  // === Actions ===

  /**
   * 댓글 목록 설정
   */
  function setComments(commentList) {
    comments.value = commentList;
  }

  /**
   * 페이지네이션 설정
   */
  function setPagination(paginationData) {
    pagination.value = { ...pagination.value, ...paginationData };
  }

  /**
   * 댓글 추가 (목록 맨 앞에)
   */
  function addComment(comment) {
    comments.value.unshift(comment);
    pagination.value.totalCount += 1;
  }

  /**
   * 댓글 업데이트
   */
  function updateComment(commentId, updatedComment) {
    const index = comments.value.findIndex((c) => c.id === parseInt(commentId));
    if (index !== -1) {
      comments.value[index] = { ...comments.value[index], ...updatedComment };
    }
  }

  /**
   * 댓글 삭제
   */
  function removeComment(commentId) {
    const index = comments.value.findIndex((c) => c.id === parseInt(commentId));
    if (index !== -1) {
      comments.value.splice(index, 1);
      pagination.value.totalCount -= 1;
    }
  }

  /**
   * 대댓글 추가
   */
  function addReply(commentId, reply) {
    const comment = comments.value.find((c) => c.id === parseInt(commentId));
    if (comment) {
      if (!comment.replies) {
        comment.replies = [];
      }
      comment.replies.push(reply);
      comment.replies_count = (comment.replies_count || 0) + 1;
    }
  }

  /**
   * 대댓글 업데이트
   */
  function updateReply(commentId, replyId, updatedReply) {
    const comment = comments.value.find((c) => c.id === parseInt(commentId));
    if (comment && comment.replies) {
      const replyIndex = comment.replies.findIndex(
        (r) => r.id === parseInt(replyId)
      );
      if (replyIndex !== -1) {
        comment.replies[replyIndex] = {
          ...comment.replies[replyIndex],
          ...updatedReply,
        };
      }
    }
  }

  /**
   * 대댓글 삭제
   */
  function removeReply(commentId, replyId) {
    const comment = comments.value.find((c) => c.id === parseInt(commentId));
    if (comment && comment.replies) {
      const replyIndex = comment.replies.findIndex(
        (r) => r.id === parseInt(replyId)
      );
      if (replyIndex !== -1) {
        comment.replies.splice(replyIndex, 1);
        comment.replies_count = Math.max(0, (comment.replies_count || 0) - 1);
      }
    }
  }

  /**
   * 로딩 상태 설정
   */
  function setLoading(isLoading) {
    loading.value = isLoading;
  }

  /**
   * 에러 설정
   */
  function setError(errorMessage) {
    error.value = errorMessage;
  }

  /**
   * 상태 초기화
   */
  function reset() {
    comments.value = [];
    pagination.value = {
      page: 1,
      totalPages: 1,
      totalCount: 0,
      hasNext: false,
      hasPrevious: false,
    };
    loading.value = false;
    error.value = null;
  }

  return {
    // State
    comments,
    pagination,
    loading,
    error,

    // Getters
    hasComments,
    getCommentById,

    // Actions
    setComments,
    setPagination,
    addComment,
    updateComment,
    removeComment,
    addReply,
    updateReply,
    removeReply,
    setLoading,
    setError,
    reset,
  };
});
```

### 2. API 서비스

```javascript
// Frontend-GoBooky/go-booky-project/src/api/comment.js

import api from "./index";

export const commentAPI = {
  /**
   * 댓글 목록 조회
   */
  async getComments(threadId, page = 1) {
    const response = await api.get(`/threads/${threadId}/comments/`, {
      params: { page },
    });
    return response.data;
  },

  /**
   * 댓글 생성
   */
  async createComment(threadId, content) {
    const response = await api.post(`/threads/${threadId}/comments/`, {
      content,
    });
    return response.data;
  },

  /**
   * 댓글 수정
   */
  async updateComment(threadId, commentId, content) {
    const response = await api.put(
      `/threads/${threadId}/comments/${commentId}/`,
      {
        content,
      }
    );
    return response.data;
  },

  /**
   * 댓글 삭제
   */
  async deleteComment(threadId, commentId) {
    await api.delete(`/threads/${threadId}/comments/${commentId}/`);
  },

  /**
   * 대댓글 생성
   */
  async createReply(threadId, commentId, content) {
    const response = await api.post(
      `/threads/${threadId}/comments/${commentId}/reply/`,
      {
        content,
      }
    );
    return response.data;
  },

  /**
   * 대댓글 수정
   */
  async updateReply(threadId, commentId, replyId, content) {
    const response = await api.put(
      `/threads/${threadId}/comments/${commentId}/replies/${replyId}/`,
      {
        content,
      }
    );
    return response.data;
  },

  /**
   * 대댓글 삭제
   */
  async deleteReply(threadId, commentId, replyId) {
    await api.delete(
      `/threads/${threadId}/comments/${commentId}/replies/${replyId}/`
    );
  },
};
```

### 3. Composable 훅

```javascript
// Frontend-GoBooky/go-booky-project/src/composables/useComments.js

import { ref, computed } from "vue";
import { useCommentStore } from "@/stores/comment";
import { commentAPI } from "@/api/comment";
import { useAuthStore } from "@/stores/auth";

export function useComments(threadId) {
  const commentStore = useCommentStore();
  const authStore = useAuthStore();

  const isSubmitting = ref(false);
  const editingCommentId = ref(null);
  const editingReplyId = ref(null);
  const replyingToCommentId = ref(null);

  // === Computed ===
  const comments = computed(() => commentStore.comments);
  const pagination = computed(() => commentStore.pagination);
  const loading = computed(() => commentStore.loading);
  const error = computed(() => commentStore.error);
  const isAuthenticated = computed(() => authStore.isAuthed);

  // === 댓글 관련 메서드 ===

  /**
   * 댓글 목록 로드
   */
  async function loadComments(page = 1) {
    try {
      commentStore.setLoading(true);
      commentStore.setError(null);

      const data = await commentAPI.getComments(threadId, page);

      if (page === 1) {
        commentStore.setComments(data.results);
      } else {
        // 페이지네이션 - 기존 댓글에 추가
        const currentComments = commentStore.comments;
        commentStore.setComments([...currentComments, ...data.results]);
      }

      commentStore.setPagination(data.pagination);
    } catch (error) {
      console.error("댓글 로드 실패:", error);
      commentStore.setError("댓글을 불러오는데 실패했습니다.");
    } finally {
      commentStore.setLoading(false);
    }
  }

  /**
   * 댓글 생성
   */
  async function createComment(content) {
    if (!isAuthenticated.value) {
      throw new Error("로그인이 필요합니다.");
    }

    try {
      isSubmitting.value = true;

      const newComment = await commentAPI.createComment(threadId, content);

      // Optimistic UI 업데이트
      commentStore.addComment(newComment);

      return newComment;
    } catch (error) {
      console.error("댓글 생성 실패:", error);
      throw new Error("댓글 작성에 실패했습니다.");
    } finally {
      isSubmitting.value = false;
    }
  }

  /**
   * 댓글 수정
   */
  async function updateComment(commentId, content) {
    try {
      isSubmitting.value = true;

      const updatedComment = await commentAPI.updateComment(
        threadId,
        commentId,
        content
      );

      // 스토어 업데이트
      commentStore.updateComment(commentId, updatedComment);

      // 편집 모드 종료
      editingCommentId.value = null;

      return updatedComment;
    } catch (error) {
      console.error("댓글 수정 실패:", error);
      throw new Error("댓글 수정에 실패했습니다.");
    } finally {
      isSubmitting.value = false;
    }
  }

  /**
   * 댓글 삭제
   */
  async function deleteComment(commentId) {
    try {
      await commentAPI.deleteComment(threadId, commentId);

      // 스토어에서 제거
      commentStore.removeComment(commentId);
    } catch (error) {
      console.error("댓글 삭제 실패:", error);
      throw new Error("댓글 삭제에 실패했습니다.");
    }
  }

  // === 대댓글 관련 메서드 ===

  /**
   * 대댓글 생성
   */
  async function createReply(commentId, content) {
    if (!isAuthenticated.value) {
      throw new Error("로그인이 필요합니다.");
    }

    try {
      isSubmitting.value = true;

      const newReply = await commentAPI.createReply(
        threadId,
        commentId,
        content
      );

      // 스토어 업데이트
      commentStore.addReply(commentId, newReply);

      // 답글 모드 종료
      replyingToCommentId.value = null;

      return newReply;
    } catch (error) {
      console.error("답글 생성 실패:", error);
      throw new Error("답글 작성에 실패했습니다.");
    } finally {
      isSubmitting.value = false;
    }
  }

  /**
   * 대댓글 수정
   */
  async function updateReply(commentId, replyId, content) {
    try {
      isSubmitting.value = true;

      const updatedReply = await commentAPI.updateReply(
        threadId,
        commentId,
        replyId,
        content
      );

      // 스토어 업데이트
      commentStore.updateReply(commentId, replyId, updatedReply);

      // 편집 모드 종료
      editingReplyId.value = null;

      return updatedReply;
    } catch (error) {
      console.error("답글 수정 실패:", error);
      throw new Error("답글 수정에 실패했습니다.");
    } finally {
      isSubmitting.value = false;
    }
  }

  /**
   * 대댓글 삭제
   */
  async function deleteReply(commentId, replyId) {
    try {
      await commentAPI.deleteReply(threadId, commentId, replyId);

      // 스토어에서 제거
      commentStore.removeReply(commentId, replyId);
    } catch (error) {
      console.error("답글 삭제 실패:", error);
      throw new Error("답글 삭제에 실패했습니다.");
    }
  }

  // === UI 상태 관리 ===

  /**
   * 댓글 편집 모드 토글
   */
  function toggleEditComment(commentId) {
    editingCommentId.value =
      editingCommentId.value === commentId ? null : commentId;
  }

  /**
   * 답글 편집 모드 토글
   */
  function toggleEditReply(replyId) {
    editingReplyId.value = editingReplyId.value === replyId ? null : replyId;
  }

  /**
   * 답글 작성 모드 토글
   */
  function toggleReplyMode(commentId) {
    replyingToCommentId.value =
      replyingToCommentId.value === commentId ? null : commentId;
  }

  /**
   * 더 많은 댓글 로드
   */
  async function loadMoreComments() {
    if (pagination.value.hasNext && !loading.value) {
      await loadComments(pagination.value.page + 1);
    }
  }

  return {
    // State
    comments,
    pagination,
    loading,
    error,
    isSubmitting,
    editingCommentId,
    editingReplyId,
    replyingToCommentId,
    isAuthenticated,

    // Methods
    loadComments,
    createComment,
    updateComment,
    deleteComment,
    createReply,
    updateReply,
    deleteReply,
    toggleEditComment,
    toggleEditReply,
    toggleReplyMode,
    loadMoreComments,
  };
}
```

---

## 📡 API 명세

### 댓글 API

| Method | Endpoint                                                | Description    | Auth Required |
| ------ | ------------------------------------------------------- | -------------- | ------------- |
| GET    | `/api/threads/{thread_id}/comments/`                    | 댓글 목록 조회 | ❌            |
| POST   | `/api/threads/{thread_id}/comments/`                    | 댓글 생성      | ✅            |
| PUT    | `/api/threads/{thread_id}/comments/{comment_id}/`       | 댓글 수정      | ✅ (작성자)   |
| DELETE | `/api/threads/{thread_id}/comments/{comment_id}/`       | 댓글 삭제      | ✅ (작성자)   |
| POST   | `/api/threads/{thread_id}/comments/{comment_id}/reply/` | 대댓글 생성    | ✅            |

### 대댓글 API

| Method | Endpoint                                                             | Description      | Auth Required |
| ------ | -------------------------------------------------------------------- | ---------------- | ------------- |
| GET    | `/api/threads/{thread_id}/comments/{comment_id}/replies/`            | 대댓글 목록 조회 | ❌            |
| PUT    | `/api/threads/{thread_id}/comments/{comment_id}/replies/{reply_id}/` | 대댓글 수정      | ✅ (작성자)   |
| DELETE | `/api/threads/{thread_id}/comments/{comment_id}/replies/{reply_id}/` | 대댓글 삭제      | ✅ (작성자)   |

### 요청/응답 예시

#### 댓글 목록 조회

```json
// GET /api/threads/1/comments/?page=1
{
  "results": [
    {
      "id": 1,
      "content": "좋은 글이네요!",
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T10:30:00Z",
      "user": {
        "id": 1,
        "email": "user@example.com",
        "nickname": "독서왕"
      },
      "replies": [
        {
          "id": 1,
          "content": "감사합니다!",
          "created_at": "2024-01-15T11:00:00Z",
          "updated_at": "2024-01-15T11:00:00Z",
          "user": {
            "id": 2,
            "email": "author@example.com",
            "nickname": "작성자"
          },
          "is_author": false
        }
      ],
      "replies_count": 1,
      "is_author": false
    }
  ],
  "pagination": {
    "page": 1,
    "total_pages": 3,
    "total_count": 25,
    "has_next": true,
    "has_previous": false
  }
}
```

#### 댓글 생성

```json
// POST /api/threads/1/comments/
{
  "content": "정말 유익한 내용이었습니다."
}

// Response
{
  "id": 2,
  "content": "정말 유익한 내용이었습니다.",
  "created_at": "2024-01-15T12:00:00Z",
  "updated_at": "2024-01-15T12:00:00Z",
  "user": {
    "id": 3,
    "email": "reader@example.com",
    "nickname": "독서러버"
  },
  "replies": [],
  "replies_count": 0,
  "is_author": true
}
```

---

## 🗄️ 데이터베이스 설계

### 테이블 구조

#### comments 테이블

```sql
CREATE TABLE comments (
    id SERIAL PRIMARY KEY,
    thread_id INTEGER NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES auth_user(id) ON DELETE CASCADE,
    content TEXT NOT NULL CHECK (length(content) <= 1000),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_deleted BOOLEAN DEFAULT FALSE
);

-- 인덱스
CREATE INDEX idx_comments_thread_created ON comments(thread_id, created_at DESC);
CREATE INDEX idx_comments_user_created ON comments(user_id, created_at DESC);
CREATE INDEX idx_comments_is_deleted ON comments(is_deleted);
```

#### replies 테이블

```sql
CREATE TABLE replies (
    id SERIAL PRIMARY KEY,
    comment_id INTEGER NOT NULL REFERENCES comments(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES auth_user(id) ON DELETE CASCADE,
    content TEXT NOT NULL CHECK (length(content) <= 500),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_deleted BOOLEAN DEFAULT FALSE
);

-- 인덱스
CREATE INDEX idx_replies_comment_created ON replies(comment_id, created_at);
CREATE INDEX idx_replies_user_created ON replies(user_id, created_at DESC);
CREATE INDEX idx_replies_is_deleted ON replies(is_deleted);
```

### 마이그레이션 파일

```python
# Backend-GoBooky/books/migrations/0002_add_comments.py

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings

class Migration(migrations.Migration):
    dependencies = [
        ('books', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Comment',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content', models.TextField(max_length=1000)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_deleted', models.BooleanField(default=False)),
                ('thread', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comments', to='books.thread')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comments', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='Reply',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content', models.TextField(max_length=500)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_deleted', models.BooleanField(default=False)),
                ('comment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='replies', to='books.comment')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='replies', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='comment',
            index=models.Index(fields=['thread', '-created_at'], name='books_comment_thread_created_idx'),
        ),
        migrations.AddIndex(
            model_name='comment',
            index=models.Index(fields=['user', '-created_at'], name='books_comment_user_created_idx'),
        ),
        migrations.AddIndex(
            model_name='reply',
            index=models.Index(fields=['comment', 'created_at'], name='books_reply_comment_created_idx'),
        ),
        migrations.AddIndex(
            model_name='reply',
            index=models.Index(fields=['user', '-created_at'], name='books_reply_user_created_idx'),
        ),
    ]
```

---

## 🔐 보안 및 권한

### 권한 매트릭스

| 액션        | 비로그인 | 로그인 | 작성자 | 관리자 |
| ----------- | -------- | ------ | ------ | ------ |
| 댓글 조회   | ✅       | ✅     | ✅     | ✅     |
| 댓글 작성   | ❌       | ✅     | ✅     | ✅     |
| 댓글 수정   | ❌       | ❌     | ✅     | ✅     |
| 댓글 삭제   | ❌       | ❌     | ✅     | ✅     |
| 대댓글 조회 | ✅       | ✅     | ✅     | ✅     |
| 대댓글 작성 | ❌       | ✅     | ✅     | ✅     |
| 대댓글 수정 | ❌       | ❌     | ✅     | ✅     |
| 대댓글 삭제 | ❌       | ❌     | ✅     | ✅     |

### 입력 검증

#### 백엔드 검증

```python
# 댓글 내용 검증
def validate_comment_content(content):
    if not content or len(content.strip()) < 1:
        raise ValidationError("댓글 내용을 입력해주세요.")

    if len(content) > 1000:
        raise ValidationError("댓글은 1000자 이내로 작성해주세요.")

    # XSS 방지를 위한 HTML 태그 제거
    import bleach
    cleaned_content = bleach.clean(content, tags=[], strip=True)

    return cleaned_content.strip()

# 대댓글 내용 검증
def validate_reply_content(content):
    if not content or len(content.strip()) < 1:
        raise ValidationError("답글 내용을 입력해주세요.")

    if len(content) > 500:
        raise ValidationError("답글은 500자 이내로 작성해주세요.")

    import bleach
    cleaned_content = bleach.clean(content, tags=[], strip=True)

    return cleaned_content.strip()
```

#### 프론트엔드 검증

```javascript
// 댓글 입력 검증
export function validateCommentContent(content) {
  const errors = [];

  if (!content || content.trim().length === 0) {
    errors.push("댓글 내용을 입력해주세요.");
  }

  if (content.length > 1000) {
    errors.push("댓글은 1000자 이내로 작성해주세요.");
  }

  // 연속된 공백 체크
  if (/\s{10,}/.test(content)) {
    errors.push("연속된 공백은 10자 이내로 제한됩니다.");
  }

  return {
    isValid: errors.length === 0,
    errors,
  };
}

// 대댓글 입력 검증
export function validateReplyContent(content) {
  const errors = [];

  if (!content || content.trim().length === 0) {
    errors.push("답글 내용을 입력해주세요.");
  }

  if (content.length > 500) {
    errors.push("답글은 500자 이내로 작성해주세요.");
  }

  return {
    isValid: errors.length === 0,
    errors,
  };
}
```

### Rate Limiting

```python
# Backend-GoBooky/books/throttles.py

from rest_framework.throttling import UserRateThrottle

class CommentCreateThrottle(UserRateThrottle):
    """댓글 생성 제한: 분당 5개"""
    scope = 'comment_create'
    rate = '5/min'

class ReplyCreateThrottle(UserRateThrottle):
    """대댓글 생성 제한: 분당 10개"""
    scope = 'reply_create'
    rate = '10/min'

# settings.py
REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour',
        'comment_create': '5/min',
        'reply_create': '10/min',
    }
}
```

---

## 🧪 테스트 계획

### 백엔드 테스트

```python
# Backend-GoBooky/books/test_comments.py

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status
from .models import Thread, Comment, Reply, Book, Category

User = get_user_model()

class CommentAPITestCase(APITestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            email='user1@test.com',
            password='testpass123'
        )
        self.user2 = User.objects.create_user(
            email='user2@test.com',
            password='testpass123'
        )

        self.category = Category.objects.create(name='소설')
        self.book = Book.objects.create(
            title='테스트 책',
            category=self.category,
            # ... 기타 필드
        )
        self.thread = Thread.objects.create(
            title='테스트 쓰레드',
            content='테스트 내용',
            book=self.book,
            user=self.user1
        )

    def test_comment_list_anonymous(self):
        """비로그인 사용자도 댓글 목록 조회 가능"""
        url = f'/api/threads/{self.thread.id}/comments/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_comment_create_authenticated(self):
        """로그인 사용자 댓글 생성"""
        self.client.force_authenticate(user=self.user1)
        url = f'/api/threads/{self.thread.id}/comments/'
        data = {'content': '좋은 글이네요!'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Comment.objects.count(), 1)

    def test_comment_create_unauthenticated(self):
        """비로그인 사용자 댓글 생성 실패"""
        url = f'/api/threads/{self.thread.id}/comments/'
        data = {'content': '좋은 글이네요!'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_comment_update_author_only(self):
        """작성자만 댓글 수정 가능"""
        comment = Comment.objects.create(
            thread=self.thread,
            user=self.user1,
            content='원본 댓글'
        )

        # 작성자로 수정
        self.client.force_authenticate(user=self.user1)
        url = f'/api/threads/{self.thread.id}/comments/{comment.id}/'
        data = {'content': '수정된 댓글'}
        response = self.client.put(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 다른 사용자로 수정 시도
        self.client.force_authenticate(user=self.user2)
        response = self.client.put(url, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_comment_delete_author_only(self):
        """작성자만 댓글 삭제 가능"""
        comment = Comment.objects.create(
            thread=self.thread,
            user=self.user1,
            content='삭제할 댓글'
        )

        # 다른 사용자로 삭제 시도
        self.client.force_authenticate(user=self.user2)
        url = f'/api/threads/{self.thread.id}/comments/{comment.id}/'
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
            thread=self.thread,
            user=self.user1,
            content='원본 댓글'
        )

        self.client.force_authenticate(user=self.user2)
        url = f'/api/threads/{self.thread.id}/comments/{comment.id}/reply/'
        data = {'content': '답글입니다'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Reply.objects.count(), 1)

    def test_comment_content_validation(self):
        """댓글 내용 검증"""
        self.client.force_authenticate(user=self.user1)
        url = f'/api/threads/{self.thread.id}/comments/'

        # 빈 내용
        response = self.client.post(url, {'content': ''})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # 너무 긴 내용
        long_content = 'a' * 1001
        response = self.client.post(url, {'content': long_content})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_comment_pagination(self):
        """댓글 페이지네이션"""
        # 15개 댓글 생성
        for i in range(15):
            Comment.objects.create(
                thread=self.thread,
                user=self.user1,
                content=f'댓글 {i}'
            )

        url = f'/api/threads/{self.thread.id}/comments/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 10)  # 페이지당 10개
        self.assertTrue(response.data['pagination']['has_next'])

        # 2페이지 조회
        response = self.client.get(url, {'page': 2})
        self.assertEqual(len(response.data['results']), 5)  # 나머지 5개
        self.assertFalse(response.data['pagination']['has_next'])
```

### 프론트엔드 테스트

```javascript
// Frontend-GoBooky/go-booky-project/tests/unit/composables/useComments.test.js

import { describe, it, expect, beforeEach, vi } from "vitest";
import { useComments } from "@/composables/useComments";
import { createPinia, setActivePinia } from "pinia";

// API 모킹
vi.mock("@/api/comment", () => ({
  commentAPI: {
    getComments: vi.fn(),
    createComment: vi.fn(),
    updateComment: vi.fn(),
    deleteComment: vi.fn(),
    createReply: vi.fn(),
    updateReply: vi.fn(),
    deleteReply: vi.fn(),
  },
}));

describe("useComments", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it("댓글 목록을 로드할 수 있다", async () => {
    const { commentAPI } = await import("@/api/comment");
    const mockComments = {
      results: [
        {
          id: 1,
          content: "테스트 댓글",
          user: { id: 1, nickname: "사용자1" },
          replies: [],
          replies_count: 0,
        },
      ],
      pagination: {
        page: 1,
        total_pages: 1,
        total_count: 1,
        has_next: false,
        has_previous: false,
      },
    };

    commentAPI.getComments.mockResolvedValue(mockComments);

    const { loadComments, comments, pagination } = useComments(1);

    await loadComments();

    expect(comments.value).toHaveLength(1);
    expect(comments.value[0].content).toBe("테스트 댓글");
    expect(pagination.value.total_count).toBe(1);
  });

  it("댓글을 생성할 수 있다", async () => {
    const { commentAPI } = await import("@/api/comment");
    const mockComment = {
      id: 2,
      content: "새 댓글",
      user: { id: 1, nickname: "사용자1" },
      replies: [],
      replies_count: 0,
    };

    commentAPI.createComment.mockResolvedValue(mockComment);

    const { createComment, comments } = useComments(1);

    await createComment("새 댓글");

    expect(comments.value).toHaveLength(1);
    expect(comments.value[0].content).toBe("새 댓글");
  });

  it("댓글 생성 시 인증 확인", async () => {
    // 비로그인 상태 모킹
    vi.mock("@/stores/auth", () => ({
      useAuthStore: () => ({
        isAuthed: false,
      }),
    }));

    const { createComment } = useComments(1);

    await expect(createComment("새 댓글")).rejects.toThrow(
      "로그인이 필요합니다."
    );
  });
});
```

### E2E 테스트

```javascript
// Frontend-GoBooky/go-booky-project/tests/e2e/comments.spec.js

import { test, expect } from "@playwright/test";

test.describe("댓글 기능", () => {
  test.beforeEach(async ({ page }) => {
    // 로그인
    await page.goto("/login");
    await page.fill('[data-testid="email-input"]', "test@example.com");
    await page.fill('[data-testid="password-input"]', "testpass123");
    await page.click('[data-testid="login-button"]');

    // 쓰레드 상세 페이지로 이동
    await page.goto("/threads/1");
  });

  test("댓글을 작성할 수 있다", async ({ page }) => {
    // 댓글 입력
    await page.fill('[data-testid="comment-input"]', "테스트 댓글입니다.");
    await page.click('[data-testid="comment-submit"]');

    // 댓글이 표시되는지 확인
    await expect(page.locator('[data-testid="comment-item"]')).toContainText(
      "테스트 댓글입니다."
    );
  });

  test("댓글을 수정할 수 있다", async ({ page }) => {
    // 기존 댓글이 있다고 가정
    await page.click('[data-testid="comment-edit-button"]');
    await page.fill('[data-testid="comment-edit-input"]', "수정된 댓글입니다.");
    await page.click('[data-testid="comment-save-button"]');

    // 수정된 댓글이 표시되는지 확인
    await expect(page.locator('[data-testid="comment-item"]')).toContainText(
      "수정된 댓글입니다."
    );
  });

  test("댓글을 삭제할 수 있다", async ({ page }) => {
    // 삭제 확인 다이얼로그 처리
    page.on("dialog", (dialog) => dialog.accept());

    await page.click('[data-testid="comment-delete-button"]');

    // 댓글이 삭제되었는지 확인
    await expect(page.locator('[data-testid="comment-item"]')).toHaveCount(0);
  });

  test("대댓글을 작성할 수 있다", async ({ page }) => {
    // 답글 버튼 클릭
    await page.click('[data-testid="reply-button"]');

    // 답글 입력
    await page.fill('[data-testid="reply-input"]', "테스트 답글입니다.");
    await page.click('[data-testid="reply-submit"]');

    // 답글이 표시되는지 확인
    await expect(page.locator('[data-testid="reply-item"]')).toContainText(
      "테스트 답글입니다."
    );
  });

  test("무한 스크롤이 작동한다", async ({ page }) => {
    // 페이지 하단으로 스크롤
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));

    // 더 많은 댓글이 로드되는지 확인
    await expect(
      page.locator('[data-testid="comment-item"]')
    ).toHaveCountGreaterThan(10);
  });
});
```

---

## 🚀 배포 체크리스트

### 백엔드 배포 전 체크

- [ ] **마이그레이션 실행**

  ```bash
  python manage.py makemigrations books
  python manage.py migrate
  ```

- [ ] **인덱스 최적화 확인**

  ```sql
  EXPLAIN ANALYZE SELECT * FROM comments WHERE thread_id = 1 ORDER BY created_at DESC LIMIT 10;
  ```

- [ ] **캐시 설정 확인**

  ```python
  # Redis 연결 테스트
  from django.core.cache import cache
  cache.set('test', 'value', 30)
  assert cache.get('test') == 'value'
  ```

- [ ] **권한 테스트**

  ```bash
  python manage.py test books.test_comments
  ```

- [ ] **Rate Limiting 설정**
  ```python
  # settings.py에서 throttle 설정 확인
  ```

### 프론트엔드 배포 전 체크

- [ ] **빌드 테스트**

  ```bash
  npm run build
  ```

- [ ] **단위 테스트**

  ```bash
  npm run test:unit
  ```

- [ ] **E2E 테스트**

  ```bash
  npm run test:e2e
  ```

- [ ] **타입 체크** (TypeScript 사용 시)

  ```bash
  npm run type-check
  ```

- [ ] **린트 검사**

  ```bash
  npm run lint
  ```

### 성능 최적화 체크

- [ ] **데이터베이스 쿼리 최적화**

  - N+1 쿼리 문제 해결 (`select_related`, `prefetch_related`)
  - 적절한 인덱스 설정
  - 쿼리 실행 계획 분석

- [ ] **캐시 전략**

  - 댓글 목록 캐시 (5분)
  - 캐시 무효화 로직
  - Redis 메모리 사용량 모니터링

- [ ] **프론트엔드 최적화**
  - 컴포넌트 지연 로딩
  - 이미지 최적화
  - 번들 크기 분석

### 모니터링 설정

- [ ] **로그 설정**

  ```python
  # settings.py
  LOGGING = {
      'version': 1,
      'handlers': {
          'file': {
              'level': 'INFO',
              'class': 'logging.FileHandler',
              'filename': 'comments.log',
          },
      },
      'loggers': {
          'books.views': {
              'handlers': ['file'],
              'level': 'INFO',
          },
      },
  }
  ```

- [ ] **에러 추적**

  - Sentry 설정
  - 에러 알림 설정

- [ ] **성능 모니터링**
  - API 응답 시간 측정
  - 데이터베이스 쿼리 시간 모니터링

---

## 📚 참고 자료

### Django REST Framework

- [Nested Routers](https://github.com/alanjds/drf-nested-routers)
- [Permissions](https://www.django-rest-framework.org/api-guide/permissions/)
- [Throttling](https://www.django-rest-framework.org/api-guide/throttling/)

### Vue 3 & Pinia

- [Composition API](https://vuejs.org/guide/extras/composition-api-faq.html)
- [Pinia State Management](https://pinia.vuejs.org/)
- [Vue Testing Utils](https://vue-test-utils.vuejs.org/)

### PostgreSQL

- [Indexing Strategies](https://www.postgresql.org/docs/current/indexes.html)
- [Query Performance](https://www.postgresql.org/docs/current/performance-tips.html)

### 보안

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Django Security](https://docs.djangoproject.com/en/4.2/topics/security/)

---

## 🎯 다음 단계

1. **브랜치 생성**: `feature/comment-system`
2. **백엔드 모델 구현**: Comment, Reply 모델 생성
3. **백엔드 API 구현**: ViewSet, Serializer 구현
4. **프론트엔드 스토어 구현**: Pinia 스토어 생성
5. **프론트엔드 컴포넌트 구현**: UI 컴포넌트 개발
6. **테스트 작성**: 단위 테스트, E2E 테스트
7. **성능 최적화**: 캐시, 인덱스 최적화
8. **배포 및 모니터링**: 프로덕션 배포

이 문서를 기반으로 단계별로 구현을 진행하시면 됩니다! 🚀
