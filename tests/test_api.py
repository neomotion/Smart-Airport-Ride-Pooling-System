"""
Integration tests for the REST API endpoints.

Uses an in-memory SQLite database with test models that replace PostGIS
Geometry columns with plain String columns.  Repository is overridden
so the routes use test-friendly models.
"""

from __future__ import annotations

from typing import Optional
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.enums import RideStatus
from tests.conftest import (
    TestBase,
    TestCabModel,
    TestRideGroupModel,
    TestRideModel,
    TestSessionFactory,
    TestUserModel,
    test_engine,
)


class _TestRideRepository:
    """Mirrors ``RideRepository`` but uses SQLite-friendly test models."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_ride(self, *, user_id, pickup_lat, pickup_lng,
                          dropoff_lat, dropoff_lng, seats_requested=1,
                          luggage_count=0, idempotency_key=None,
                          status=RideStatus.PENDING):
        ride = TestRideModel(
            user_id=user_id,
            pickup_lat=pickup_lat, pickup_lng=pickup_lng,
            dropoff_lat=dropoff_lat, dropoff_lng=dropoff_lng,
            pickup_point=f"POINT({pickup_lng} {pickup_lat})",
            dropoff_point=f"POINT({dropoff_lng} {dropoff_lat})",
            seats_requested=seats_requested,
            luggage_count=luggage_count,
            idempotency_key=idempotency_key,
            status=status.value if hasattr(status, "value") else status,
        )
        self.session.add(ride)
        await self.session.flush()
        return ride

    async def get_by_id(self, ride_id: int) -> Optional[TestRideModel]:
        return await self.session.get(TestRideModel, ride_id)

    async def get_by_idempotency_key(self, key: str):
        result = await self.session.execute(
            select(TestRideModel).where(TestRideModel.idempotency_key == key)
        )
        return result.scalar_one_or_none()

    async def get_rides_in_group(self, group_id: int):
        result = await self.session.execute(
            select(TestRideModel).where(TestRideModel.ride_group_id == group_id)
        )
        return list(result.scalars().all())


class _TestRideGroupRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, group_id: int):
        return await self.session.get(TestRideGroupModel, group_id)

    async def get_active_groups(self):
        result = await self.session.execute(
            select(TestRideGroupModel).where(TestRideGroupModel.status == "ACTIVE")
        )
        return list(result.scalars().all())


class _TestCabRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, cab_id: int):
        return await self.session.get(TestCabModel, cab_id)


# ── Fixture ───────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def client():
    """AsyncClient backed by SQLite + test models."""
    async with test_engine.begin() as conn:
        await conn.run_sync(TestBase.metadata.create_all)

    # Seed
    async with TestSessionFactory() as session:
        session.add(TestUserModel(name="Test User", email="test@example.com"))
        session.add(TestCabModel(max_seats=4, max_luggage=3, is_available=True))
        await session.commit()

    # Override repos at the module level where routes import them
    with (
        patch(
            "src.workers.matcher.start_matching_loop",
            new_callable=AsyncMock,
        ),
        patch(
            "src.workers.matcher.stop_matching_loop",
            new_callable=AsyncMock,
        ),
        patch(
            "src.api.routes.rides.RideRepository",
            _TestRideRepository,
        ),
        patch(
            "src.api.routes.rides.RideGroupRepository",
            _TestRideGroupRepository,
        ),
        patch(
            "src.api.routes.rides.CabRepository",
            _TestCabRepository,
        ),
        patch(
            "src.api.routes.admin.RideGroupRepository",
            _TestRideGroupRepository,
        ),
        patch(
            "src.api.routes.admin.RideRepository",
            _TestRideRepository,
        ),
    ):
        # DB session dependency
        async def _test_db():
            async with TestSessionFactory() as session:
                try:
                    yield session
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise

        from src.api.app import create_app
        from src.api.dependencies import get_db

        app = create_app()
        app.dependency_overrides[get_db] = _test_db

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    async with test_engine.begin() as conn:
        await conn.run_sync(TestBase.metadata.drop_all)


# ── Tests ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    resp = await client.get("/api/v1/admin/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_create_ride_returns_202(client: AsyncClient):
    resp = await client.post(
        "/api/v1/rides",
        json={
            "user_id": 1,
            "pickup_lat": 19.0896,
            "pickup_lng": 72.8656,
            "dropoff_lat": 19.1176,
            "dropoff_lng": 72.8490,
            "seats_requested": 1,
            "luggage_count": 1,
        },
    )
    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "PENDING"
    assert data["id"] is not None


@pytest.mark.asyncio
async def test_get_ride(client: AsyncClient):
    create_resp = await client.post(
        "/api/v1/rides",
        json={
            "user_id": 1,
            "pickup_lat": 19.09,
            "pickup_lng": 72.87,
            "dropoff_lat": 19.12,
            "dropoff_lng": 72.85,
        },
    )
    ride_id = create_resp.json()["id"]
    resp = await client.get(f"/api/v1/rides/{ride_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == ride_id


@pytest.mark.asyncio
async def test_get_ride_not_found(client: AsyncClient):
    resp = await client.get("/api/v1/rides/9999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cancel_pending_ride(client: AsyncClient):
    create_resp = await client.post(
        "/api/v1/rides",
        json={
            "user_id": 1,
            "pickup_lat": 19.09,
            "pickup_lng": 72.87,
            "dropoff_lat": 19.12,
            "dropoff_lng": 72.85,
        },
    )
    ride_id = create_resp.json()["id"]
    resp = await client.patch(f"/api/v1/rides/{ride_id}/cancel")
    assert resp.status_code == 200
    assert resp.json()["status"] == "CANCELLED"


@pytest.mark.asyncio
async def test_cancel_already_cancelled_ride_fails(client: AsyncClient):
    create_resp = await client.post(
        "/api/v1/rides",
        json={
            "user_id": 1,
            "pickup_lat": 19.09,
            "pickup_lng": 72.87,
            "dropoff_lat": 19.12,
            "dropoff_lng": 72.85,
        },
    )
    ride_id = create_resp.json()["id"]
    await client.patch(f"/api/v1/rides/{ride_id}/cancel")
    resp = await client.patch(f"/api/v1/rides/{ride_id}/cancel")
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_idempotency_key(client: AsyncClient):
    body = {
        "user_id": 1,
        "pickup_lat": 19.09,
        "pickup_lng": 72.87,
        "dropoff_lat": 19.12,
        "dropoff_lng": 72.85,
        "idempotency_key": "unique-key-123",
    }
    resp1 = await client.post("/api/v1/rides", json=body)
    resp2 = await client.post("/api/v1/rides", json=body)
    assert resp1.status_code == 202
    assert resp2.status_code == 202
    assert resp1.json()["id"] == resp2.json()["id"]


@pytest.mark.asyncio
async def test_active_groups_endpoint(client: AsyncClient):
    resp = await client.get("/api/v1/admin/active-groups")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
