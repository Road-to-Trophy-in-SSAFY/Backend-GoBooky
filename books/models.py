import datetime
from django.db import models
from django.conf import settings
from django.urls import reverse


# Create your models here.
class Category(models.Model):
    name = models.CharField(max_length=50)

    def __str__(self):
        return self.name


class Book(models.Model):
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="books"
    )
    title = models.CharField(max_length=255)
    description = models.TextField()
    isbn = models.CharField(max_length=20)
    cover = models.URLField()
    publisher = models.CharField(max_length=255)
    pub_date = models.DateField()
    author = models.CharField(max_length=255)
    author_info = models.TextField()
    author_photo = models.URLField()
    customer_review_rank = models.FloatField()
    subTitle = models.CharField(max_length=255)
    audiobook_file = models.CharField(
        max_length=500, blank=True, null=True, help_text="오디오북 파일 경로"
    )

    def __str__(self):
        return self.title


class BookEmbedding(models.Model):
    book = models.OneToOneField(
        Book, on_delete=models.CASCADE, related_name="embedding"
    )
    related_books = models.ManyToManyField(Book, related_name="related_to", blank=True)

    def __str__(self):
        return f"Related books for {self.book.title}"


class Thread(models.Model):
    title = models.CharField(max_length=100)
    content = models.TextField()
    reading_date = models.DateField(default=datetime.date.today)
    cover_img = models.ImageField(upload_to="thread_cover_img/", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    book = models.ForeignKey("Book", on_delete=models.CASCADE)
    likes = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="liked_threads", blank=True
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True
    )

    def __str__(self):
        return self.title

    def get_cover_img_url(self):
        if self.cover_img and hasattr(self.cover_img, "url"):
            return self.cover_img.url
        return "/media/default_images/default_thread_image.jpg"


class Comment(models.Model):
    """댓글 모델"""

    thread = models.ForeignKey(
        "Thread", on_delete=models.CASCADE, related_name="comments"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comments"
    )
    content = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)  # 소프트 삭제

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["thread", "-created_at"]),
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self):
        return f"Comment by {self.user.email} on {self.thread.title}"


class Reply(models.Model):
    """대댓글 모델"""

    comment = models.ForeignKey(
        "Comment", on_delete=models.CASCADE, related_name="replies"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="replies"
    )
    content = models.TextField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)  # 소프트 삭제

    class Meta:
        ordering = ["created_at"]  # 대댓글은 시간순 정렬
        indexes = [
            models.Index(fields=["comment", "created_at"]),
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self):
        return f"Reply by {self.user.email} to comment {self.comment.id}"
