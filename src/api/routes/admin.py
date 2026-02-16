"""
Admin / observability endpoints
===============================

GET /api/v1/admin/active-groups -- list all active ride groups with rides
GET /api/v1/admin/health        -- simple health check
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db
from src.api.middleware import limiter
from src.api.schemas import HealthResponse, RideGroupResponse, RideResponse
from src.infrastructure.repositories import RideGroupRepository, RideRepository

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get(
    "/active-groups",
    response_model=list[RideGroupResponse],
    summary="List all active ride groups with their rides",
)
@limiter.limit("100/minute")
async def get_active_groups(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    group_repo = RideGroupRepository(db)
    ride_repo = RideRepository(db)

    groups = await group_repo.get_active_groups()
    result: list[RideGroupResponse] = []
    for g in groups:
        rides = await ride_repo.get_rides_in_group(g.id)
        ride_dtos = [
            RideResponse(
                id=r.id,
                user_id=r.user_id,
                pickup_lat=r.pickup_lat,
                pickup_lng=r.pickup_lng,
                dropoff_lat=r.dropoff_lat,
                dropoff_lng=r.dropoff_lng,
                status=r.status.value if hasattr(r.status, "value") else r.status,
                seats_requested=r.seats_requested,
                luggage_count=r.luggage_count,
                ride_group_id=r.ride_group_id,
                price=r.price,
                created_at=r.created_at,
            )
            for r in rides
        ]
        result.append(
            RideGroupResponse(
                id=g.id,
                cab_id=g.cab_id,
                seats_occupied=g.seats_occupied,
                luggage_occupied=g.luggage_occupied,
                status=g.status,
                h3_cell=g.h3_cell,
                rides=ride_dtos,
            )
        )
    return result


@router.get("/health", response_model=HealthResponse, summary="Health check")
async def health():
    return HealthResponse()
