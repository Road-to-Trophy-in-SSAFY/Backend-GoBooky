#!/usr/bin/env python3
import os
import django

# Django 설정
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "go_booky_project.settings")
django.setup()

from books.models import Book

# 오디오북이 연결된 책 확인
books_with_audiobook = Book.objects.filter(audiobook_file__isnull=False)

print(f"오디오북이 연결된 책 수: {books_with_audiobook.count()}")
print("\n첫 5개 책 정보:")
for book in books_with_audiobook[:5]:
    print(f"- ID: {book.id}, 제목: {book.title}")
    print(f"  오디오북 파일: {book.audiobook_file}")
    print()

# 특정 책 확인 (pk=1)
try:
    book1 = Book.objects.get(pk=1)
    print(f"책 ID 1: {book1.title}")
    print(f"오디오북 파일: {book1.audiobook_file}")
except Book.DoesNotExist:
    print("ID 1인 책이 존재하지 않습니다.")
