from .models import AuditLog
from django.utils import timezone


def log_auth_action(user, action, request=None, details=None):
    """
    인증 관련 활동을 Audit 로그에 기록합니다.

    Args:
        user: User 객체 또는 None
        action: AuditLog.ACTION_CHOICES 중 하나
        request: HttpRequest 객체 (선택사항)
        details: 추가 정보를 담은 dict (선택사항)
    """
    log_data = {
        "user": user,
        "action": action,
        "timestamp": timezone.now(),
    }

    if request:
        log_data.update(
            {
                "ip_address": get_client_ip(request),
                "user_agent": request.META.get("HTTP_USER_AGENT"),
            }
        )

    if details:
        log_data["details"] = details

    AuditLog.objects.create(**log_data)


def get_client_ip(request):
    """
    클라이언트의 IP 주소를 가져옵니다.
    """
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip
