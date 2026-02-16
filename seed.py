"""
Seed script -- populates the database with sample data for reviewers.

Run after migrations:
    python seed.py

Creates:
  - 10 sample users
  - 15 sample cabs (spread around Mumbai airport area)
  - 8 sample rides (mix of PENDING, MATCHED, COMPLETED)
  - 2 sample ride groups with pre-matched rides
"""

import asyncio
import sys

from sqlalchemy import text
from geoalchemy2.functions import ST_MakePoint

from src.config import settings
from src.infrastructure.database import async_session_factory, engine
from src.infrastructure.models import (
    CabModel,
    RideGroupModel,
    RideModel,
    UserModel,
)
from src.domain.enums import RideStatus, VehicleType

# Mumbai airport coordinates (approx)
AIRPORT_LAT, AIRPORT_LNG = 19.0896, 72.8656


USERS = [
    {"name": "Aarav Sharma", "email": "aarav@example.com", "rating": 4.8},
    {"name": "Priya Patel", "email": "priya@example.com", "rating": 4.9},
    {"name": "Rohan Mehta", "email": "rohan@example.com", "rating": 4.5},
    {"name": "Sneha Gupta", "email": "sneha@example.com", "rating": 4.7},
    {"name": "Vikram Singh", "email": "vikram@example.com", "rating": 4.6},
    {"name": "Ananya Reddy", "email": "ananya@example.com", "rating": 4.9},
    {"name": "Karan Joshi", "email": "karan@example.com", "rating": 4.3},
    {"name": "Meera Nair", "email": "meera@example.com", "rating": 4.8},
    {"name": "Arjun Kumar", "email": "arjun@example.com", "rating": 4.4},
    {"name": "Diya Iyer", "email": "diya@example.com", "rating": 4.7},
]

CABS = [
    # Sedans near airport
    {"vehicle_type": VehicleType.SEDAN, "max_seats": 4, "max_luggage": 3, "lat": 19.0900, "lng": 72.8660},
    {"vehicle_type": VehicleType.SEDAN, "max_seats": 4, "max_luggage": 3, "lat": 19.0880, "lng": 72.8640},
    {"vehicle_type": VehicleType.SEDAN, "max_seats": 4, "max_luggage": 3, "lat": 19.0910, "lng": 72.8670},
    {"vehicle_type": VehicleType.SEDAN, "max_seats": 4, "max_luggage": 3, "lat": 19.0920, "lng": 72.8680},
    {"vehicle_type": VehicleType.SEDAN, "max_seats": 4, "max_luggage": 3, "lat": 19.0870, "lng": 72.8630},
    # SUVs
    {"vehicle_type": VehicleType.SUV, "max_seats": 6, "max_luggage": 5, "lat": 19.0905, "lng": 72.8665},
    {"vehicle_type": VehicleType.SUV, "max_seats": 6, "max_luggage": 5, "lat": 19.0895, "lng": 72.8655},
    {"vehicle_type": VehicleType.SUV, "max_seats": 6, "max_luggage": 5, "lat": 19.0885, "lng": 72.8645},
    # Vans
    {"vehicle_type": VehicleType.VAN, "max_seats": 8, "max_luggage": 8, "lat": 19.0915, "lng": 72.8675},
    {"vehicle_type": VehicleType.VAN, "max_seats": 8, "max_luggage": 8, "lat": 19.0875, "lng": 72.8635},
    # Extra sedans
    {"vehicle_type": VehicleType.SEDAN, "max_seats": 4, "max_luggage": 3, "lat": 19.0930, "lng": 72.8690},
    {"vehicle_type": VehicleType.SEDAN, "max_seats": 4, "max_luggage": 3, "lat": 19.0860, "lng": 72.8620},
    {"vehicle_type": VehicleType.SEDAN, "max_seats": 4, "max_luggage": 3, "lat": 19.0940, "lng": 72.8700},
    {"vehicle_type": VehicleType.SUV, "max_seats": 6, "max_luggage": 5, "lat": 19.0850, "lng": 72.8610},
    {"vehicle_type": VehicleType.VAN, "max_seats": 8, "max_luggage": 8, "lat": 19.0945, "lng": 72.8705},
]


