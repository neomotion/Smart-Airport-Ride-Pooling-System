"""Pydantic request / response schemas for the REST API."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Requests ──────────────────────────────────────────────────────────


class RideCreateRequest(BaseModel):
    user_id: int
    pickup_lat: float = Field(..., ge=-90, le=90)
    pickup_lng: float = Field(..., ge=-180, le=180)
    dropoff_lat: float = Field(..., ge=-90, le=90)
    dropoff_lng: float = Field(..., ge=-180, le=180)
    seats_requested: int = Field(1, ge=1, le=6)
    luggage_count: int = Field(0, ge=0, le=10)
    idempotency_key: Optional[str] = Field(
        None,
        max_length=64,
        description="Client-generated UUID to prevent double-booking on retries.",
    )


# ── Responses ─────────────────────────────────────────────────────────


class RideResponse(BaseModel):
    id: int
    user_id: int
    pickup_lat: float
    pickup_lng: float
    dropoff_lat: float
    dropoff_lng: float
    status: str
    seats_requested: int
    luggage_count: int
    ride_group_id: Optional[int] = None
    price: Optional[float] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class RideGroupResponse(BaseModel):
    id: int
    cab_id: Optional[int] = None
    seats_occupied: int
    luggage_occupied: int
    status: str
    h3_cell: Optional[str] = None
    rides: list[RideResponse] = []

    model_config = {"from_attributes": True}


class HealthResponse(BaseModel):
    status: str = "ok"


class ErrorResponse(BaseModel):
    detail: str
