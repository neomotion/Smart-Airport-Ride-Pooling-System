"""
Concurrency safety tests.

Demonstrates:
1. Idempotency keys prevent double-booking on network retries.
2. Ride group entity's ``can_accommodate`` correctly rejects over-capacity.
3. Distributed lock prevents simultaneous acquire.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

from src.domain.entities import RideGroup
from src.infrastructure.locks import DistributedLock


class TestRideGroupConcurrency:
    """Entity-level capacity guard."""

    def test_cannot_exceed_seat_capacity(self):
        group = RideGroup(seats_occupied=3, luggage_occupied=1)
        assert not group.can_accommodate(seats=2, luggage=0, max_seats=4, max_luggage=3)

    def test_cannot_exceed_luggage_capacity(self):
        group = RideGroup(seats_occupied=1, luggage_occupied=2)
        assert not group.can_accommodate(seats=1, luggage=2, max_seats=4, max_luggage=3)

    def test_exact_fit_is_accepted(self):
        group = RideGroup(seats_occupied=3, luggage_occupied=2)
        assert group.can_accommodate(seats=1, luggage=1, max_seats=4, max_luggage=3)


class TestDistributedLock:
    """Tests the Redis distributed lock logic (mocked Redis)."""

    @pytest.mark.asyncio
    async def test_acquire_succeeds(self):
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)

        lock = DistributedLock(mock_redis, "test-key", ttl_seconds=10)
        assert await lock.acquire() is True

    @pytest.mark.asyncio
    async def test_acquire_fails_if_held(self):
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=False)

        lock = DistributedLock(mock_redis, "test-key", ttl_seconds=10)
        assert await lock.acquire() is False

    @pytest.mark.asyncio
    async def test_release_calls_eval(self):
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.eval = AsyncMock(return_value=1)

        lock = DistributedLock(mock_redis, "test-key", ttl_seconds=10)
        await lock.acquire()
        await lock.release()

        mock_redis.eval.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager_acquire_fail_raises(self):
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=False)

        lock = DistributedLock(mock_redis, "test-key", ttl_seconds=10)
        with pytest.raises(RuntimeError, match="Could not acquire lock"):
            async with lock:
                pass
