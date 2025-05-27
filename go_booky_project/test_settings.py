"""
테스트용 Django 설정
SQLite 데이터베이스 사용
"""

from .settings import *

# 테스트용 SQLite 데이터베이스
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# 테스트용 캐시 설정
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# 테스트 시 로그 레벨 조정
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "WARNING",
        },
    },
}

# 테스트 시 미디어 파일 처리
MEDIA_ROOT = "/tmp/test_media"

# 테스트 시 이메일 백엔드
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# 테스트 시 비밀번호 해싱 속도 향상
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]
