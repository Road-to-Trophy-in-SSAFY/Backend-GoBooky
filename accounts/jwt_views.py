from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer,
    TokenRefreshSerializer,
)
from django.conf import settings
from django.contrib.auth import get_user_model
from .serializers import UserSerializer
from .utils import log_auth_action
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    지침에 따른 커스텀 토큰 시리얼라이저
    - 사용자 정보 포함
    - 커스텀 클레임 추가 가능
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # 커스텀 클레임 추가
        token["email"] = user.email
        token["username"] = user.username

        return token

    def validate(self, attrs):
        data = super().validate(attrs)

        # 사용자 정보 추가
        data["user"] = UserSerializer(self.user).data

        return data


class CustomTokenRefreshSerializer(TokenRefreshSerializer):
    """
    지침에 따른 커스텀 토큰 갱신 시리얼라이저
    - 사용자 정보 포함
    """

    def validate(self, attrs):
        data = super().validate(attrs)

        # 토큰에서 사용자 정보 추출
        refresh = RefreshToken(attrs["refresh"])
        user = User.objects.get(id=refresh["user_id"])

        # 사용자 정보 추가
        data["user"] = UserSerializer(user).data

        return data


class CustomTokenObtainPairView(TokenObtainPairView):
    """
    지침에 따른 로그인 뷰 - SimpleJWT 내장 뷰 활용
    - Access token은 응답 body에 반환 (메모리 저장용)
    - Refresh token은 HttpOnly 쿠키로 설정
    - 로그인 감사 로그 기록
    """

    permission_classes = [AllowAny]
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        try:
            # 부모 클래스의 post 메서드 호출
            response = super().post(request, *args, **kwargs)

            if response.status_code == 200:
                data = response.data

                # Refresh token을 HttpOnly 쿠키로 설정
                refresh_token = data.get("refresh")
                if refresh_token:
                    response.set_cookie(
                        settings.SIMPLE_JWT["AUTH_COOKIE_REFRESH"],
                        refresh_token,
                        max_age=settings.SIMPLE_JWT[
                            "REFRESH_TOKEN_LIFETIME"
                        ].total_seconds(),
                        httponly=settings.SIMPLE_JWT["AUTH_COOKIE_HTTP_ONLY"],
                        secure=settings.SIMPLE_JWT["AUTH_COOKIE_SECURE"],
                        samesite=settings.SIMPLE_JWT["AUTH_COOKIE_SAMESITE"],
                        path=settings.SIMPLE_JWT["AUTH_COOKIE_PATH"],
                    )

                    # 응답에서 refresh token 제거 (쿠키로만 전송)
                    del data["refresh"]

                # 성공 로그인 기록
                user_data = data.get("user")
                if user_data:
                    try:
                        user = User.objects.get(id=user_data["id"])
                        log_auth_action(
                            user=user,
                            action="jwt_login",
                            request=request,
                            details={"method": "jwt_login", "success": True},
                        )
                    except User.DoesNotExist:
                        pass

                logger.info(
                    f"✅ JWT 로그인 성공: {user_data.get('email') if user_data else 'Unknown'}"
                )

            return response

        except Exception as e:
            # 실패한 로그인 시도 기록
            log_auth_action(
                user=None,
                action="failed_jwt_login",
                request=request,
                details={"error": str(e), "method": "jwt_login"},
            )
            logger.error(f"❌ JWT 로그인 실패: {str(e)}")
            raise


