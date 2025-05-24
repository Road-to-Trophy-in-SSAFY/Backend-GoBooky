from django.middleware.csrf import get_token
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
import json


class DoubleSubmitCookieMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        if not getattr(request, "_csrf_cookie_set", False):
            if getattr(request, "csrf_cookie_needs_reset", False):
                response.delete_cookie(settings.CSRF_COOKIE_NAME)

            csrf_token = get_token(request)
            response.set_cookie(
                settings.CSRF_COOKIE_NAME,
                csrf_token,
                max_age=settings.CSRF_COOKIE_AGE,
                domain=settings.CSRF_COOKIE_DOMAIN,
                secure=settings.CSRF_COOKIE_SECURE,
                httponly=False,  # JavaScript에서 접근 가능하도록 설정
                samesite=settings.CSRF_COOKIE_SAMESITE,
            )
            request._csrf_cookie_set = True

            # X-CSRF-TOKEN 헤더도 설정
            response["X-CSRF-TOKEN"] = csrf_token

        return response
