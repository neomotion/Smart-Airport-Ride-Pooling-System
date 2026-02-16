"""
Redis-based distributed lock.

Used by the matching worker to ensure only one instance runs the
matching cycle at a time.  In production this could be extended to
per-H3-cell locks for parallelism.

Implementation uses SET NX EX for acquire and a Lua script for
atomic check-and-delete on release.
"""

from __future__ import annotations

import uuid

import redis.asyncio as aioredis


class DistributedLock:
    def __init__(
        self, client: aioredis.Redis, key: str, ttl_seconds: int = 30
    ):
        self.redis = client
        self.key = f"lock:{key}"
        self.ttl = ttl_seconds
        self.token = str(uuid.uuid4())

    async def acquire(self) -> bool:
        """Try to acquire. Returns True on success."""
        return bool(
            await self.redis.set(self.key, self.token, nx=True, ex=self.ttl)
        )

    async def release(self) -> None:
        """Release only if we still own the lock (atomic via Lua)."""
        lua = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        await self.redis.eval(lua, 1, self.key, self.token)

    # context-manager support
    async def __aenter__(self):
        acquired = await self.acquire()
        if not acquired:
            raise RuntimeError(f"Could not acquire lock: {self.key}")
        return self

    async def __aexit__(self, *args):
        await self.release()