class CustomTokenRefreshView(TokenRefreshView):
    """
    완전한 토큰 갱신 뷰 - ROTATE_REFRESH_TOKENS 지원
    - HttpOnly 쿠키에서 refresh token 읽기
    - 새로운 access token 반환
    - ROTATE_REFRESH_TOKENS=True인 경우 새 refresh token을 쿠키에 설정
    - 이전 refresh token은 자동으로 블랙리스트에 추가됨
    """

    permission_classes = [AllowAny]
    serializer_class = CustomTokenRefreshSerializer  # 커스텀 시리얼라이저 사용

    def post(self, request, *args, **kwargs):
        # 쿠키에서 refresh token 가져오기
        refresh_token = request.COOKIES.get(settings.SIMPLE_JWT["AUTH_COOKIE_REFRESH"])

        if not refresh_token:
            logger.warning("❌ JWT 토큰 갱신 실패: Refresh token이 없음")
            return Response(
                {"detail": "Refresh token이 없습니다."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            # 새로운 딕셔너리로 데이터 생성 (더 확실한 방법)
            data = {"refresh": refresh_token}
            logger.info(f"🔍 [DEBUG] 입력 refresh token: {refresh_token[:50]}...")

            # 시리얼라이저에 데이터 전달
            serializer = self.get_serializer(data=data)
            logger.info(f"🔍 [DEBUG] 시리얼라이저 생성 완료")
            serializer.is_valid(raise_exception=True)
            logger.info(f"🔍 [DEBUG] 시리얼라이저 검증 완료")

            # 검증된 데이터 가져오기
            validated_data = serializer.validated_data

            # 응답 생성
            response = Response(validated_data, status=status.HTTP_200_OK)

            # ROTATE_REFRESH_TOKENS=True인 경우 새로운 refresh token을 쿠키에 설정
            if settings.SIMPLE_JWT.get("ROTATE_REFRESH_TOKENS", False):
                new_refresh_token = validated_data.get("refresh")
                if new_refresh_token:
                    response.set_cookie(
                        settings.SIMPLE_JWT["AUTH_COOKIE_REFRESH"],
                        new_refresh_token,
                        max_age=settings.SIMPLE_JWT[
                            "REFRESH_TOKEN_LIFETIME"
                        ].total_seconds(),
                        httponly=settings.SIMPLE_JWT["AUTH_COOKIE_HTTP_ONLY"],
                        secure=settings.SIMPLE_JWT["AUTH_COOKIE_SECURE"],
                        samesite=settings.SIMPLE_JWT["AUTH_COOKIE_SAMESITE"],
                        path=settings.SIMPLE_JWT["AUTH_COOKIE_PATH"],
                    )

            # 응답에서 refresh token 제거 (쿠키로만 관리)
            if "refresh" in validated_data:
                del validated_data["refresh"]

            # 토큰 갱신 로그 기록
            user_data = validated_data.get("user")
            if user_data:
                try:
                    user = User.objects.get(id=user_data["id"])
                    log_auth_action(
                        user=user,
                        action="jwt_refresh",
                        request=request,
                        details={"method": "jwt_refresh", "success": True},
                    )
                    logger.info(f"✅ JWT 토큰 갱신 성공: {user.email}")
                except User.DoesNotExist:
                    logger.warning("⚠️ 토큰 갱신 성공했지만 사용자를 찾을 수 없음")

            return response

        except (TokenError, InvalidToken) as e:
            logger.error(f"❌ JWT 토큰 갱신 실패: {str(e)}")
            return Response(
                {"detail": "유효하지 않은 refresh token입니다."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except Exception as e:
            logger.error(f"❌ JWT 토큰 갱신 중 예상치 못한 오류: {str(e)}")
            return Response(
                {"detail": "토큰 갱신 중 오류가 발생했습니다."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class CustomTokenBlacklistView(TokenRefreshView):
    """
    간단한 해결책 - 로그아웃 뷰
    - HttpOnly 쿠키 삭제 (블랙리스트 없이)
    - 로그아웃 감사 로그 기록
    - ROTATE_REFRESH_TOKENS=False이므로 토큰은 자연 만료됨
    """

    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        # 쿠키에서 refresh token 가져오기
        refresh_token = request.COOKIES.get(settings.SIMPLE_JWT["AUTH_COOKIE_REFRESH"])

        user = None
        if refresh_token:
            try:
                # 토큰을 블랙리스트에 추가
                token = RefreshToken(refresh_token)
                user = User.objects.get(id=token["user_id"])

                # 토큰 블랙리스트 처리 (BLACKLIST_AFTER_ROTATION=True인 경우)
                if settings.SIMPLE_JWT.get("BLACKLIST_AFTER_ROTATION", False):
                    token.blacklist()
                    logger.info(f"🚫 JWT 토큰 블랙리스트 추가: {user.email}")

                logger.info(f"✅ JWT 로그아웃 처리: {user.email}")

            except (TokenError, User.DoesNotExist) as e:
                logger.warning(f"⚠️ JWT 토큰 정보 추출 실패: {str(e)}")
                # 토큰이 이미 만료되었거나 유효하지 않아도 로그아웃 진행

        # 응답 생성 및 쿠키 삭제
        response = Response(
            {"detail": "로그아웃되었습니다."}, status=status.HTTP_200_OK
        )

        # Refresh token 쿠키 삭제 (모든 속성을 정확히 맞춰서 삭제)
        response.delete_cookie(
            settings.SIMPLE_JWT["AUTH_COOKIE_REFRESH"],
            path=settings.SIMPLE_JWT["AUTH_COOKIE_PATH"],
            domain=settings.SIMPLE_JWT.get("AUTH_COOKIE_DOMAIN"),
            samesite=settings.SIMPLE_JWT["AUTH_COOKIE_SAMESITE"],
        )

        # 로그아웃 로그 기록
        log_auth_action(
            user=user,
            action="jwt_logout",
            request=request,
            details={"method": "jwt_logout", "success": True},
        )

        logger.info(f"✅ JWT 로그아웃 완료: {user.email if user else 'Unknown'}")

        return response
