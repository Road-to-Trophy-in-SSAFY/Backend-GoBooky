import datetime
from django.db import models
from django.conf import settings


# Create your models here.
class Category(models.Model):
    name = models.CharField(max_length=50)

    def __str__(self):
        return self.name


class Book(models.Model):
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="books"
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    isbn = models.CharField(max_length=20)
    cover = models.URLField()
    publisher = models.CharField(max_length=100)
    pub_date = models.DateField()
    author = models.CharField(max_length=100)
    author_info = models.TextField()
    author_photo = models.URLField()
    customer_review_rank = models.FloatField()
    subTitle = models.CharField(max_length=100)

    def __str__(self):
        return self.title


class Thread(models.Model):
    title = models.CharField(max_length=100)
    content = models.TextField()
    reading_date = models.DateField(default=datetime.date.today)
    cover_img = models.ImageField(upload_to="thread_cover_img/", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    book = models.ForeignKey("Book", on_delete=models.CASCADE)
    # likes = models.ManyToManyField(
    #     settings.AUTH_USER_MODEL, related_name="liked_threads", blank=True
    # )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, default=1
    )

    def __str__(self):
        return self.title
