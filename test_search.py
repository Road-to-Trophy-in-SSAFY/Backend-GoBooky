#!/usr/bin/env python3
import os
import django

# Django 설정
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "go_booky_project.settings")
django.setup()

from books.models import Book
from books.views import BookViewSet
from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser
from django.db.models import Q

print("=== 검색 기능 테스트 ===")

# 1. 직접 모델 쿼리 테스트
print("\n1. 직접 모델 쿼리 테스트:")
books = Book.objects.filter(
    Q(title__icontains="한강")
    | Q(author__icontains="한강")
    | Q(publisher__icontains="한강")
    | Q(description__icontains="한강")
)
print(f"직접 쿼리 결과: {books.count()}개")
for book in books[:3]:
    print(f"  - {book.title} by {book.author}")

# 2. ViewSet get_queryset 테스트
print("\n2. ViewSet get_queryset 테스트:")
factory = RequestFactory()
request = factory.get("/api/books/?search=한강")
request.user = AnonymousUser()

viewset = BookViewSet()
viewset.request = request

queryset = viewset.get_queryset()
print(f"ViewSet 쿼리 결과: {queryset.count()}개")
print(f"SQL 쿼리: {queryset.query}")

# 3. 전체 책 수 확인
print(f"\n3. 전체 책 수: {Book.objects.count()}개")

# 4. 한강 작가 책만 확인
hangang_books = Book.objects.filter(author__icontains="한강")
print(f"4. 한강 작가 책 수: {hangang_books.count()}개")
