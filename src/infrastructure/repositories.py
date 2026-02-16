"""
Repository Pattern -- abstracts DB access so domain logic stays DB-agnostic.

Each repository receives an ``AsyncSession`` (unit-of-work) and exposes
domain-relevant queries only.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .models import CabModel, RideGroupModel, RideModel, UserModel
from src.domain.enums import RideStatus


class RideRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, ride: RideModel) -> RideModel:
        self.session.add(ride)
        await self.session.flush()
        return ride

    async def create_ride(
        self,
        *,
        user_id: int,
        pickup_lat: float,
        pickup_lng: float,
        dropoff_lat: float,
        dropoff_lng: float,
        seats_requested: int = 1,
        luggage_count: int = 0,
        idempotency_key: str | None = None,
        status: RideStatus = RideStatus.PENDING,
    ) -> RideModel:
        """Create a ride with proper PostGIS geometry columns."""
        from geoalchemy2.functions import ST_MakePoint

        ride = RideModel(
            user_id=user_id,
            pickup_lat=pickup_lat,
            pickup_lng=pickup_lng,
            dropoff_lat=dropoff_lat,
            dropoff_lng=dropoff_lng,
            pickup_point=ST_MakePoint(pickup_lng, pickup_lat),
            dropoff_point=ST_MakePoint(dropoff_lng, dropoff_lat),
            seats_requested=seats_requested,
            luggage_count=luggage_count,
            idempotency_key=idempotency_key,
            status=status,
        )
        self.session.add(ride)
        await self.session.flush()
        return ride

    async def get_by_id(self, ride_id: int) -> Optional[RideModel]:
        return await self.session.get(RideModel, ride_id)

    async def get_by_idempotency_key(self, key: str) -> Optional[RideModel]:
        result = await self.session.execute(
            select(RideModel).where(RideModel.idempotency_key == key)
        )
        return result.scalar_one_or_none()

    async def get_pending_rides(self) -> list[RideModel]:
        result = await self.session.execute(
            select(RideModel)
            .where(RideModel.status == RideStatus.PENDING)
            .order_by(RideModel.created_at)
        )
        return list(result.scalars().all())

    async def get_rides_in_group(self, group_id: int) -> list[RideModel]:
        result = await self.session.execute(
            select(RideModel).where(RideModel.ride_group_id == group_id)
        )
        return list(result.scalars().all())

    async def count_pending(self) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(RideModel)
            .where(RideModel.status == RideStatus.PENDING)
        )
        return result.scalar() or 0


class RideGroupRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, group: RideGroupModel) -> RideGroupModel:
        self.session.add(group)
        await self.session.flush()
        return group

    async def get_by_id(self, group_id: int) -> Optional[RideGroupModel]:
        return await self.session.get(RideGroupModel, group_id)

    async def get_active_groups_for_update(
        self, h3_cell: str | None = None
    ) -> list[RideGroupModel]:
        """SELECT ... FOR UPDATE to prevent concurrent modifications."""
        query = (
            select(RideGroupModel)
            .where(RideGroupModel.status == "ACTIVE")
            .with_for_update()
        )
        if h3_cell:
            query = query.where(RideGroupModel.h3_cell == h3_cell)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_active_groups(self) -> list[RideGroupModel]:
        result = await self.session.execute(
            select(RideGroupModel).where(RideGroupModel.status == "ACTIVE")
        )
        return list(result.scalars().all())


class CabRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_available(self) -> list[CabModel]:
        result = await self.session.execute(
            select(CabModel).where(CabModel.is_available.is_(True))
        )
        return list(result.scalars().all())

    async def get_by_id(self, cab_id: int) -> Optional[CabModel]:
        return await self.session.get(CabModel, cab_id)

    async def count_available(self) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(CabModel)
            .where(CabModel.is_available.is_(True))
        )
        return result.scalar() or 0


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: int) -> Optional[UserModel]:
        return await self.session.get(UserModel, user_id)
