import hashlib
import logging

from fastapi import HTTPException, Request, status
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _key(request: Request, login_id: str) -> str:
    address = request.client.host if request.client else "unknown"
    digest = hashlib.sha256(f"{address}:{login_id.strip().lower()}".encode()).hexdigest()
    return f"auth:login:{digest}"


async def enforce_login_rate_limit(request: Request, login_id: str) -> None:
    """Enforce a Redis-backed fixed-window login limit without storing identifiers."""
    if settings.app_env.lower() in {"test", "ci"}:
        return
    client = Redis.from_url(
        settings.redis_url,
        socket_connect_timeout=1,
        socket_timeout=1,
        decode_responses=True,
    )
    try:
        key = _key(request, login_id)
        attempts = await client.incr(key)
        if attempts == 1:
            await client.expire(key, settings.auth_login_window_seconds)
        if attempts > settings.auth_login_max_attempts:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many login attempts. Try again later.",
                headers={"Retry-After": str(settings.auth_login_window_seconds)},
            )
    except RedisError as exc:
        logger.error("Login rate-limit store is unavailable; authentication denied")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service temporarily unavailable",
        ) from exc
    finally:
        await client.aclose()


async def clear_login_rate_limit(request: Request, login_id: str) -> None:
    if settings.app_env.lower() in {"test", "ci"}:
        return
    client = Redis.from_url(
        settings.redis_url,
        socket_connect_timeout=1,
        socket_timeout=1,
        decode_responses=True,
    )
    try:
        await client.delete(_key(request, login_id))
    except RedisError:
        logger.warning("Login rate-limit store is unavailable")
    finally:
        await client.aclose()
