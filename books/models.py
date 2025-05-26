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

    def __str__(self):
        return self.title


class BookEmbedding(models.Model):
    book = models.OneToOneField(
        Book, on_delete=models.CASCADE, related_name="embedding"
    )
    embedding_vector = models.JSONField(
        null=True, blank=True
    )  # 임베딩 벡터를 JSON으로 저장
    related_books = models.ManyToManyField(Book, related_name="related_to", blank=True)

    def __str__(self):
        return f"Embedding for {self.book.title}"

    def get_related_book_ids(self):
        """관련 도서의 ID 목록을 반환합니다."""
        return list(self.related_books.values_list("id", flat=True))


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
