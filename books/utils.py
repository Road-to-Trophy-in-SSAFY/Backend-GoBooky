import json
import requests
import openai
from pathlib import Path
from django.conf import settings
from pydantic import BaseModel


def create_thread_image(thread):
    API_KEY = settings.OPENAI_API_KEY

    print(f"🎨 [이미지 생성] 시작 - Thread ID: {thread.pk}")
    print(f"🔑 [이미지 생성] API 키 존재 여부: {bool(API_KEY)}")

    # API 키가 없으면 None 반환
    if not API_KEY:
        print("❌ [이미지 생성] OpenAI API 키가 설정되지 않았습니다.")
        return None

    try:
        print(f"📝 [이미지 생성] 프롬프트: {thread.content[:100]}...")

        client = openai.OpenAI(api_key=API_KEY)
        response = client.images.generate(
            model="dall-e-2",
            prompt=f"Create a beautiful, artistic book-related image for the following thread about reading: {thread.content[:500]}",
            size="1024x1024",
            quality="standard",
            n=1,
        )

        img_url = response.data[0].url
        print(f"🌐 [이미지 생성] 이미지 URL 생성됨: {img_url[:50]}...")

        if img_url:
            print("📥 [이미지 생성] 이미지 다운로드 중...")
            response_img = requests.get(img_url)

            output_dir = Path(settings.MEDIA_ROOT) / "thread_cover_img"
            output_dir.mkdir(parents=True, exist_ok=True)

            # 확장자 추출
            ext = img_url.split(".")[-1].split("?")[0]
            if not ext or ext not in ["png", "jpg", "jpeg", "webp"]:
                ext = "png"  # 기본값

            file_name = f"thread_{thread.pk}.{ext}"
            file_path = output_dir / file_name

            file_path.write_bytes(response_img.content)
            print(f"💾 [이미지 생성] 파일 저장 완료: {file_path}")

            # ImageField에 맞는 상대 경로 반환 (thread_cover_img/ 폴더 경로)
            relative_path = f"thread_cover_img/{file_name}"
            print(f"✅ [이미지 생성] 성공 - 상대 경로: {relative_path}")
            return relative_path

    except Exception as e:
        print(f"❌ [이미지 생성] 오류 발생: {e}")
        import traceback

        print(f"❌ [이미지 생성] 상세 오류: {traceback.format_exc()}")

    return None
