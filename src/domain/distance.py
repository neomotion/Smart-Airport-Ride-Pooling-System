"""
Distance calculation using the Haversine formula.

Assumption
----------
We use great-circle (Haversine) distance instead of a real routing engine
(OSRM / Google Maps) to keep the project self-contained and runnable
locally without external API keys.  In production this module would be
replaced by a routing-service client that returns actual road distances.

Complexity: O(1) per call.
"""

import math

EARTH_RADIUS_KM = 6_371.0


def haversine_km(
    lat1: float, lng1: float, lat2: float, lng2: float
) -> float:
    """Return the great-circle distance in **km** between two points."""
    lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlng / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))
