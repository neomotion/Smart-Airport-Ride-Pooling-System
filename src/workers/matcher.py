"""
Background Matching Worker
==========================

Runs every ``MATCHING_INTERVAL_SECONDS`` (default 15 s).

Concurrency safety
------------------
* **Redis distributed lock** ensures only one instance runs the matching
  cycle at a time across multiple API processes.
* **SELECT … FOR UPDATE** on ``ride_groups`` within each H3 cell prevents
  two concurrent cycles from over-booking the same group.

Algorithm per cycle
-------------------
1. Fetch all PENDING rides.
2. Bin them into H3 cells (spatial binning).
3. For each cell, run greedy grouping: try to add each ride to an
   existing group (capacity + luggage + detour OK) or create a new one.
4. Assign an available cab to each new group.
5. Calculate dynamic price for each newly matched ride.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict

from src.config import settings
from src.domain.enums import RideStatus
from src.domain.matching import detour_ok, ride_h3_cell
from src.domain.pricing import PricingEngine
from src.infrastructure.database import async_session_factory
from src.infrastructure.locks import DistributedLock
from src.infrastructure.models import RideGroupModel
from src.infrastructure.redis_client import get_redis
from src.infrastructure.repositories import (
    CabRepository,
    RideGroupRepository,
    RideRepository,
)

logger = logging.getLogger(__name__)

_task: asyncio.Task | None = None
_stop_event: asyncio.Event | None = None


# ── Public API ────────────────────────────────────────────────────────


async def start_matching_loop() -> None:
    global _task, _stop_event
    _stop_event = asyncio.Event()
    _task = asyncio.create_task(_loop())
    logger.info(
        "Matching worker started (interval=%ds)", settings.matching_interval_seconds
    )


async def stop_matching_loop() -> None:
    if _stop_event:
        _stop_event.set()
    if _task:
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
    logger.info("Matching worker stopped")


# ── Internals ─────────────────────────────────────────────────────────


async def _loop() -> None:
    """Periodic loop: run a matching cycle then sleep."""
    assert _stop_event is not None
    while not _stop_event.is_set():
        try:
            await run_matching_cycle()
        except Exception:
            logger.exception("Unhandled error in matching cycle")
        # Wait for the interval or until stop is signalled
        try:
            await asyncio.wait_for(
                _stop_event.wait(), timeout=settings.matching_interval_seconds
            )
            break
        except asyncio.TimeoutError:
            pass  # next cycle


async def run_matching_cycle() -> int:
    """Execute one matching cycle.  Returns the number of rides matched."""
    redis = await get_redis()
    lock = DistributedLock(redis, "matching_engine", ttl_seconds=60)

    if not await lock.acquire():
        logger.debug("Lock held by another worker – skipping cycle")
        return 0

    matched = 0
    try:
        async with async_session_factory() as session:
            ride_repo = RideRepository(session)
            group_repo = RideGroupRepository(session)
            cab_repo = CabRepository(session)
            pricing = PricingEngine(settings.base_fare, settings.rate_per_km)

            # 1. Fetch pending rides
            pending = await ride_repo.get_pending_rides()
            if not pending:
                await session.commit()
                return 0

            active_requests = len(pending)
            available_cabs = await cab_repo.count_available()

            # 2. Spatial binning
            cell_rides: dict[str, list] = defaultdict(list)
            for ride in pending:
                cell = ride_h3_cell(
                    ride.pickup_lat, ride.pickup_lng, settings.h3_resolution
                )
                cell_rides[cell].append(ride)

            # 3. Greedy grouping per cell
            for cell, rides_in_cell in cell_rides.items():
                groups = await group_repo.get_active_groups_for_update(h3_cell=cell)

                # Pre-load existing ride data for each group
                gdata: dict[int, dict] = {}
                for g in groups:
                    existing = await ride_repo.get_rides_in_group(g.id)
                    gdata[g.id] = {
                        "pickups": [(r.pickup_lat, r.pickup_lng) for r in existing],
                        "dropoffs": [
                            (r.dropoff_lat, r.dropoff_lng) for r in existing
                        ],
                    }

                for ride in rides_in_cell:
                    placed = False

                    for g in groups:
                        cab = (
                            await cab_repo.get_by_id(g.cab_id) if g.cab_id else None
                        )
                        max_s = cab.max_seats if cab else 4
                        max_l = cab.max_luggage if cab else 3

                        # Capacity check
                        if (
                            g.seats_occupied + ride.seats_requested > max_s
                            or g.luggage_occupied + ride.luggage_count > max_l
                        ):
                            continue

                        # Detour check
                        if not detour_ok(
                            gdata[g.id]["pickups"],
                            gdata[g.id]["dropoffs"],
                            (ride.pickup_lat, ride.pickup_lng),
                            (ride.dropoff_lat, ride.dropoff_lng),
                            tolerance=settings.detour_tolerance,
                        ):
                            continue

                        # ✓ Match
                        g.seats_occupied += ride.seats_requested
                        g.luggage_occupied += ride.luggage_count
                        gdata[g.id]["pickups"].append(
                            (ride.pickup_lat, ride.pickup_lng)
                        )
                        gdata[g.id]["dropoffs"].append(
                            (ride.dropoff_lat, ride.dropoff_lng)
                        )

                        position = len(gdata[g.id]["pickups"])
                        ride.status = RideStatus.MATCHED
                        ride.ride_group_id = g.id
                        ride.price = pricing.calculate_price(
                            ride.pickup_lat,
                            ride.pickup_lng,
                            ride.dropoff_lat,
                            ride.dropoff_lng,
                            passenger_position=position,
                            active_requests=active_requests,
                            available_cabs=max(available_cabs, 1),
                        )
                        matched += 1
                        placed = True
                        break

                    if not placed:
                        # Create a new group with the next available cab
                        cabs = await cab_repo.get_available()
                        cab = cabs[0] if cabs else None

                        new_group = RideGroupModel(
                            cab_id=cab.id if cab else None,
                            seats_occupied=ride.seats_requested,
                            luggage_occupied=ride.luggage_count,
                            status="ACTIVE",
                            h3_cell=cell,
                        )
                        new_group = await group_repo.create(new_group)

                        if cab:
                            cab.is_available = False

                        ride.status = RideStatus.MATCHED
                        ride.ride_group_id = new_group.id
                        ride.price = pricing.calculate_price(
                            ride.pickup_lat,
                            ride.pickup_lng,
                            ride.dropoff_lat,
                            ride.dropoff_lng,
                            passenger_position=1,
                            active_requests=active_requests,
                            available_cabs=max(available_cabs, 1),
                        )
                        matched += 1

                        # Track for subsequent iterations in this cycle
                        groups.append(new_group)
                        gdata[new_group.id] = {
                            "pickups": [(ride.pickup_lat, ride.pickup_lng)],
                            "dropoffs": [(ride.dropoff_lat, ride.dropoff_lng)],
                        }

            await session.commit()
            if matched:
                logger.info("Matching cycle: %d rides matched", matched)
    except Exception:
        logger.exception("Error in matching cycle")
    finally:
        await lock.release()

    return matched
