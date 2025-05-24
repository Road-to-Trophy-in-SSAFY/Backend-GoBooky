from django.urls import path
from . import views

urlpatterns = [
    path("", views.book_list),
    path("<int:book_id>/", views.book_detail),
    path("search/", views.search_books, name="search_books"),
    path("threads/", views.thread_list),
    path("threads/<int:thread_id>/", views.thread_detail),
    path("threads/create/", views.thread_create),
    path("threads/<int:thread_id>/update/", views.thread_update),
    path("threads/<int:thread_id>/delete/", views.thread_delete),
    path("threads/<int:thread_id>/like/", views.thread_like),
]
