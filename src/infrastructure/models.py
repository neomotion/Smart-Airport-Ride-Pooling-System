"""
SQLAlchemy ORM models  (maps to PostgreSQL + PostGIS).

Tables
------
* ``users``        -- registered passengers
* ``cabs``         -- vehicles with capacity limits
* ``rides``        -- individual ride requests
* ``ride_groups``  -- shared-ride groups (one cab, multiple rides)

Indexes
-------
* **GIST** on geometry columns (pickup_point, dropoff_point, current_location)
  for efficient spatial queries.
* **B-Tree** on ``status``, ``user_id``, ``ride_group_id``, ``idempotency_key``
  for fast look-ups used by the matching engine and API.
"""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from geoalchemy2 import Geometry

from .database import Base
from src.domain.enums import RideStatus, VehicleType


class UserModel(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(120), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    rating = Column(Float, default=5.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CabModel(Base):
    __tablename__ = "cabs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vehicle_type = Column(Enum(VehicleType), default=VehicleType.SEDAN)
    max_seats = Column(Integer, default=4, nullable=False)
    max_luggage = Column(Integer, default=3, nullable=False)
    current_location = Column(Geometry("POINT", srid=4326), nullable=True)
    is_available = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_cabs_location", "current_location", postgresql_using="gist"),
        Index("idx_cabs_available", "is_available"),
    )


class RideModel(Base):
    __tablename__ = "rides"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Stored as PostGIS geometry for spatial indexing
    pickup_point = Column(Geometry("POINT", srid=4326), nullable=False)
    dropoff_point = Column(Geometry("POINT", srid=4326), nullable=False)

    # Also stored as plain floats for fast reads (avoids ST_X / ST_Y)
    pickup_lat = Column(Float, nullable=False)
    pickup_lng = Column(Float, nullable=False)
    dropoff_lat = Column(Float, nullable=False)
    dropoff_lng = Column(Float, nullable=False)

    status = Column(Enum(RideStatus), default=RideStatus.PENDING, nullable=False)
    seats_requested = Column(Integer, default=1, nullable=False)
    luggage_count = Column(Integer, default=0, nullable=False)
    ride_group_id = Column(Integer, ForeignKey("ride_groups.id"), nullable=True)
    idempotency_key = Column(String(64), unique=True, nullable=True)
    price = Column(Float, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("idx_rides_pickup", "pickup_point", postgresql_using="gist"),
        Index("idx_rides_dropoff", "dropoff_point", postgresql_using="gist"),
        Index("idx_rides_status", "status"),
        Index("idx_rides_user", "user_id"),
        Index("idx_rides_group", "ride_group_id"),
        Index("idx_rides_idempotency", "idempotency_key"),
    )


class RideGroupModel(Base):
    __tablename__ = "ride_groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cab_id = Column(Integer, ForeignKey("cabs.id"), nullable=True)
    seats_occupied = Column(Integer, default=0, nullable=False)
    luggage_occupied = Column(Integer, default=0, nullable=False)
    status = Column(String(20), default="ACTIVE")
    h3_cell = Column(String(20), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("idx_ride_groups_status", "status"),
        Index("idx_ride_groups_cell", "h3_cell"),
        Index("idx_ride_groups_cab", "cab_id"),
    )
