"""
Domain entities with business logic.

Patterns used
-------------
- **State Pattern** on ``Ride``: enforces valid lifecycle transitions
  (PENDING -> MATCHED -> ON_TRIP -> COMPLETED | CANCELLED).
- ``RideGroup.can_accommodate`` encapsulates capacity & luggage invariants.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .enums import RideStatus, RIDE_TRANSITIONS


class InvalidStateTransition(Exception):
    """Raised when a ride status change violates the state machine."""


# ── Value Object ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class Location:
    latitude: float
    longitude: float


# ── Entities ──────────────────────────────────────────────────────────


@dataclass
class Ride:
    id: Optional[int] = None
    user_id: int = 0
    pickup: Location = field(default_factory=lambda: Location(0, 0))
    dropoff: Location = field(default_factory=lambda: Location(0, 0))
    status: RideStatus = RideStatus.PENDING
    seats_requested: int = 1
    luggage_count: int = 0
    ride_group_id: Optional[int] = None
    idempotency_key: Optional[str] = None
    price: Optional[float] = None
    created_at: Optional[datetime] = None

    def transition_to(self, new_status: RideStatus) -> None:
        """Move to *new_status* if the transition is legal, else raise."""
        allowed = RIDE_TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise InvalidStateTransition(
                f"Cannot transition from {self.status} to {new_status}"
            )
        self.status = new_status


@dataclass
class Cab:
    id: Optional[int] = None
    vehicle_type: str = "SEDAN"
    max_seats: int = 4
    max_luggage: int = 3
    current_lat: float = 0.0
    current_lng: float = 0.0
    is_available: bool = True


@dataclass
class RideGroup:
    id: Optional[int] = None
    cab_id: Optional[int] = None
    seats_occupied: int = 0
    luggage_occupied: int = 0
    status: str = "ACTIVE"

    def can_accommodate(
        self, seats: int, luggage: int, max_seats: int, max_luggage: int
    ) -> bool:
        return (
            self.seats_occupied + seats <= max_seats
            and self.luggage_occupied + luggage <= max_luggage
        )

    def add_passenger(self, seats: int, luggage: int) -> None:
        self.seats_occupied += seats
        self.luggage_occupied += luggage

    def remove_passenger(self, seats: int, luggage: int) -> None:
        self.seats_occupied = max(0, self.seats_occupied - seats)
        self.luggage_occupied = max(0, self.luggage_occupied - luggage)
