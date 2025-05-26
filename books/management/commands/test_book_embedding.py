import json
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
from django.core.management.base import BaseCommand
from books.models import Book, BookEmbedding
from django.db import transaction


class Command(BaseCommand):
    help = "단일 책에 대한 임베딩 생성 및 연관 도서 추출 테스트"

    def add_arguments(self, parser):
        parser.add_argument("--book_id", type=int, default=1, help="테스트할 책의 ID")
        parser.add_argument("--top_k", type=int, default=3, help="추출할 연관 도서 수")

    def handle(self, *args, **options):
        book_id = options["book_id"]
        top_k = options["top_k"]

        try:
            target_book = Book.objects.get(id=book_id)
        except Book.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"ID가 {book_id}인 책이 존재하지 않습니다.")
            )
            return

        self.stdout.write(
            f'"{target_book.title}" 책에 대한 임베딩 테스트를 시작합니다...'
        )

        # 문장 임베딩 모델 로드
        self.stdout.write("임베딩 모델을 로드합니다...")
        model = SentenceTransformer(
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        )

        # 모든 책 데이터 가져오기 (비교를 위해)
        books = Book.objects.all()
        self.stdout.write(f"총 {books.count()}권의 책 중 연관 도서를 찾습니다.")

        # 책 정보 결합 및 임베딩 생성
        book_embeddings = {}

        # 타겟 책 임베딩
        target_book_info = f"제목: {target_book.title} 저자: {target_book.author} 카테고리: {target_book.category.name} 설명: {target_book.description}"
        target_embedding = model.encode(target_book_info)
        book_embeddings[target_book.id] = target_embedding

        # 다른 모든 책 임베딩
        for book in books:
            if book.id == target_book.id:
                continue

            book_info = f"제목: {book.title} 저자: {book.author} 카테고리: {book.category.name} 설명: {book.description}"
            embedding = model.encode(book_info)
            book_embeddings[book.id] = embedding

        self.stdout.write("모든 책의 임베딩 생성 완료")

        # 코사인 유사도 계산
        self.stdout.write("코사인 유사도 계산 중...")
        similarities = {}
        target_embedding = book_embeddings[target_book.id]

        for book_id, embedding in book_embeddings.items():
            if book_id == target_book.id:
                continue

            similarity = cosine_similarity([target_embedding], [embedding])[0][0]
            similarities[book_id] = similarity

        # 상위 K개 연관 도서 추출
        top_related_books = sorted(
            similarities.items(), key=lambda x: x[1], reverse=True
        )[:top_k]

        # 결과 출력
        self.stdout.write(f'"{target_book.title}" 책의 상위 {top_k}개 연관 도서:')
        self.stdout.write("-" * 50)

        related_book_ids = []
        for i, (related_book_id, similarity) in enumerate(top_related_books, 1):
            related_book = Book.objects.get(id=related_book_id)
            related_book_ids.append(related_book_id)

            self.stdout.write(
                f"{i}. {related_book.title} (저자: {related_book.author})"
            )
            self.stdout.write(f"   카테고리: {related_book.category.name}")
            self.stdout.write(f"   유사도: {similarity:.4f}")
            self.stdout.write("-" * 50)

        # 결과를 JSON 파일로 저장 (ID만 저장하는 방식)
        result_data = {
            "book_id": target_book.id,
            "book_title": target_book.title,
            "related_book_ids": related_book_ids,
        }

        # JSON 파일로 저장
        with open("books/fixtures/test_related_book.json", "w", encoding="utf-8") as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2)

        self.stdout.write(self.style.SUCCESS("테스트 완료!"))
        self.stdout.write(
            f"테스트 결과가 books/fixtures/test_related_book.json 파일로 저장되었습니다."
        )
