from rest_framework_simplejwt.tokens import RefreshToken


class CustomRefreshToken(RefreshToken):
    @property
    def jti(self):
        return self.payload.get("jti")

    @classmethod
    def for_user(cls, user):
        token = super().for_user(user)
        # jti는 이미 SimpleJWT에서 자동 생성됨
        return token


# AccessToken도 필요시 확장 가능
