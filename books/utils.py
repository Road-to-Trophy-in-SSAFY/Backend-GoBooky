import json
import requests
import openai
from pathlib import Path
from django.conf import settings
from pydantic import BaseModel
import logging
import re

logger = logging.getLogger(__name__)


def clean_content(content):
    """HTML 태그 제거 및 텍스트 정리"""
    # HTML 태그 제거
    clean_text = re.sub(r"<[^>]+>", "", content)
    # 연속된 공백 제거
    clean_text = re.sub(r"\s+", " ", clean_text)
    # 특수 문자 제거 (기본적인 문장 부호만 유지)
    clean_text = re.sub(r"[^\w\s.,!?-]", "", clean_text)
    return clean_text.strip()


def create_thread_image(thread):
    API_KEY = settings.OPENAI_API_KEY

    logger.info(f"🎨 [ImageUtils] 이미지 생성 시작 - Thread ID: {thread.pk}")
    logger.info(
        f"📋 [ImageUtils] 쓰레드 정보 - 제목: {thread.title}, 도서: {thread.book.title}"
    )
    logger.info(f"🔑 [ImageUtils] API 키 존재 여부: {bool(API_KEY)}")

    # API 키가 없으면 None 반환
    if not API_KEY:
        logger.error("❌ [ImageUtils] OpenAI API 키가 설정되지 않았습니다.")
        return None

    try:
        # 콘텐츠 정리
        clean_text = clean_content(thread.content)

        # 더 안전하고 간단한 프롬프트 생성
        prompt_text = f"A beautiful artistic illustration inspired by reading a book. Style: watercolor painting, warm colors, peaceful atmosphere. Theme: {thread.book.title[:50]}"

        # 프롬프트 길이 제한 (DALL-E 제한사항)
        if len(prompt_text) > 1000:
            prompt_text = prompt_text[:1000]

        logger.info(f"📝 [ImageUtils] 프롬프트 생성 완료 (길이: {len(prompt_text)})")
        logger.info(f"📝 [ImageUtils] 프롬프트 내용: {prompt_text}")

        logger.info("🤖 [ImageUtils] OpenAI 클라이언트 생성")
        client = openai.OpenAI(api_key=API_KEY)

        logger.info("📡 [ImageUtils] DALL-E API 호출 시작")
        response = client.images.generate(
            model="dall-e-2",
            prompt=prompt_text,
            size="1024x1024",
            n=1,
        )
        logger.info("✅ [ImageUtils] DALL-E API 호출 성공")

        img_url = response.data[0].url
        logger.info(f"🌐 [ImageUtils] 이미지 URL 생성됨: {img_url[:100]}...")

        if img_url:
            logger.info("📥 [ImageUtils] 이미지 다운로드 시작")
            response_img = requests.get(img_url)
            logger.info(
                f"📥 [ImageUtils] 이미지 다운로드 완료 - 크기: {len(response_img.content)} bytes"
            )

            output_dir = Path(settings.MEDIA_ROOT) / "thread_cover_img"
            output_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"📁 [ImageUtils] 출력 디렉토리 확인: {output_dir}")

            # 확장자 추출
            ext = img_url.split(".")[-1].split("?")[0]
            if not ext or ext not in ["png", "jpg", "jpeg", "webp"]:
                ext = "png"  # 기본값
            logger.info(f"📄 [ImageUtils] 파일 확장자: {ext}")

            file_name = f"thread_{thread.pk}.{ext}"
            file_path = output_dir / file_name
            logger.info(f"📄 [ImageUtils] 파일 경로: {file_path}")

            file_path.write_bytes(response_img.content)
            logger.info(f"💾 [ImageUtils] 파일 저장 완료: {file_path}")

            # 파일 존재 확인
            if file_path.exists():
                logger.info(
                    f"✅ [ImageUtils] 파일 존재 확인됨 - 크기: {file_path.stat().st_size} bytes"
                )
            else:
                logger.error(f"❌ [ImageUtils] 파일 저장 실패 - 파일이 존재하지 않음")

            # ImageField에 맞는 상대 경로 반환 (thread_cover_img/ 폴더 경로)
            relative_path = f"thread_cover_img/{file_name}"
            logger.info(
                f"✅ [ImageUtils] 이미지 생성 성공 - 상대 경로: {relative_path}"
            )
            return relative_path
        else:
            logger.error("❌ [ImageUtils] 이미지 URL이 없음")

    except Exception as e:
        logger.error(f"❌ [ImageUtils] 이미지 생성 오류: {e}", exc_info=True)

    logger.error("❌ [ImageUtils] 이미지 생성 실패 - None 반환")
    return None
