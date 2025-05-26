from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import get_user_model, login, logout
from django.utils.crypto import get_random_string
from django.conf import settings
from django.core.mail import send_mail, EmailMultiAlternatives
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.cache import cache
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator
from .serializers import (
    RegisterSerializer,
    VerifyEmailSerializer,
    ProfileCompleteSerializer,
    LoginSerializer,
    AccountDeleteSerializer,
    UserSerializer,
    CategorySerializer,
    CheckNicknameSerializer,
    ProfileUpdateSerializer,
)
from .redis_utils import (
    set_confirm,
    get_confirm,
    delete_confirm,
    rate_limit_check,
    blacklist_token,
    redis_client,
)
from .tokens import CustomRefreshToken
import uuid
import datetime
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from books.models import Category
import json
import logging
import jwt
from datetime import datetime, timedelta, timezone
from .utils import log_auth_action
from rest_framework.authentication import SessionAuthentication
from dj_rest_auth.jwt_auth import JWTCookieAuthentication
from rest_framework import serializers
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, AuthenticationFailed

logger = logging.getLogger(__name__)

User = get_user_model()


# 닉네임 중복 확인 시리얼라이저
class CheckNicknameSerializer(serializers.Serializer):
    username = serializers.CharField(min_length=2, max_length=20)


# 캐시 키 생성 함수
def get_cache_key(prefix, *args):
    return f"{settings.CACHE_KEY_PREFIX}:{prefix}:{':'.join(str(arg) for arg in args)}"


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        from .serializers import RegisterSerializer
        import json

        data = request.data
        serializer = RegisterSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        password = serializer.validated_data["password"]

        # 이메일 인증 UUID 생성
        confirm_uuid = str(uuid.uuid4())

        # 레이트리밋 체크
        if not rate_limit_check(email):
            return Response(
                {
                    "detail": "이메일 인증 요청이 너무 많습니다. 잠시 후 다시 시도해주세요."
                },
                status=429,
            )

        # 이전 링크 만료 처리
        for key in redis_client.scan_iter(f"pending_user:*"):
            user_data_json = redis_client.get(key)
            if user_data_json:
                user_data = json.loads(user_data_json)
                if user_data.get("email") == email:
                    redis_client.delete(key)

        # 임시 저장 (5분)
        user_data = {
            "email": email,
            "password": password,
            "email_verified": False,
            "created_at": datetime.now().isoformat(),
        }
        redis_client.setex(
            f"pending_user:{confirm_uuid}", 300, json.dumps(user_data)  # 5분 = 300초
        )
        # 이메일 발송
        verification_url = f"http://localhost:5173/verify-email/{confirm_uuid}"
        subject = "[GoBooky] 이메일 인증 요청"
        text_content = f"아래 링크를 클릭해 인증을 완료하세요.\n{verification_url}"
        html_content = f'아래 링크를 클릭해 인증을 완료하세요.<br><a href="{verification_url}">{verification_url}</a>'

        try:
            msg = EmailMultiAlternatives(
                subject, text_content, settings.DEFAULT_FROM_EMAIL, [email]
            )
            msg.attach_alternative(html_content, "text/html")
            msg.send()
        except Exception as e:
            # 이메일 발송 실패 시 임시 저장 데이터 삭제
            redis_client.delete(f"pending_user:{confirm_uuid}")
            return Response(
                {"detail": "이메일 발송에 실패했습니다. 다시 시도해주세요."},
                status=500,
            )

        return Response(
            {"detail": "이메일 인증 메일이 발송되었습니다.", "uuid": confirm_uuid},
            status=201,
        )


class ResendEmailView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        import json

        email = request.data.get("email")
        if not email:
            return Response({"detail": "이메일 주소가 필요합니다."}, status=400)
        # pending_user에서 해당 이메일의 uuid 찾기
        for key in redis_client.scan_iter("pending_user:*"):
            user_data_json = redis_client.get(key)
            if not user_data_json:
                continue
            user_data = json.loads(user_data_json)
            if user_data.get("email") == email:
                uuid = key.decode().split(":")[1]
                # 레이트리밋 체크
                if not rate_limit_check(email):
                    return Response(
                        {
                            "detail": "이메일 인증 요청이 너무 많습니다. 잠시 후 다시 시도해주세요."
                        },
                        status=429,
                    )
                verification_url = f"http://localhost:5173/verify-email/{uuid}"
                subject = "[GoBooky] 이메일 인증 요청 (재전송)"
                text_content = (
                    f"아래 링크를 클릭해 인증을 완료하세요.\n{verification_url}"
                )
                html_content = f'아래 링크를 클릭해 인증을 완료하세요.<br><a href="{verification_url}">{verification_url}</a>'
                msg = EmailMultiAlternatives(
                    subject, text_content, settings.DEFAULT_FROM_EMAIL, [email]
                )
                msg.attach_alternative(html_content, "text/html")
                msg.send()
                return Response({"detail": "인증 이메일이 재발송되었습니다."})
        return Response(
            {"detail": "해당 이메일로 대기 중인 인증이 없습니다."}, status=400
        )


