import json
from django.core.management.base import BaseCommand
from books.models import Book, BookEmbedding
from django.db import transaction


class Command(BaseCommand):
    help = "연관 도서 데이터를 fixtures 파일에서 로드합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            default="books/fixtures/related_books.json",
            help="연관 도서 데이터가 저장된 JSON 파일 경로",
        )

    def handle(self, *args, **options):
        file_path = options["file"]
        self.stdout.write(f"{file_path}에서 연관 도서 데이터를 로드합니다...")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                related_books_data = json.load(f)
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f"파일을 찾을 수 없습니다: {file_path}"))
            return
        except json.JSONDecodeError:
            self.stdout.write(
                self.style.ERROR(f"유효하지 않은 JSON 파일입니다: {file_path}")
            )
            return

        self.stdout.write(
            f"총 {len(related_books_data)}개의 책 연관 도서 데이터를 로드합니다."
        )

        with transaction.atomic():
            # 기존 임베딩 데이터 삭제
            BookEmbedding.objects.all().delete()

            # 새로운 임베딩 및 연관 도서 데이터 저장
            for item in related_books_data:
                book_id = item["book_id"]

                try:
                    book = Book.objects.get(id=book_id)
                except Book.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(
                            f"ID가 {book_id}인 책이 존재하지 않습니다. 건너뜁니다."
                        )
                    )
                    continue

                # 임베딩 객체 생성
                embedding_obj = BookEmbedding.objects.create(
                    book=book,
                    embedding_vector=[],  # 실제 임베딩 벡터는 필요 없으므로 빈 리스트로 설정
                )

                # 연관 도서 추가 (ID만 있는 방식에 맞게 수정)
                related_book_ids = item.get("related_book_ids", [])

                # 이전 형식 지원 (하위 호환성)
                if not related_book_ids and "related_books" in item:
                    related_book_ids = [rb["id"] for rb in item["related_books"]]

                related_books = Book.objects.filter(id__in=related_book_ids)

                if related_books.count() != len(related_book_ids):
                    self.stdout.write(
                        self.style.WARNING(
                            f"책 ID {book_id}의 일부 연관 도서를 찾을 수 없습니다."
                        )
                    )

                embedding_obj.related_books.add(*related_books)

        self.stdout.write(self.style.SUCCESS("연관 도서 데이터 로드가 완료되었습니다!"))
