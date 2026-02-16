"""
Shared test fixtures.

Uses an in-memory SQLite database (via aiosqlite) so tests run without
Docker / PostgreSQL / Redis.  PostGIS-specific features (Geometry columns)
are mocked by using plain String columns in the test models.
"""

import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Column, DateTime, Float, Integer, String, Boolean, ForeignKey, func
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


# ── Test DB (SQLite in-memory) ────────────────────────────────────────

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DB_URL, echo=False)
TestSessionFactory = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


class TestBase(DeclarativeBase):
    pass


# Mirror the production models but without PostGIS Geometry columns
# (SQLite doesn't support them).

class TestUserModel(TestBase):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(120), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    rating = Column(Float, default=5.0)
    created_at = Column(DateTime, server_default=func.now())


class TestCabModel(TestBase):
    __tablename__ = "cabs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    vehicle_type = Column(String(20), default="SEDAN")
    max_seats = Column(Integer, default=4, nullable=False)
    max_luggage = Column(Integer, default=3, nullable=False)
    current_location = Column(String, nullable=True)  # stub for Geometry
    is_available = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


class TestRideGroupModel(TestBase):
    __tablename__ = "ride_groups"
    id = Column(Integer, primary_key=True, autoincrement=True)
    cab_id = Column(Integer, ForeignKey("cabs.id"), nullable=True)
    seats_occupied = Column(Integer, default=0, nullable=False)
    luggage_occupied = Column(Integer, default=0, nullable=False)
    status = Column(String(20), default="ACTIVE")
    h3_cell = Column(String(20), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now())


class TestRideModel(TestBase):
    __tablename__ = "rides"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    pickup_point = Column(String, nullable=True)  # stub for Geometry
    dropoff_point = Column(String, nullable=True)  # stub for Geometry
    pickup_lat = Column(Float, nullable=False)
    pickup_lng = Column(Float, nullable=False)
    dropoff_lat = Column(Float, nullable=False)
    dropoff_lng = Column(Float, nullable=False)
    status = Column(String(20), default="PENDING", nullable=False)
    seats_requested = Column(Integer, default=1, nullable=False)
    luggage_count = Column(Integer, default=0, nullable=False)
    ride_group_id = Column(Integer, ForeignKey("ride_groups.id"), nullable=True)
    idempotency_key = Column(String(64), unique=True, nullable=True)
    price = Column(Float, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now())


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create tables, yield a session, then drop everything."""
    async with test_engine.begin() as conn:
        await conn.run_sync(TestBase.metadata.create_all)

    async with TestSessionFactory() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(TestBase.metadata.drop_all)
