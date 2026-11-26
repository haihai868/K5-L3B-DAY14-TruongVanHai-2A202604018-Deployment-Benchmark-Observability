"""
Rate limiting (tiêu chí 7).

Yêu cầu:
  • Mỗi API key tối đa RATE_LIMIT_PER_MINUTE request trong 60 giây (sliding window)
  • Vượt giới hạn → HTTP 429, kèm header Retry-After
  • State lưu trong Redis để mọi worker / instance dùng chung và vẫn còn sau khi restart
"""
import time
from fastapi import HTTPException
from app.config import settings
from app.redis_client import get_redis


def check_rate_limit(key: str) -> None:
    """Kiểm tra rate limit dạng sliding window sử dụng Redis sorted set."""
    redis_client = get_redis()
    if redis_client is None:
        return

    now = time.time()
    window = 60
    redis_key = f"rate_limit:{key}"
    limit = settings.rate_limit_per_minute

    try:
        pipe = redis_client.pipeline()
        pipe.zremrangebyscore(redis_key, 0, now - window)
        pipe.zcard(redis_key)
        results = pipe.execute()
        current_requests = results[1]

        if current_requests >= limit:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: max {limit} requests per minute",
                headers={"Retry-After": "60"},
            )

        pipe = redis_client.pipeline()
        pipe.zadd(redis_key, {f"{now}-{current_requests}": now})
        pipe.expire(redis_key, window + 10)
        pipe.execute()
    except HTTPException:
        raise
    except Exception:
        pass
