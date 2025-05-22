from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.http import HttpRequest
from .models import CustomUser


class CustomAccountAdapter(DefaultAccountAdapter):
    def save_user(self, request, user, form, commit=True):
        """
        일반 회원가입시 기본 정보 외에 추가 정보를 저장하는 메서드.
        dj-rest-auth에서는 CustomRegisterSerializer에서 처리하므로,
        여기서는 기본 구현만 유지합니다.
        """
        user = super().save_user(request, user, form, commit)
        return user


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        """
        소셜 로그인 직전에 호출되는 메서드.
        소셜 계정과 기존 이메일 계정을 연결하는 등의 처리를 수행할 수 있습니다.
        """
        # 기존 이메일로 가입된 사용자가 있는지 확인
        email = sociallogin.account.extra_data.get("email", None)
        if email:
            try:
                user = CustomUser.objects.get(email=email)
                # 기존 사용자를 소셜 로그인 객체에 연결
                sociallogin.connect(request, user)
            except CustomUser.DoesNotExist:
                # 기존 사용자가 없으면 새로 생성됨 (기본 동작)
                pass

    def populate_user(self, request, sociallogin, data):
        """
        소셜 로그인으로 새 사용자 생성 시 필요한 초기 데이터 설정
        """
        user = super().populate_user(request, sociallogin, data)
        # 소셜 로그인 제공자에 따라 다른 데이터를 가져올 수 있음
        if sociallogin.account.provider == "google":
            # Google에서 제공하는 정보를 활용
            pass
        elif sociallogin.account.provider == "kakao":
            # Kakao에서 제공하는 정보를 활용
            pass

        # 기본값 설정: 실제 서비스에서는 소셜 로그인 후
        # 추가 정보 입력 페이지로 리다이렉션하는 것이 좋습니다.
        user.gender = "M"  # 임시 기본값
        user.age = 20  # 임시 기본값
        user.annual_reading_count = 0

        return user
