from rest_framework_simplejwt.tokens import RefreshToken
import uuid


class CustomRefreshToken(RefreshToken):
    @property
    def jti(self):
        return self.payload.get("jti")

    @classmethod
    def for_user(cls, user):
        token = super().for_user(user)
        # 세션 ID 생성 및 토큰에 추가
        session_id = str(uuid.uuid4())
        print(f"Generated session ID: {session_id}")  # 디버깅 로그
        token["session_id"] = session_id
        return token, session_id


# AccessToken도 필요시 확장 가능
