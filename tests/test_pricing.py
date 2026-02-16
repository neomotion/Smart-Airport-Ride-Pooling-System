"""Unit tests for the dynamic pricing engine."""

import pytest

from src.domain.pricing import (
    PricingEngine,
    PoolDiscountPricing,
    StandardPricing,
    SurgePricing,
)


class TestPricingStrategies:
    def test_standard_pricing(self):
        strategy = StandardPricing()
        assert strategy.calculate(10.0, 50.0, 15.0) == 200.0  # 50 + 10*15

    def test_surge_pricing_multiplier(self):
        strategy = SurgePricing(surge_multiplier=2.0)
        assert strategy.calculate(10.0, 50.0, 15.0) == 400.0  # 200 * 2

    def test_pool_discount_first_passenger(self):
        strategy = PoolDiscountPricing(passenger_position=1, surge_multiplier=1.0)
        assert strategy.calculate(10.0, 50.0, 15.0) == 200.0  # 0% discount

    def test_pool_discount_second_passenger(self):
        strategy = PoolDiscountPricing(passenger_position=2, surge_multiplier=1.0)
        assert strategy.calculate(10.0, 50.0, 15.0) == 160.0  # 20% off

    def test_pool_discount_third_passenger(self):
        strategy = PoolDiscountPricing(passenger_position=3, surge_multiplier=1.0)
        assert strategy.calculate(10.0, 50.0, 15.0) == 140.0  # 30% off

    def test_pool_discount_caps_at_third(self):
        strat3 = PoolDiscountPricing(passenger_position=3, surge_multiplier=1.0)
        strat5 = PoolDiscountPricing(passenger_position=5, surge_multiplier=1.0)
        assert strat3.calculate(10.0, 50.0, 15.0) == strat5.calculate(10.0, 50.0, 15.0)


class TestPricingEngine:
    def setup_method(self):
        self.engine = PricingEngine(base_fare=50.0, rate_per_km=15.0)

    def test_compute_surge_normal(self):
        assert self.engine.compute_surge(10, 10) == 1.0

    def test_compute_surge_high_demand(self):
        assert self.engine.compute_surge(30, 10) == 3.0  # capped at 3.0

    def test_compute_surge_no_cabs(self):
        assert self.engine.compute_surge(10, 0) == 3.0

    def test_compute_surge_low_demand(self):
        assert self.engine.compute_surge(5, 10) == 1.0  # min 1.0

    def test_calculate_price_returns_positive(self):
        # Mumbai airport → Andheri (~4 km)
        price = self.engine.calculate_price(
            19.0896, 72.8656, 19.1176, 72.8490,
            passenger_position=1, active_requests=10, available_cabs=10,
        )
        assert price > 0

    def test_second_passenger_cheaper(self):
        args = dict(
            pickup_lat=19.0896, pickup_lng=72.8656,
            dropoff_lat=19.1176, dropoff_lng=72.8490,
            active_requests=10, available_cabs=10,
        )
        p1 = self.engine.calculate_price(**args, passenger_position=1)
        p2 = self.engine.calculate_price(**args, passenger_position=2)
        assert p2 < p1  # 20% discount for 2nd
