"""
Kết nối Redis dùng chung cho rate limiter và cost guard.
"""
import redis
from app.config import settings

r = None


def get_redis():
    global r
    if not settings.redis_url:
        return None
    if r is None:
        try:
            r = redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=1.0,
                socket_timeout=1.0,
            )
        except Exception:
            return None
    return r


def redis_healthy() -> bool:
    """Kiểm tra kết nối Redis cho endpoint GET /ready."""
    if not settings.redis_url:
        return False
    try:
        client = get_redis()
        if client is None:
            return False
        return bool(client.ping())
    except Exception:
        return False