async def seed():
    async with async_session_factory() as session:
        # Check if already seeded
        result = await session.execute(text("SELECT count(*) FROM users"))
        if result.scalar() > 0:
            print("Database already seeded. Skipping.")
            return

        # ── Users ─────────────────────────────────────────────────────
        user_models = []
        for u in USERS:
            m = UserModel(name=u["name"], email=u["email"], rating=u["rating"])
            session.add(m)
            user_models.append(m)
        await session.flush()
        print(f"  Created {len(user_models)} users")

        # ── Cabs ──────────────────────────────────────────────────────
        cab_models = []
        for c in CABS:
            m = CabModel(
                vehicle_type=c["vehicle_type"],
                max_seats=c["max_seats"],
                max_luggage=c["max_luggage"],
                current_location=ST_MakePoint(c["lng"], c["lat"]),
                is_available=True,
            )
            session.add(m)
            cab_models.append(m)
        await session.flush()
        print(f"  Created {len(cab_models)} cabs")

        # ── Ride Groups (pre-matched examples) ────────────────────────
        group1 = RideGroupModel(
            cab_id=cab_models[0].id,
            seats_occupied=2,
            luggage_occupied=2,
            status="ACTIVE",
            h3_cell="872a1072bffffff",  # example H3 cell near Mumbai
        )
        group2 = RideGroupModel(
            cab_id=cab_models[5].id,
            seats_occupied=3,
            luggage_occupied=3,
            status="ACTIVE",
            h3_cell="872a1072bffffff",
        )
        session.add_all([group1, group2])
        await session.flush()
        # Mark assigned cabs as unavailable
        cab_models[0].is_available = False
        cab_models[5].is_available = False
        print("  Created 2 ride groups")

        # ── Rides ─────────────────────────────────────────────────────
        rides_data = [
            # Group 1 rides (MATCHED)
            {
                "user_id": user_models[0].id,
                "pickup": (19.0896, 72.8656),  # Airport
                "dropoff": (19.0760, 72.8777),  # Andheri
                "status": RideStatus.MATCHED,
                "seats": 1, "luggage": 1,
                "group_id": group1.id, "price": 120.50,
            },
            {
                "user_id": user_models[1].id,
                "pickup": (19.0890, 72.8650),
                "dropoff": (19.0730, 72.8800),  # Andheri East
                "status": RideStatus.MATCHED,
                "seats": 1, "luggage": 1,
                "group_id": group1.id, "price": 105.20,
            },
            # Group 2 rides (MATCHED)
            {
                "user_id": user_models[2].id,
                "pickup": (19.0900, 72.8660),
                "dropoff": (19.1176, 72.9060),  # Powai
                "status": RideStatus.MATCHED,
                "seats": 1, "luggage": 1,
                "group_id": group2.id, "price": 180.00,
            },
            {
                "user_id": user_models[3].id,
                "pickup": (19.0895, 72.8655),
                "dropoff": (19.1136, 72.9000),  # near Powai
                "status": RideStatus.MATCHED,
                "seats": 1, "luggage": 1,
                "group_id": group2.id, "price": 150.40,
            },
            {
                "user_id": user_models[4].id,
                "pickup": (19.0892, 72.8652),
                "dropoff": (19.1200, 72.9100),  # IIT Bombay
                "status": RideStatus.MATCHED,
                "seats": 1, "luggage": 1,
                "group_id": group2.id, "price": 140.00,
            },
            # PENDING rides (waiting to be matched)
            {
                "user_id": user_models[5].id,
                "pickup": (19.0888, 72.8648),
                "dropoff": (19.0540, 72.8400),  # Bandra
                "status": RideStatus.PENDING,
                "seats": 2, "luggage": 2,
                "group_id": None, "price": None,
            },
            {
                "user_id": user_models[6].id,
                "pickup": (19.0902, 72.8662),
                "dropoff": (19.0600, 72.8500),  # Santacruz
                "status": RideStatus.PENDING,
                "seats": 1, "luggage": 1,
                "group_id": None, "price": None,
            },
            # COMPLETED ride
            {
                "user_id": user_models[7].id,
                "pickup": (19.0896, 72.8656),
                "dropoff": (19.0200, 72.8500),  # Dadar
                "status": RideStatus.COMPLETED,
                "seats": 1, "luggage": 0,
                "group_id": None, "price": 250.00,
            },
        ]

        for r in rides_data:
            ride = RideModel(
                user_id=r["user_id"],
                pickup_lat=r["pickup"][0],
                pickup_lng=r["pickup"][1],
                dropoff_lat=r["dropoff"][0],
                dropoff_lng=r["dropoff"][1],
                pickup_point=ST_MakePoint(r["pickup"][1], r["pickup"][0]),
                dropoff_point=ST_MakePoint(r["dropoff"][1], r["dropoff"][0]),
                status=r["status"],
                seats_requested=r["seats"],
                luggage_count=r["luggage"],
                ride_group_id=r["group_id"],
                price=r["price"],
            )
            session.add(ride)
        await session.flush()
        print(f"  Created {len(rides_data)} rides")

        await session.commit()
        print("\nSeed complete!")


async def main():
    print("Seeding database...")
    await seed()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
