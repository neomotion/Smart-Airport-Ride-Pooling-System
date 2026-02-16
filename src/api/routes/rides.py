"""
Ride endpoints
==============

POST /api/v1/rides           -- create a ride request (returns 202 Accepted)
GET  /api/v1/rides/{ride_id} -- check match status and price
PATCH /api/v1/rides/{ride_id}/cancel -- cancel a ride
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db
from src.api.middleware import limiter
from src.api.schemas import RideCreateRequest, RideResponse
from src.domain.enums import RIDE_TRANSITIONS, RideStatus
from src.infrastructure.repositories import (
    CabRepository,
    RideGroupRepository,
    RideRepository,
)

router = APIRouter(prefix="/rides", tags=["rides"])


@router.post(
    "",
    status_code=202,
    response_model=RideResponse,
    summary="Create a ride request",
    responses={202: {"description": "Ride request accepted; matching is async."}},
)
@limiter.limit("100/minute")
async def create_ride(
    request: Request,
    body: RideCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    repo = RideRepository(db)

    # ── Idempotency guard ─────────────────────────────────────────
    if body.idempotency_key:
        existing = await repo.get_by_idempotency_key(body.idempotency_key)
        if existing:
            return existing

    ride = await repo.create_ride(
        user_id=body.user_id,
        pickup_lat=body.pickup_lat,
        pickup_lng=body.pickup_lng,
        dropoff_lat=body.dropoff_lat,
        dropoff_lng=body.dropoff_lng,
        seats_requested=body.seats_requested,
        luggage_count=body.luggage_count,
        idempotency_key=body.idempotency_key,
    )
    return ride


@router.get(
    "/{ride_id}",
    response_model=RideResponse,
    summary="Get ride status and price",
)
@limiter.limit("100/minute")
async def get_ride(
    request: Request,
    ride_id: int,
    db: AsyncSession = Depends(get_db),
):
    ride = await RideRepository(db).get_by_id(ride_id)
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")
    return ride


@router.patch(
    "/{ride_id}/cancel",
    response_model=RideResponse,
    summary="Cancel a ride",
    description=(
        "Transitions a PENDING or MATCHED ride to CANCELLED. "
        "If the ride was in a group, the group's capacity is freed."
    ),
)
@limiter.limit("100/minute")
async def cancel_ride(
    request: Request,
    ride_id: int,
    db: AsyncSession = Depends(get_db),
):
    ride_repo = RideRepository(db)
    group_repo = RideGroupRepository(db)

    ride = await ride_repo.get_by_id(ride_id)
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")

    allowed = RIDE_TRANSITIONS.get(RideStatus(ride.status), set())
    if RideStatus.CANCELLED not in allowed:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot cancel ride in status {ride.status}",
        )

    # Free group capacity if the ride was matched
    if ride.ride_group_id:
        group = await group_repo.get_by_id(ride.ride_group_id)
        if group:
            group.seats_occupied = max(
                0, group.seats_occupied - ride.seats_requested
            )
            group.luggage_occupied = max(
                0, group.luggage_occupied - ride.luggage_count
            )
            # If no active rides remain, deactivate group & free cab
            remaining = await ride_repo.get_rides_in_group(group.id)
            active = [
                r
                for r in remaining
                if r.id != ride_id
                and RideStatus(r.status) != RideStatus.CANCELLED
            ]
            if not active:
                group.status = "INACTIVE"
                if group.cab_id:
                    cab = await CabRepository(db).get_by_id(group.cab_id)
                    if cab:
                        cab.is_available = True

    ride.status = RideStatus.CANCELLED
    ride.ride_group_id = None
    return ride
