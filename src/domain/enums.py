"""Domain enumerations and state-transition rules."""

import enum


class RideStatus(str, enum.Enum):
    PENDING = "PENDING"
    MATCHED = "MATCHED"
    ON_TRIP = "ON_TRIP"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


# State machine: maps current status -> set of valid next statuses
RIDE_TRANSITIONS: dict[RideStatus, set[RideStatus]] = {
    RideStatus.PENDING: {RideStatus.MATCHED, RideStatus.CANCELLED},
    RideStatus.MATCHED: {RideStatus.ON_TRIP, RideStatus.CANCELLED},
    RideStatus.ON_TRIP: {RideStatus.COMPLETED},
    RideStatus.COMPLETED: set(),
    RideStatus.CANCELLED: set(),
}


class VehicleType(str, enum.Enum):
    SEDAN = "SEDAN"
    SUV = "SUV"
    VAN = "VAN"
