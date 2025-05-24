import json
import requests
import openai
from pathlib import Path
from django.conf import settings
from pydantic import BaseModel


def create_thread_image(thread):
    API_KEY = settings.OPENAI_API_KEY

    # API 키가 없으면 None 반환
    if not API_KEY:
        print("OpenAI API 키가 설정되지 않았습니다.")
        return None

    try:
        client = openai.OpenAI(api_key=API_KEY)
        response = client.images.generate(
            model="dall-e-3",
            prompt=f"Create a beautiful image for the following thread: {thread.content}",
            size="1024x1024",
            quality="standard",
            n=1,
        )

        img_url = response.data[0].url
        if img_url:
            response_img = requests.get(img_url)
            output_dir = Path(settings.MEDIA_ROOT) / "thread_cover_img"
            output_dir.mkdir(parents=True, exist_ok=True)
            # 확장자 추출
            ext = img_url.split(".")[-1].split("?")[0]
            file_name = f"thread_{thread.pk}.{ext}"
            file_path = output_dir / file_name
            file_path.write_bytes(response_img.content)
            # ImageField에 맞는 상대 경로 반환 (thread_cover_img/ 폴더 경로)
            return f"thread_cover_img/{file_name}"
    except Exception as e:
        print(f"이미지 생성 중 오류 발생: {e}")
    return None
