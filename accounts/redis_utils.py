import redis
from django.conf import settings

# Redis 연결 (settings에 REDIS_URL 필요)
redis_client = redis.StrictRedis.from_url(
    getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
)


def set_with_ttl(key, value, ttl):
    redis_client.setex(key, ttl, value)


def get_value(key):
    return redis_client.get(key)


def delete_key(key):
    redis_client.delete(key)


def incr_key(key):
    return redis_client.incr(key)


def get_ttl(key):
    return redis_client.ttl(key)


def rate_limit_check(email, limit=5, window=60):
    key = f"rate_limit:{email}"
    count = incr_key(key)
    if count == 1:
        redis_client.expire(key, window)
    if count > limit:
        return False
    return True


def blacklist_token(jti, ttl):
    redis_client.setex(f"bl:{jti}", ttl, 1)


# 이메일 인증 confirm 키
def set_confirm(uuid, user_id, ttl=300):
    redis_client.setex(f"confirm:{uuid}", ttl, user_id)


def get_confirm(uuid):
    return redis_client.get(f"confirm:{uuid}")


def delete_confirm(uuid):
    redis_client.delete(f"confirm:{uuid}")
