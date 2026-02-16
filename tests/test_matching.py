"""Unit tests for the matching / detour algorithm."""

import pytest

from src.domain.matching import detour_ok, ride_h3_cell, _shared_leg
from src.domain.distance import haversine_km


class TestHaversine:
    def test_same_point_is_zero(self):
        assert haversine_km(19.0, 72.0, 19.0, 72.0) == 0.0

    def test_known_distance(self):
        # Mumbai airport → Andheri ~3.6 km (approx)
        d = haversine_km(19.0896, 72.8656, 19.1176, 72.8490)
        assert 3.0 < d < 5.0

    def test_symmetric(self):
        d1 = haversine_km(19.0, 72.0, 20.0, 73.0)
        d2 = haversine_km(20.0, 73.0, 19.0, 72.0)
        assert abs(d1 - d2) < 1e-6


class TestH3Cell:
    def test_returns_string(self):
        cell = ride_h3_cell(19.0896, 72.8656, 7)
        assert isinstance(cell, str)
        assert len(cell) > 0

    def test_nearby_points_same_cell(self):
        """Two points 100m apart should be in the same H3 res-7 cell."""
        c1 = ride_h3_cell(19.0896, 72.8656, 7)
        c2 = ride_h3_cell(19.0897, 72.8657, 7)
        assert c1 == c2

    def test_distant_points_different_cell(self):
        """Mumbai vs Delhi should be different cells."""
        c1 = ride_h3_cell(19.0896, 72.8656, 7)
        c2 = ride_h3_cell(28.6139, 77.2090, 7)
        assert c1 != c2


class TestDetourOk:
    def test_single_passenger_always_ok(self):
        """With no existing passengers, detour = 0 => always OK."""
        assert detour_ok([], [], (19.09, 72.87), (19.12, 72.85), tolerance=0.4)

    def test_nearby_dropoffs_accepted(self):
        """Two passengers going nearly the same direction."""
        existing_p = [(19.0896, 72.8656)]
        existing_d = [(19.1176, 72.8490)]
        new_p = (19.0900, 72.8660)
        new_d = (19.1180, 72.8500)
        assert detour_ok(existing_p, existing_d, new_p, new_d, tolerance=0.4)

    def test_opposite_direction_rejected(self):
        """Two passengers going opposite directions => large detour."""
        existing_p = [(19.0896, 72.8656)]
        existing_d = [(19.2000, 72.9500)]  # far north-east
        new_p = (19.0896, 72.8656)
        new_d = (18.9000, 72.7500)  # far south-west
        assert not detour_ok(existing_p, existing_d, new_p, new_d, tolerance=0.4)


class TestSharedLeg:
    def test_single_passenger_equals_direct(self):
        pickups = [(19.09, 72.87)]
        dropoffs = [(19.12, 72.85)]
        leg = _shared_leg(pickups, dropoffs, 0)
        direct = haversine_km(19.09, 72.87, 19.12, 72.85)
        assert abs(leg - direct) < 0.01