class VerifyEmailView(APIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = VerifyEmailSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        confirm_uuid = serializer.validated_data["uuid"]

        # 캐시에서 확인
        cache_key = get_cache_key("email_verify", confirm_uuid)
        cached_result = cache.get(cache_key)
        if cached_result:
            return Response(cached_result)

        user_data_json = redis_client.get(f"pending_user:{confirm_uuid}")
        if not user_data_json:
            return Response(
                {"detail": "인증 링크가 만료되었거나 잘못되었습니다."}, status=400
            )

        user_data = json.loads(user_data_json)

        # 이메일이 인증되지 않은 경우
        if not user_data.get("email_verified"):
            return Response(
                {
                    "detail": "아직 이메일 인증이 완료되지 않았습니다. 인증 링크를 클릭해주세요."
                },
                status=400,
            )

        response_data = {
            "detail": "이메일 인증이 완료되었습니다. 다음 단계로 진행해주세요."
        }
        cache.set(cache_key, response_data, settings.CACHE_TTL)
        return Response(response_data)

    def get(self, request, uuid):
        user_data_json = redis_client.get(f"pending_user:{uuid}")
        if not user_data_json:
            return Response({"detail": "만료된 링크입니다."}, status=400)

        user_data = json.loads(user_data_json)

        # 이메일이 이미 인증된 경우
        if user_data.get("email_verified"):
            return Response({"detail": "이미 인증이 완료된 링크입니다."}, status=400)

        # 이메일 인증 처리
        user_data["email_verified"] = True
        redis_client.setex(
            f"pending_user:{uuid}", 300, json.dumps(user_data)
        )  # 5분 유지

        # 캐시 무효화
        cache_key = get_cache_key("email_verify", uuid)
        cache.delete(cache_key)

        return Response(
            {"detail": "이메일 인증이 완료되었습니다. 다음을 진행해주세요."}
        )


class CheckNicknameView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = CheckNicknameSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        username = serializer.validated_data["username"]

        # 닉네임 중복 확인
        exists = User.objects.filter(username=username).exists()

        return Response({"available": not exists}, status=status.HTTP_200_OK)


class ProfileCompleteView(APIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = ProfileCompleteSerializer

    def patch(self, request):
        # 마지막 단계에서 모든 정보와 uuid를 받아 실제 User 생성
        import json

        confirm_uuid = request.data.get("uuid")
        if not confirm_uuid:
            return Response({"detail": "인증 UUID가 필요합니다."}, status=400)
        user_data_json = redis_client.get(f"pending_user:{confirm_uuid}")
        if not user_data_json:
            return Response(
                {
                    "detail": "회원가입 세션이 만료되었습니다. 처음부터 다시 시도해주세요."
                },
                status=400,
            )
        user_data = json.loads(user_data_json)
        if not user_data.get("email_verified"):
            return Response({"detail": "이메일 인증이 필요합니다."}, status=400)

        # 프론트에서 보낸 최신 프로필 정보 반영
        user_data["username"] = request.data.get("username")
        user_data["first_name"] = request.data.get("first_name")
        user_data["last_name"] = request.data.get("last_name")
        user_data["gender"] = request.data.get("gender")
        user_data["weekly_read_time"] = request.data.get("weekly_read_time")
        user_data["yearly_read_count"] = request.data.get("yearly_read_count")
        user_data["category_ids"] = request.data.get("category_ids", [])

        # 중복 체크
        if User.objects.filter(email=user_data["email"]).exists():
            redis_client.delete(f"pending_user:{confirm_uuid}")
            return Response({"detail": "이미 등록된 이메일입니다."}, status=400)

        # 실제 User 생성
        user = User.objects.create_user(
            email=user_data["email"],
            password=user_data["password"],
            username=user_data["username"],
            first_name=user_data["first_name"],
            last_name=user_data["last_name"],
            gender=user_data["gender"],
            weekly_read_time=user_data.get("weekly_read_time"),
            yearly_read_count=user_data.get("yearly_read_count"),
            is_active=True,
        )

        # 관심 장르 설정
        if user_data.get("category_ids"):
            user.categories.set(user_data["category_ids"])

        redis_client.delete(f"pending_user:{confirm_uuid}")
        return Response({"detail": "회원가입이 완료되었습니다."}, status=201)


class LegacyLoginView(APIView):  # 백업용으로 이름 변경
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data["user"]
            access_token = self._generate_access_token(user)
            refresh_token = self._generate_refresh_token(user)

            # 세션 ID 생성 및 Redis에 저장
            session_id = self._generate_session_id()
            session_data = {
                "user_id": str(user.id),
                "refresh_token": refresh_token,
            }
            redis_client.setex(
                f"session:{session_id}",
                settings.REFRESH_TOKEN_LIFETIME,
                json.dumps(session_data),
            )

            # Audit 로그 기록
            log_auth_action(
                user=user,
                action="login",
                request=request,
                details={"session_id": session_id},
            )

            response = Response(
                {
                    "access_token": access_token,
                    "user": UserSerializer(user).data,
                },
                status=status.HTTP_200_OK,
            )

            # 세션 ID를 쿠키로 설정
            response.set_cookie(
                "sid",
                session_id,
                max_age=settings.REFRESH_TOKEN_LIFETIME,
                httponly=True,
                secure=settings.DEBUG is False,
                samesite="Lax",
                domain=None,
                path="/",
            )

            return response
        else:
            # 실패한 로그인 시도 기록
            log_auth_action(
                user=None,
                action="failed_login",
                request=request,
                details={"errors": serializer.errors},
            )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def _generate_access_token(self, user):
        payload = {
            "user_id": str(user.id),
            "exp": datetime.now(timezone.utc)
            + timedelta(minutes=settings.ACCESS_TOKEN_LIFETIME),
            "iat": datetime.now(timezone.utc),
            "jti": str(uuid.uuid4().hex),
            "token_type": "access",
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

    def _generate_refresh_token(self, user):
        payload = {
            "user_id": str(user.id),
            "exp": datetime.now(timezone.utc)
            + timedelta(days=settings.REFRESH_TOKEN_LIFETIME),
            "iat": datetime.now(timezone.utc),
            "jti": str(uuid.uuid4().hex),
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

    def _generate_session_id(self):
        return jwt.encode(
            {"timestamp": datetime.now(timezone.utc).timestamp()},
            settings.SECRET_KEY,
            algorithm="HS256",
        )


class LegacyLogoutView(APIView):  # 백업용으로 이름 변경
    permission_classes = [AllowAny]
    authentication_classes = []
    # authentication_classes = [JWTCookieAuthentication]

    def post(self, request):
        logger.info("LogoutView: POST request received (start)")
        # Access Token 인증 시 발생할 수 있는 예외를 잡아서 무시합니다.
        try:
            # DRF의 request.user 접근 시 인증 시도가 일어날 수 있습니다.
            # 인증 실패 시 여기서 예외가 발생할 수 있으며, 로그아웃 로직을 방해할 수 있습니다.
            # 여기서는 예외 발생 여부만 확인하고 로그아웃 로직을 계속 진행하도록 합니다.
            user = request.user  # 인증 시도 트리거
            if user and user.is_authenticated:
                logger.info(f"LogoutView: User is authenticated: {user.username}")
            else:
                logger.info("LogoutView: User is not authenticated.")
        except Exception as e:
            logger.warning(
                f"LogoutView: Error during initial authentication attempt: {e}"
            )
            # 예외 발생 시 무시하고 계속 진행
            pass

        logger.info(
            "LogoutView: Authentication check passed (or bypassed). Proceeding with logout."
        )

        session_id = request.COOKIES.get("sid")

        # 세션 ID가 있다면 Redis 세션 삭제 및 쿠키 제거 시도
        if session_id:
            logger.info(f"LogoutView: Session ID found in cookies: {session_id}")
            # Redis에서 세션 데이터 가져오기
            session_data_json = redis_client.get(f"session:{session_id}")
            if session_data_json:
                try:
                    session_data = json.loads(session_data_json)
                    refresh_token = session_data.get("refresh_token")
                    logger.info(
                        f"LogoutView: Session data retrieved for session ID: {session_id}, refresh token found: {bool(refresh_token)}"
                    )
                    logger.debug(
                        f"LogoutView: Retrieved refresh token: {refresh_token}"
                    )  # 로그 추가

                    # refresh token을 블랙리스트에 추가
                    if refresh_token:
                        try:
                            # 토큰 디코딩 시도
                            payload = jwt.decode(
                                refresh_token, settings.SECRET_KEY, algorithms=["HS256"]
                            )
                            logger.info(
                                f"LogoutView: Refresh token decoded successfully. Payload: {payload}"
                            )  # 로그 추가
                            exp = payload.get("exp")
                            if exp:
                                blacklist_token(
                                    refresh_token,
                                    exp - int(datetime.now(timezone.utc).timestamp()),
                                )
                                logger.info(
                                    f"LogoutView: Refresh token blacklisted successfully: {refresh_token}"
                                )
                            else:
                                logger.warning(
                                    f"LogoutView: Refresh token payload missing expiry (exp) for token: {refresh_token}"
                                )
                        except jwt.InvalidTokenError as e:
                            logger.error(
                                f"LogoutView: Invalid refresh token format during blacklisting: {refresh_token}. Error: {e}",
                                exc_info=True,
                            )  # 에러 로그 상세화
                            # 유효하지 않은 토큰은 블랙리스트에 추가하지 않고 건너뜁니다.
                            pass
                        except Exception as e:
                            logger.error(
                                f"LogoutView: Error blacklisting refresh token {refresh_token}: {e}",
                                exc_info=True,
                            )
                    else:
                        logger.warning(
                            f"LogoutView: No refresh token found in session data for session ID: {session_id}"
                        )

                except json.JSONDecodeError:
                    logger.error(
                        f"LogoutView: Failed to decode session data JSON for session ID: {session_id}. Data: {session_data_json}"
                    )  # 로그 추가
                    # JSON 디코딩 실패 시 Refresh Token 블랙리스트 추가 로직 건너뜁니다.
                    pass
                except Exception as e:
                    logger.error(
                        f"LogoutView: An unexpected error occurred during session data processing for session ID {session_id}: {e}",
                        exc_info=True,
                    )
                    pass
            else:
                logger.warning(
                    f"LogoutView: No session data found in Redis for session ID: {session_id}"
                )  # 로그 추가

            # Redis에서 세션 데이터 삭제 시도
            try:
                delete_success = redis_client.delete(f"session:{session_id}")
                if delete_success:
                    logger.info(
                        f"LogoutView: Redis session data deleted successfully for session ID: {session_id}"
                    )
                else:
                    logger.warning(
                        f"LogoutView: No Redis session data found to delete for session ID: {session_id}"
                    )
            except Exception as e:
                logger.error(
                    f"LogoutView: Error deleting Redis session data for session ID {session_id}: {e}",
                    exc_info=True,
                )

            # Audit 로그 기록
            log_auth_action(
                user=request.user if request.user.is_authenticated else None,
                action="logout",
                request=request,
                details={
                    "session_id": session_id,
                    "message": "Logout attempt (session ID found)",
                },
            )

            response = Response(status=status.HTTP_205_RESET_CONTENT)
            # 쿠키 삭제
            response.delete_cookie(
                "sid",
                path="/",
                domain=None,
                samesite="Lax",
            )
            # CSRF 쿠키 삭제 (필요하다면)
            if settings.CSRF_COOKIE_NAME:
                response.delete_cookie(
                    settings.CSRF_COOKIE_NAME,
                    path="/",
                    domain=None,
                    samesite="Lax",
                )
            logger.info(f"LogoutView: sid cookie deleted for session ID: {session_id}")
            return response

        # 세션 ID가 없는 경우
        logger.warning(
            "LogoutView: No session ID found in cookies. Proceeding with cookie deletion."
        )
        log_auth_action(
            user=request.user if request.user.is_authenticated else None,
            action="logout",
            request=request,
            details={
                "message": "Logout attempt (no session ID)",
                "session_id": session_id,
            },
        )

        response = Response(
            {"detail": "Logout successful or no active session."},
            status=status.HTTP_205_RESET_CONTENT,
        )
        response.delete_cookie(
            "sid",
            path="/",
            domain=None,
            samesite="Lax",
        )
        if settings.CSRF_COOKIE_NAME:
            response.delete_cookie(
                settings.CSRF_COOKIE_NAME,
                path="/",
                domain=None,
                samesite="Lax",
            )
        logger.info(
            "LogoutView: sid cookie deletion attempted (no initial session ID)."
        )
        return response


class AccountDeleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AccountDeleteSerializer

    def delete(self, request):
        serializer = self.serializer_class(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        user = request.user

        # 회원탈퇴 시 refresh token 블랙리스트 처리
        refresh_token = request.COOKIES.get(settings.SIMPLE_JWT["AUTH_COOKIE_REFRESH"])
        if refresh_token:
            try:
                from rest_framework_simplejwt.tokens import RefreshToken

                token = RefreshToken(refresh_token)
                token.blacklist()
                logger.info(f"🚫 회원탈퇴 시 JWT 토큰 블랙리스트 추가: {user.email}")
            except Exception as e:
                logger.warning(f"⚠️ 회원탈퇴 시 토큰 블랙리스트 실패: {str(e)}")

        # 사용자 삭제
        user.delete()

        # 응답 생성 및 쿠키 삭제
        response = Response(status=status.HTTP_204_NO_CONTENT)
        response.delete_cookie(
            settings.SIMPLE_JWT["AUTH_COOKIE_REFRESH"],
            path=settings.SIMPLE_JWT["AUTH_COOKIE_PATH"],
            domain=settings.SIMPLE_JWT.get("AUTH_COOKIE_DOMAIN"),
            samesite=settings.SIMPLE_JWT["AUTH_COOKIE_SAMESITE"],
        )

        return response


@api_view(["GET"])
@permission_classes([AllowAny])
def get_categories(request):
    cache_key = get_cache_key("categories", "all")
    cached_data = cache.get(cache_key)

    if cached_data:
        return Response(cached_data)

    categories = Category.objects.all()
    serializer = CategorySerializer(categories, many=True)
    cache.set(cache_key, serializer.data, 60 * 15)  # 15분 캐싱
    return Response(serializer.data)


class ProfileDetailView(generics.RetrieveUpdateAPIView):
    queryset = User.objects.all()
    permission_classes = [IsAuthenticated]
    lookup_field = "username"

    def get(self, request, *args, **kwargs):
        logger.debug(
            f"ProfileDetailView GET request received for username: {kwargs.get('username')}"
        )
        logger.debug(f"Request Headers: {request.headers}")
        logger.debug(f"Request Cookies: {request.COOKIES}")
        logger.debug(f"Request User after default authentication: {request.user}")
        logger.debug(
            f"Request User is authenticated after default authentication: {request.user.is_authenticated}"
        )

        # --- 추가된 디버그 로깅 ---
        logger.debug("Attempting manual JWT authentication check...")
        jwt_authenticator = JWTAuthentication()
        try:
            # manually authenticate the request
            user_auth_tuple = jwt_authenticator.authenticate(request)
            if user_auth_tuple:
                user, auth = user_auth_tuple
                logger.debug(
                    f"Manual JWT authentication SUCCESS: User: {user}, Auth: {auth}"
                )
                logger.debug(
                    f"Manual JWT authentication User is authenticated: {user.is_authenticated}"
                )
            else:
                logger.debug(
                    "Manual JWT authentication FAILED: authenticator returned None"
                )
        except (InvalidToken, AuthenticationFailed) as e:
            logger.error(
                f"Manual JWT authentication FAILED with exception: {e}", exc_info=True
            )
        except Exception as e:
            logger.error(
                f"Manual JWT authentication FAILED with unexpected exception: {e}",
                exc_info=True,
            )
        # --- 디버그 로깅 끝 ---

        # The permission check [IsAuthenticated] happens before this get method.
        # If request.user is AnonymousUser here, it means permission check failed.
        if not request.user.is_authenticated:
            logger.warning(
                "ProfileDetailView: Request reached get method but user is not authenticated. This should not happen if permission check worked as expected."
            )
            # You might want to return a 401/403 response here explicitly if needed,
            # but typically DRF handles this before the view method.
            # For now, we proceed to let super().get() likely raise PermissionDenied
            pass  # Proceed to super().get() to see default DRF behavior on unauthenticated user

        return super().get(request, *args, **kwargs)

    def get_serializer_class(self):
        # Use different serializers for retrieve (GET) and update (PATCH)
        if self.request.method == "GET":
            return UserSerializer
        return ProfileUpdateSerializer

    # Optional: Add logic to restrict access to own profile or by admin
    # def get_object(self):
    #     obj = super().get_object()
    #     # Example: Only allow users to view/edit their own profile
    #     if obj != self.request.user:
    #         raise permissions.PermissionDenied('You do not have permission to access this profile.')
    #     return obj


class LegacyRefreshTokenView(APIView):  # 백업용으로 이름 변경
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        logger.info("RefreshTokenView POST requested")
        session_id = request.COOKIES.get("sid")

        if not session_id:
            logger.warning("RefreshTokenView: No session ID found in cookies")
            return Response(
                {"error": "No session ID found"}, status=status.HTTP_401_UNAUTHORIZED
            )

        session_data = redis_client.get(f"session:{session_id}")
        if not session_data:
            logger.warning(f"RefreshTokenView: Invalid session ID: {session_id}")
            return Response(
                {"error": "Invalid session"}, status=status.HTTP_401_UNAUTHORIZED
            )

        session_data = json.loads(session_data)
        user_id = session_data.get("user_id")
        refresh_token = session_data.get("refresh_token")

        logger.info(f"RefreshTokenView: Found session data for user_id: {user_id}")

        try:
            # 블랙리스트 확인
            if redis_client.exists(f"bl:{refresh_token}"):
                logger.warning(
                    f"RefreshTokenView: Token has been revoked: {refresh_token}"
                )
                return Response(
                    {"error": "Token has been revoked"},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            logger.info("RefreshTokenView: Token is not blacklisted")

            # Refresh Token 검증
            payload = jwt.decode(
                refresh_token, settings.SECRET_KEY, algorithms=["HS256"]
            )
            logger.info(
                f"RefreshTokenView: Token decoded successfully for user_id: {payload.get('user_id')}"
            )

            user = User.objects.get(id=user_id)
            logger.info(f"RefreshTokenView: User object loaded: {user}")

            # 새로운 Access Token만 생성
            new_access_token = self._generate_access_token(user)
            logger.info("RefreshTokenView: New access token generated")

            # Audit 로그 기록
            log_auth_action(
                user=user,
                action="refresh_token",
                request=request,
                details={"session_id": session_id},
            )
            logger.info("RefreshTokenView: Audit log recorded")

            user_data = UserSerializer(user).data
            logger.info(f"RefreshTokenView: Serialized user data: {user_data}")

            return Response(
                {
                    "access": new_access_token,
                    "user": user_data,
                },
                status=status.HTTP_200_OK,
            )
        except (
            jwt.ExpiredSignatureError,
            jwt.InvalidTokenError,
            User.DoesNotExist,
        ) as e:
            logger.error(
                f"RefreshTokenView: Token validation or User lookup failed: {e}"
            )
            return Response(
                {"error": "Invalid refresh token"}, status=status.HTTP_401_UNAUTHORIZED
            )
        except Exception as e:
            logger.error(
                f"RefreshTokenView: An unexpected error occurred: {e}", exc_info=True
            )
            return Response({"detail": str(e)}, status=status.HTTP_401_UNAUTHORIZED)

    def _generate_access_token(self, user):
        payload = {
            "user_id": str(user.id),
            "exp": datetime.now(timezone.utc)
            + timedelta(minutes=settings.ACCESS_TOKEN_LIFETIME),
            "iat": datetime.now(timezone.utc),
            "jti": str(uuid.uuid4().hex),
            "token_type": "access",
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

    def _generate_refresh_token(self, user):
        payload = {
            "user_id": str(user.id),
            "exp": datetime.now(timezone.utc)
            + timedelta(days=settings.REFRESH_TOKEN_LIFETIME),
            "iat": datetime.now(timezone.utc),
            "jti": str(uuid.uuid4().hex),
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

    def _generate_session_id(self):
        return jwt.encode(
            {"timestamp": datetime.now(timezone.utc).timestamp()},
            settings.SECRET_KEY,
            algorithm="HS256",
        )


class FollowToggleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, username):
        try:
            target_user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response({"detail": "해당 유저가 존재하지 않습니다."}, status=404)

        if request.user == target_user:
            return Response({"detail": "자기 자신을 팔로우할 수 없습니다."}, status=400)

        if target_user in request.user.following.all():
            request.user.following.remove(target_user)
            is_following = False
            action = "unfollowed"
        else:
            request.user.following.add(target_user)
            is_following = True
            action = "followed"

        return Response(
            {
                "action": action,
                "is_following": is_following,
                "followers_count": target_user.followers.count(),
            }
        )
