"""
Dynamic Pricing Engine  (Strategy Pattern)
==========================================

Formula
-------
Price = (Base_Fare + Distance x Rate_Per_KM) x Surge_Multiplier x (1 - Pooling_Discount)

* **Surge_Multiplier** = clamp(active_requests / available_cabs, 1.0, 3.0)
* **Pooling_Discount**: 0 % for 1st passenger, 20 % for 2nd, 30 % for 3rd+

Complexity: O(1) per price calculation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .distance import haversine_km


# ── Strategy hierarchy ────────────────────────────────────────────────


class PricingStrategy(ABC):
    @abstractmethod
    def calculate(
        self, distance_km: float, base_fare: float, rate_per_km: float
    ) -> float: ...


class StandardPricing(PricingStrategy):
    def calculate(
        self, distance_km: float, base_fare: float, rate_per_km: float
    ) -> float:
        return base_fare + distance_km * rate_per_km


class SurgePricing(PricingStrategy):
    def __init__(self, surge_multiplier: float = 1.0):
        self.surge_multiplier = surge_multiplier

    def calculate(
        self, distance_km: float, base_fare: float, rate_per_km: float
    ) -> float:
        return (base_fare + distance_km * rate_per_km) * self.surge_multiplier


class PoolDiscountPricing(PricingStrategy):
    """Applies surge *and* a position-based pooling discount."""

    DISCOUNTS = {1: 0.0, 2: 0.20, 3: 0.30}

    def __init__(self, passenger_position: int, surge_multiplier: float = 1.0):
        self.discount = self.DISCOUNTS.get(min(passenger_position, 3), 0.30)
        self.surge_multiplier = surge_multiplier

    def calculate(
        self, distance_km: float, base_fare: float, rate_per_km: float
    ) -> float:
        raw = (base_fare + distance_km * rate_per_km) * self.surge_multiplier
        return round(raw * (1 - self.discount), 2)


# ── Engine facade ─────────────────────────────────────────────────────


class PricingEngine:
    """High-level API used by the matching worker and the API layer."""

    def __init__(self, base_fare: float = 50.0, rate_per_km: float = 15.0):
        self.base_fare = base_fare
        self.rate_per_km = rate_per_km

    @staticmethod
    def compute_surge(active_requests: int, available_cabs: int) -> float:
        if available_cabs <= 0:
            return 3.0
        return min(3.0, max(1.0, active_requests / available_cabs))

    def calculate_price(
        self,
        pickup_lat: float,
        pickup_lng: float,
        dropoff_lat: float,
        dropoff_lng: float,
        passenger_position: int = 1,
        active_requests: int = 1,
        available_cabs: int = 1,
    ) -> float:
        distance = haversine_km(pickup_lat, pickup_lng, dropoff_lat, dropoff_lng)
        surge = self.compute_surge(active_requests, available_cabs)
        strategy = PoolDiscountPricing(passenger_position, surge)
        return strategy.calculate(distance, self.base_fare, self.rate_per_km)
