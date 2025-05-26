import json
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
from django.core.management.base import BaseCommand
from books.models import Book, BookEmbedding
from django.db import transaction
import time


class Command(BaseCommand):
    help = "책 설명, 제목, 저자, 카테고리를 활용해 임베딩을 생성하고 연관 도서를 추출합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch_size",
            type=int,
            default=0,
            help="한 번에 처리할 책의 수 (0이면 모든 책 처리)",
        )
        parser.add_argument(
            "--start_id", type=int, default=1, help="처리를 시작할 책 ID"
        )
        parser.add_argument(
            "--end_id",
            type=int,
            default=0,
            help="처리를 종료할 책 ID (0이면 마지막 책까지)",
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        start_id = options["start_id"]
        end_id = options["end_id"]

        self.stdout.write("책 임베딩 생성 및 연관 도서 추출을 시작합니다...")

        # 문장 임베딩 모델 로드
        start_time = time.time()
        self.stdout.write("임베딩 모델을 로드합니다...")
        model = SentenceTransformer(
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        )
        self.stdout.write(f"모델 로드 완료 ({time.time() - start_time:.2f}초)")

        # 책 데이터 필터링
        books_query = Book.objects.all()
        if start_id > 1:
            books_query = books_query.filter(id__gte=start_id)
        if end_id > 0:
            books_query = books_query.filter(id__lte=end_id)

        # 배치 처리 설정
        if batch_size > 0:
            books = books_query[:batch_size]
        else:
            books = books_query

        total_books = books.count()
        self.stdout.write(f"총 {total_books}권의 책에 대한 임베딩을 생성합니다.")

        # 각 책에 대한 임베딩 생성
        book_embeddings = {}
        start_time = time.time()
        for i, book in enumerate(books):
            # 책 정보 결합
            book_info = f"제목: {book.title} 저자: {book.author} 카테고리: {book.category.name} 설명: {book.description}"

            # 임베딩 생성
            embedding = model.encode(book_info)
            book_embeddings[book.id] = embedding

            if (i + 1) % 10 == 0 or (i + 1) == total_books:
                elapsed = time.time() - start_time
                eta = (elapsed / (i + 1)) * (total_books - (i + 1))
                self.stdout.write(
                    f"{i + 1}/{total_books} 책 임베딩 생성 완료 "
                    f"(경과: {elapsed:.2f}초, 예상 남은 시간: {eta:.2f}초)"
                )

        # 코사인 유사도 계산 및 연관 도서 추출
        self.stdout.write("코사인 유사도 계산 및 연관 도서 추출을 시작합니다...")

        # 임베딩 벡터를 numpy 배열로 변환
        book_ids = list(book_embeddings.keys())
        embeddings_array = np.array([book_embeddings[book_id] for book_id in book_ids])

        # 코사인 유사도 계산
        start_time = time.time()
        similarity_matrix = cosine_similarity(embeddings_array)
        self.stdout.write(f"코사인 유사도 계산 완료 ({time.time() - start_time:.2f}초)")

        # 연관 도서 추출 및 저장
        start_time = time.time()
        embeddings_to_save = []

        with transaction.atomic():
            # 기존 임베딩 데이터 삭제 (처리하는 책에 대해서만)
            BookEmbedding.objects.filter(book_id__in=book_ids).delete()

            # 새로운 임베딩 및 연관 도서 저장
            for i, book_id in enumerate(book_ids):
                if (i + 1) % 10 == 0 or (i + 1) == len(book_ids):
                    self.stdout.write(f"DB 저장 진행 중: {i + 1}/{len(book_ids)}")

                book = Book.objects.get(id=book_id)

                # 자기 자신을 제외한 유사도 점수
                similarities = similarity_matrix[i]
                similarities[i] = -1  # 자기 자신 제외

                # 상위 3개 연관 도서 인덱스 추출
                top_indices = np.argsort(similarities)[-3:][::-1]
                related_book_ids = [book_ids[idx] for idx in top_indices]

                # 임베딩 저장
                embedding_obj = BookEmbedding.objects.create(book=book)

                # 연관 도서 추가
                related_books = Book.objects.filter(id__in=related_book_ids)
                embedding_obj.related_books.add(*related_books)

                # Django fixture 형식으로 저장할 데이터 준비
                embeddings_to_save.append(
                    {
                        "model": "books.bookembedding",
                        "pk": embedding_obj.pk,
                        "fields": {"book": book.id, "related_books": related_book_ids},
                    }
                )

        self.stdout.write(f"DB 저장 완료 ({time.time() - start_time:.2f}초)")

        # Django fixture 형식으로 JSON 파일 저장
        start_time = time.time()

        # 파일명 결정 (배치 처리 시 구분)
        if batch_size > 0 or start_id > 1 or end_id > 0:
            file_name = f"related_books_{start_id}_to_{book_ids[-1]}.json"
        else:
            file_name = "related_books.json"

        # Django fixture 형식으로 JSON 파일 저장
        with open(f"books/fixtures/{file_name}", "w", encoding="utf-8") as f:
            json.dump(embeddings_to_save, f, ensure_ascii=False, indent=2)

        self.stdout.write(f"JSON 파일 저장 완료 ({time.time() - start_time:.2f}초)")

        self.stdout.write(
            self.style.SUCCESS("책 임베딩 생성 및 연관 도서 추출이 완료되었습니다!")
        )
        self.stdout.write(
            f"연관 도서 데이터가 books/fixtures/{file_name} 파일로 저장되었습니다."
        )
        self.stdout.write(
            f"Django fixture 형식으로 저장되어 'python manage.py loaddata {file_name.replace('.json', '')}'로 로드할 수 있습니다."
        )
