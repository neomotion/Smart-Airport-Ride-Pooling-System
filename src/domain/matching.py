"""
Windowed Spatial Batching Algorithm
====================================

1. **Spatial Binning**   -- H3 hexagons at resolution 7 (~5.16 km²).
2. **Temporal Batching** -- Pending rides are buffered for a configurable
   window (default 15 s) before the matching engine runs.
3. **Greedy Grouping**   -- Within each cell, iterate pending rides and
   either join an existing group (capacity + luggage + detour OK) or
   create a new group.

Detour constraint (per passenger)
---------------------------------
  total_distance_with_new_stop  <=  (1 + DETOUR_TOLERANCE) x direct_distance

Complexity
----------
Let N = total pending rides, C = # H3 cells with rides,
    m_i = rides in cell i, g_i = active groups in cell i.

* Binning:       O(N)                -- one H3 call per ride
* Grouping:      sum[ O(m_i x g_i) ] -- for each ride, scan groups
* Worst-case:    O(N^2)              -- all rides in one cell, no matches
* Expected:      O(N x G_avg)        -- G_avg << N with spatial binning

**Note:** The greedy heuristic does NOT guarantee global minimisation of
total travel deviation.  An exact solution would require integer
programming (NP-hard).  The greedy approach is chosen for its manageable
O(N x G_avg) runtime.
"""

from __future__ import annotations

import h3

from .distance import haversine_km


def ride_h3_cell(lat: float, lng: float, resolution: int = 7) -> str:
    """Map a geo-point to an H3 hexagonal cell index.  O(1)."""
    return h3.latlng_to_cell(lat, lng, resolution)


def detour_ok(
    existing_pickups: list[tuple[float, float]],
    existing_dropoffs: list[tuple[float, float]],
    new_pickup: tuple[float, float],
    new_dropoff: tuple[float, float],
    tolerance: float = 0.4,
) -> bool:
    """
    Check whether adding a new stop keeps *every* passenger's detour
    within ``(1 + tolerance) x direct_distance``.

    Simplified model
    ~~~~~~~~~~~~~~~~
    The shared route visits all pickups in order then all drop-offs in
    order.  For each passenger *i* the "shared leg" is the distance
    along that route from pickup_i to dropoff_i.

    Complexity: O(k) where k = passengers already in the group.
    """
    all_pickups = existing_pickups + [new_pickup]
    all_dropoffs = existing_dropoffs + [new_dropoff]

    for i, (p, d) in enumerate(zip(all_pickups, all_dropoffs)):
        direct = haversine_km(p[0], p[1], d[0], d[1])
        if direct < 0.1:  # negligible distance -- skip
            continue

        total_shared = _shared_leg(all_pickups, all_dropoffs, i)
        if total_shared > (1 + tolerance) * direct:
            return False

    return True


def _shared_leg(
    pickups: list[tuple[float, float]],
    dropoffs: list[tuple[float, float]],
    passenger_idx: int,
) -> float:
    """
    Estimate the shared-route distance for passenger *passenger_idx*.

    Sequential model: all pickups in index order, then all drop-offs.
    The passenger's leg = sum of hops from their pickup position to
    their drop-off position along the ordered stop list.

    Complexity: O(k) where k = total stops.
    """
    stops = list(pickups) + list(dropoffs)
    start_idx = passenger_idx
    end_idx = len(pickups) + passenger_idx

    total = 0.0
    for j in range(start_idx, end_idx):
        total += haversine_km(
            stops[j][0], stops[j][1],
            stops[j + 1][0], stops[j + 1][1],
        )
    return total
