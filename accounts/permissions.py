from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsSelf(BasePermission):
    """
    사용자가 자기 자신의 객체에만 접근할 수 있도록 하는 권한
    프로필 수정, 계정 삭제 등에 사용
    """

    def has_object_permission(self, request, view, obj):
        return obj == request.user


class IsAuthorOrReadOnly(BasePermission):
    """
    작성자는 모든 권한, 다른 사용자는 읽기 권한만
    Thread CRUD에 사용
    """

    def has_object_permission(self, request, view, obj):
        # 읽기 권한은 모든 인증된 사용자에게 허용
        if request.method in SAFE_METHODS:
            return True
        # 쓰기 권한은 작성자에게만 허용
        return obj.user == request.user


class IsOwnerOrReadOnly(BasePermission):
    """
    소유자는 모든 권한, 다른 사용자는 읽기 권한만
    일반적인 소유권 기반 권한
    """

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return (
            obj.owner == request.user
            if hasattr(obj, "owner")
            else obj.user == request.user
        )
