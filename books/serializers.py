from rest_framework import serializers
from .models import Book, Category, Thread, Comment, Reply, BookEmbedding


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


class RelatedBookSerializer(serializers.ModelSerializer):
    """연관 도서를 위한 간단한 Serializer"""

    class Meta:
        model = Book
        fields = (
            "id",
            "title",
            "cover",
            "author",
        )


class BookDetailSerializer(serializers.ModelSerializer):
    related_books = serializers.SerializerMethodField()
    is_saved = serializers.SerializerMethodField()
    saved_count = serializers.SerializerMethodField()

    class Meta:
        model = Book
        fields = "__all__"

    def get_related_books(self, obj):
        """책과 연관된 도서 3권을 반환합니다."""
        try:
            # BookEmbedding 객체가 있는지 확인
            book_embedding = BookEmbedding.objects.get(book=obj)
            related_books = book_embedding.related_books.all()[:3]
            return RelatedBookSerializer(related_books, many=True).data
        except BookEmbedding.DoesNotExist:
            return []

    def get_is_saved(self, obj):
        """현재 사용자가 이 책을 저장했는지 확인"""
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return obj.saved_by_users.filter(id=request.user.id).exists()
        return False

    def get_saved_count(self, obj):
        """이 책을 저장한 사용자 수"""
        return obj.saved_by_users.count()


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
    likes_count = serializers.SerializerMethodField()
    liked = serializers.SerializerMethodField()
    cover_img_url = serializers.SerializerMethodField()

    class Meta:
        model = Thread
        fields = (
            "id",
            "title",
            "book",
            "likes_count",
            "liked",
            "cover_img",
            "cover_img_url",
        )

    def get_likes_count(self, obj):
        return obj.likes.count()

    def get_liked(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return obj.likes.filter(id=request.user.id).exists()
        return False

    def get_cover_img_url(self, obj):
        if obj.cover_img:
            request = self.context.get("request")
            if request is not None:
                return request.build_absolute_uri(obj.cover_img.url)
            return obj.cover_img.url
        return None


# 쓰레드 생성용
class ThreadCreateSerializer(serializers.ModelSerializer):
    book = serializers.PrimaryKeyRelatedField(queryset=Book.objects.all())
    likes_count = serializers.SerializerMethodField(read_only=True)
    liked = serializers.SerializerMethodField(read_only=True)

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
            "likes_count",
            "liked",
        )

    def get_likes_count(self, obj):
        return obj.likes.count()

    def get_liked(self, obj):
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            if request.user.is_authenticated:
                return obj.likes.filter(id=request.user.id).exists()
        return False


# 쓰레드 수정용
class ThreadUpdateSerializer(serializers.ModelSerializer):
    book = serializers.PrimaryKeyRelatedField(read_only=True)
    likes_count = serializers.SerializerMethodField(read_only=True)
    liked = serializers.SerializerMethodField(read_only=True)

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
            "likes_count",
            "liked",
        )

    def get_likes_count(self, obj):
        return obj.likes.count()

    def get_liked(self, obj):
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            if request.user.is_authenticated:
                return obj.likes.filter(id=request.user.id).exists()
        return False


