#!/usr/bin/env python3
"""
오디오북 파일과 책을 매칭하여 books.json을 업데이트하는 스크립트
파일명 형식: audiobook_{pk}_{title}.mp3
"""

import json
import os
import re
from pathlib import Path


def extract_pk_from_filename(filename):
    """
    파일명에서 책의 pk를 추출
    예: audiobook_1_소년이 온다.mp3 -> 1
    """
    match = re.match(r"audiobook_(\d+)_.*\.mp3$", filename)
    if match:
        return int(match.group(1))
    return None


def update_books_json():
    """books.json 파일을 업데이트하여 audiobook_file 필드 추가"""

    # 경로 설정
    audio_book_dir = Path("audio_book")
    books_json_path = Path("books/fixtures/books.json")

    if not audio_book_dir.exists():
        print(f"오디오북 폴더가 존재하지 않습니다: {audio_book_dir}")
        return

    if not books_json_path.exists():
        print(f"books.json 파일이 존재하지 않습니다: {books_json_path}")
        return

    # 오디오북 파일 목록 가져오기
    audio_files = list(audio_book_dir.glob("*.mp3"))
    print(f"발견된 오디오북 파일 수: {len(audio_files)}")

    # 파일명에서 pk 추출하여 매핑 생성
    audiobook_mapping = {}
    for audio_file in audio_files:
        pk = extract_pk_from_filename(audio_file.name)
        if pk:
            # audio_book/ 경로를 포함한 상대 경로로 저장
            audiobook_mapping[pk] = f"audio_book/{audio_file.name}"
            print(f"매핑 생성: pk={pk} -> {audio_file.name}")
        else:
            print(f"pk를 추출할 수 없는 파일: {audio_file.name}")

    print(f"총 {len(audiobook_mapping)}개의 오디오북이 매핑되었습니다.")

    # books.json 파일 읽기
    try:
        with open(books_json_path, "r", encoding="utf-8") as f:
            books_data = json.load(f)
    except Exception as e:
        print(f"books.json 파일을 읽는 중 오류 발생: {e}")
        return

    # 각 책에 audiobook_file 필드 추가
    updated_count = 0
    for book in books_data:
        if book.get("model") == "books.book":
            pk = book.get("pk")
            if pk in audiobook_mapping:
                book["fields"]["audiobook_file"] = audiobook_mapping[pk]
                updated_count += 1
                print(
                    f"업데이트: pk={pk}, 제목='{book['fields']['title']}' -> {audiobook_mapping[pk]}"
                )
            else:
                # 오디오북이 없는 경우 빈 문자열로 설정
                book["fields"]["audiobook_file"] = ""

    print(f"총 {updated_count}개의 책에 오디오북이 연결되었습니다.")

    # 백업 파일 생성
    backup_path = books_json_path.with_suffix(".json.backup")
    try:
        with open(backup_path, "w", encoding="utf-8") as f:
            json.dump(books_data, f, ensure_ascii=False, indent=2)
        print(f"백업 파일 생성: {backup_path}")
    except Exception as e:
        print(f"백업 파일 생성 중 오류 발생: {e}")
        return

    # 업데이트된 books.json 파일 저장
    try:
        with open(books_json_path, "w", encoding="utf-8") as f:
            json.dump(books_data, f, ensure_ascii=False, indent=2)
        print(f"books.json 파일이 성공적으로 업데이트되었습니다.")
    except Exception as e:
        print(f"books.json 파일 저장 중 오류 발생: {e}")
        return

    # 매칭되지 않은 오디오북 파일 출력
    matched_pks = set(audiobook_mapping.keys())
    all_book_pks = {
        book["pk"] for book in books_data if book.get("model") == "books.book"
    }
    unmatched_audio_pks = matched_pks - all_book_pks
    unmatched_book_pks = all_book_pks - matched_pks

    if unmatched_audio_pks:
        print(
            f"\n매칭되지 않은 오디오북 파일들 (존재하지 않는 pk): {unmatched_audio_pks}"
        )

    if unmatched_book_pks:
        print(
            f"\n오디오북이 없는 책들의 pk: {sorted(list(unmatched_book_pks))[:10]}... (총 {len(unmatched_book_pks)}개)"
        )


if __name__ == "__main__":
    print("오디오북 파일과 책 매칭 작업을 시작합니다...")
    update_books_json()
    print("작업이 완료되었습니다.")
