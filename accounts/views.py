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
from rest_framework.permissions import AllowAny
from .models import Category

User = get_user_model()


# 캐시 키 생성 함수
def get_cache_key(prefix, *args):
    return f"{settings.CACHE_KEY_PREFIX}:{prefix}:{':'.join(str(arg) for arg in args)}"


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        # 1단계: 이메일과 비밀번호만 임시 저장
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
        # 임시 저장 (24시간)
        user_data = {
            "email": email,
            "password": password,
            "email_verified": False,
        }
        redis_client.setex(
            f"pending_user:{confirm_uuid}", 24 * 3600, json.dumps(user_data)
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
        response_data = (
            {"detail": "이메일 인증이 완료되었습니다. 다음 단계로 진행해주세요."}
            if user_data.get("email_verified")
            else {
                "detail": "아직 이메일 인증이 완료되지 않았습니다. 인증 링크를 클릭해주세요."
            }
        )

        # 결과 캐싱
        cache.set(cache_key, response_data, settings.CACHE_TTL)

        return Response(response_data)

    def get(self, request, uuid):
        user_data_json = redis_client.get(f"pending_user:{uuid}")
        if not user_data_json:
            return Response({"detail": "만료된 링크입니다."}, status=400)

        user_data = json.loads(user_data_json)
        user_data["email_verified"] = True
        redis_client.setex(f"pending_user:{uuid}", 24 * 3600, json.dumps(user_data))

        # 캐시 무효화
        cache_key = get_cache_key("email_verify", uuid)
        cache.delete(cache_key)

        return Response(
            {"detail": "이메일 인증이 완료되었습니다. 다음을 진행해주세요."}
        )


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


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = LoginSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        refresh = CustomRefreshToken.for_user(user)
        redis_client.setex(f"refresh:{user.id}:{refresh['jti']}", 7 * 24 * 3600, 1)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserSerializer(user).data,
            }
        )


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            redis_client.delete(f"refresh:{request.user.id}:{token['jti']}")
            return Response(status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            return Response(status=status.HTTP_400_BAD_REQUEST)


class AccountDeleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AccountDeleteSerializer

    def delete(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@method_decorator(cache_page(60 * 15), name="get")  # 15분 캐싱
@api_view(["GET"])
@permission_classes([AllowAny])
def get_categories(request):
    categories = Category.objects.all()
    serializer = CategorySerializer(categories, many=True)
    return Response(serializer.data)
