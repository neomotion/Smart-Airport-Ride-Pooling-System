"""Redis async connection pool."""

import redis.asyncio as aioredis

from src.config import settings

_pool = aioredis.ConnectionPool.from_url(
    settings.redis_url, decode_responses=True
)


async def get_redis() -> aioredis.Redis:
    """Return a Redis client backed by the shared connection pool."""
    return aioredis.Redis(connection_pool=_pool)
