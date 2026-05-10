"""GovGuard™ — Redis Cache Layer"""
import json
from typing import Any, Optional
import redis.asyncio as aioredis
from core.config import settings

redis_client: Optional[aioredis.Redis] = None


async def init_redis() -> None:
    global redis_client
    redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    await redis_client.ping()


async def close_redis() -> None:
    if redis_client:
        await redis_client.aclose()


async def cache_get(key: str) -> Optional[Any]:
    if not redis_client:
        return None
    value = await redis_client.get(key)
    return json.loads(value) if value else None


async def cache_set(key: str, value: Any, ttl: int = 300) -> None:
    if not redis_client:
        return
    await redis_client.setex(key, ttl, json.dumps(value))


async def cache_delete(key: str) -> None:
    if redis_client:
        await redis_client.delete(key)


async def cache_delete_pattern(pattern: str) -> None:
    if not redis_client:
        return
    keys = await redis_client.keys(pattern)
    if keys:
        await redis_client.delete(*keys)