# 단일 쓰레드
class ThreadDetailSerializer(serializers.ModelSerializer):
    book = BookTitleSerializer(read_only=True)
    user = serializers.SerializerMethodField()
    likes_count = serializers.SerializerMethodField()
    liked = serializers.SerializerMethodField()
    cover_img_url = serializers.SerializerMethodField()

    class Meta:
        model = Thread
        fields = (
            "id",
            "book",
            "user",
            "title",
            "content",
            "cover_img",
            "cover_img_url",
            "reading_date",
            "created_at",
            "updated_at",
            "likes_count",
            "liked",
        )

    def get_user(self, obj):
        return {
            "id": obj.user.id,
            "email": obj.user.email,
            "username": obj.user.username,
        }

    def get_likes_count(self, obj):
        return obj.likes.count()

    def get_liked(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return obj.likes.filter(id=request.user.id).exists()
        return False

    def get_cover_img_url(self, obj):
        if obj.cover_img:
            request = self.context.get("request")
            if request is not None:
                return request.build_absolute_uri(obj.cover_img.url)
            return obj.cover_img.url
        return None


# === 댓글/대댓글 시리얼라이저 ===


class UserProfileSerializer(serializers.Serializer):
    """사용자 프로필 정보 시리얼라이저"""

    id = serializers.IntegerField(read_only=True)
    email = serializers.EmailField(read_only=True)
    username = serializers.CharField(read_only=True)


class ReplySerializer(serializers.ModelSerializer):
    """대댓글 시리얼라이저"""

    user = UserProfileSerializer(read_only=True)
    is_author = serializers.SerializerMethodField()
    thread_id = serializers.SerializerMethodField()
    thread_title = serializers.SerializerMethodField()
    parent_comment = serializers.SerializerMethodField()

    class Meta:
        model = Reply
        fields = [
            "id",
            "content",
            "created_at",
            "updated_at",
            "user",
            "is_author",
            "thread_id",
            "thread_title",
            "parent_comment",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "user"]

    def get_is_author(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return obj.user == request.user
        return False

    def get_thread_id(self, obj):
        return obj.comment.thread.id

    def get_thread_title(self, obj):
        return obj.comment.thread.title

    def get_parent_comment(self, obj):
        return {
            "id": obj.comment.id,
            "content": obj.comment.content,
            "user": obj.comment.user.username,
        }


class CommentSerializer(serializers.ModelSerializer):
    """댓글 시리얼라이저"""

    user = UserProfileSerializer(read_only=True)
    replies = ReplySerializer(many=True, read_only=True)
    replies_count = serializers.SerializerMethodField()
    is_author = serializers.SerializerMethodField()
    thread_id = serializers.SerializerMethodField()
    thread_title = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            "id",
            "content",
            "created_at",
            "updated_at",
            "user",
            "replies",
            "replies_count",
            "is_author",
            "thread_id",
            "thread_title",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "user"]

    def get_replies_count(self, obj):
        return obj.replies.filter(is_deleted=False).count()

    def get_is_author(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return obj.user == request.user
        return False

    def get_thread_id(self, obj):
        return obj.thread.id

    def get_thread_title(self, obj):
        return obj.thread.title


class CommentCreateSerializer(serializers.ModelSerializer):
    """댓글 생성 시리얼라이저"""

    class Meta:
        model = Comment
        fields = ["content"]

    def validate_content(self, value):
        if not value or len(value.strip()) < 1:
            raise serializers.ValidationError(
                {"content": "댓글 내용을 입력해주세요.", "code": "required"}
            )

        if len(value) > 1000:
            raise serializers.ValidationError(
                {
                    "content": f"댓글은 1000자 이내로 작성해주세요. (현재: {len(value)}자)",
                    "code": "max_length",
                    "current_length": len(value),
                    "max_length": 1000,
                }
            )

        # 연속된 공백 체크
        if len(value.strip()) < 3:
            raise serializers.ValidationError(
                {"content": "댓글은 최소 3자 이상 입력해주세요.", "code": "min_length"}
            )

        # 스팸 방지: 동일 문자 반복 체크
        if len(set(value.strip())) < 2:
            raise serializers.ValidationError(
                {"content": "의미 있는 댓글을 작성해주세요.", "code": "invalid_content"}
            )

        return value.strip()


class ReplyCreateSerializer(serializers.ModelSerializer):
    """대댓글 생성 시리얼라이저"""

    class Meta:
        model = Reply
        fields = ["content"]

    def validate_content(self, value):
        if not value or len(value.strip()) < 1:
            raise serializers.ValidationError(
                {"content": "답글 내용을 입력해주세요.", "code": "required"}
            )

        if len(value) > 500:
            raise serializers.ValidationError(
                {
                    "content": f"답글은 500자 이내로 작성해주세요. (현재: {len(value)}자)",
                    "code": "max_length",
                    "current_length": len(value),
                    "max_length": 500,
                }
            )

        # 연속된 공백 체크
        if len(value.strip()) < 2:
            raise serializers.ValidationError(
                {"content": "답글은 최소 2자 이상 입력해주세요.", "code": "min_length"}
            )

        return value.strip()
