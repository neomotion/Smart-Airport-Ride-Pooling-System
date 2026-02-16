"""Unit tests for ride entity state transitions (State Pattern)."""

import pytest

from src.domain.entities import Ride, InvalidStateTransition
from src.domain.enums import RideStatus


class TestRideStateMachine:
    def test_initial_status_is_pending(self):
        ride = Ride()
        assert ride.status == RideStatus.PENDING

    # ── Valid transitions ─────────────────────────────────────────

    def test_pending_to_matched(self):
        ride = Ride(status=RideStatus.PENDING)
        ride.transition_to(RideStatus.MATCHED)
        assert ride.status == RideStatus.MATCHED

    def test_pending_to_cancelled(self):
        ride = Ride(status=RideStatus.PENDING)
        ride.transition_to(RideStatus.CANCELLED)
        assert ride.status == RideStatus.CANCELLED

    def test_matched_to_on_trip(self):
        ride = Ride(status=RideStatus.MATCHED)
        ride.transition_to(RideStatus.ON_TRIP)
        assert ride.status == RideStatus.ON_TRIP

    def test_matched_to_cancelled(self):
        ride = Ride(status=RideStatus.MATCHED)
        ride.transition_to(RideStatus.CANCELLED)
        assert ride.status == RideStatus.CANCELLED

    def test_on_trip_to_completed(self):
        ride = Ride(status=RideStatus.ON_TRIP)
        ride.transition_to(RideStatus.COMPLETED)
        assert ride.status == RideStatus.COMPLETED

    # ── Invalid transitions ───────────────────────────────────────

    def test_pending_to_completed_fails(self):
        ride = Ride(status=RideStatus.PENDING)
        with pytest.raises(InvalidStateTransition):
            ride.transition_to(RideStatus.COMPLETED)

    def test_completed_to_anything_fails(self):
        ride = Ride(status=RideStatus.COMPLETED)
        with pytest.raises(InvalidStateTransition):
            ride.transition_to(RideStatus.PENDING)

    def test_cancelled_to_anything_fails(self):
        ride = Ride(status=RideStatus.CANCELLED)
        with pytest.raises(InvalidStateTransition):
            ride.transition_to(RideStatus.PENDING)

    def test_on_trip_to_cancelled_fails(self):
        """Once on-trip, can only complete -- not cancel."""
        ride = Ride(status=RideStatus.ON_TRIP)
        with pytest.raises(InvalidStateTransition):
            ride.transition_to(RideStatus.CANCELLED)
