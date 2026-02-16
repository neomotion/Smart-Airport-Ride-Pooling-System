"""Initial schema with PostGIS extension and all core tables.

Revision ID: 001
Create Date: 2026-02-15
"""

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry


revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable PostGIS extension
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # ── users ─────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("rating", sa.Float, default=5.0),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # ── cabs ──────────────────────────────────────────────────────────
    op.create_table(
        "cabs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "vehicle_type",
            sa.Enum("SEDAN", "SUV", "VAN", name="vehicletype"),
            default="SEDAN",
        ),
        sa.Column("max_seats", sa.Integer, default=4, nullable=False),
        sa.Column("max_luggage", sa.Integer, default=3, nullable=False),
        sa.Column(
            "current_location", Geometry("POINT", srid=4326), nullable=True
        ),
        sa.Column("is_available", sa.Boolean, default=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "idx_cabs_location",
        "cabs",
        ["current_location"],
        postgresql_using="gist",
    )
    op.create_index("idx_cabs_available", "cabs", ["is_available"])

    # ── ride_groups ───────────────────────────────────────────────────
    op.create_table(
        "ride_groups",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("cab_id", sa.Integer, sa.ForeignKey("cabs.id"), nullable=True),
        sa.Column("seats_occupied", sa.Integer, default=0, nullable=False),
        sa.Column("luggage_occupied", sa.Integer, default=0, nullable=False),
        sa.Column("status", sa.String(20), default="ACTIVE"),
        sa.Column("h3_cell", sa.String(20), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index("idx_ride_groups_status", "ride_groups", ["status"])
    op.create_index("idx_ride_groups_cell", "ride_groups", ["h3_cell"])
    op.create_index("idx_ride_groups_cab", "ride_groups", ["cab_id"])

    # ── rides ─────────────────────────────────────────────────────────
    op.create_table(
        "rides",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column(
            "pickup_point", Geometry("POINT", srid=4326), nullable=False
        ),
        sa.Column(
            "dropoff_point", Geometry("POINT", srid=4326), nullable=False
        ),
        sa.Column("pickup_lat", sa.Float, nullable=False),
        sa.Column("pickup_lng", sa.Float, nullable=False),
        sa.Column("dropoff_lat", sa.Float, nullable=False),
        sa.Column("dropoff_lng", sa.Float, nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "MATCHED",
                "ON_TRIP",
                "COMPLETED",
                "CANCELLED",
                name="ridestatus",
            ),
            default="PENDING",
            nullable=False,
        ),
        sa.Column("seats_requested", sa.Integer, default=1, nullable=False),
        sa.Column("luggage_count", sa.Integer, default=0, nullable=False),
        sa.Column(
            "ride_group_id",
            sa.Integer,
            sa.ForeignKey("ride_groups.id"),
            nullable=True,
        ),
        sa.Column("idempotency_key", sa.String(64), unique=True, nullable=True),
        sa.Column("price", sa.Float, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "idx_rides_pickup", "rides", ["pickup_point"], postgresql_using="gist"
    )
    op.create_index(
        "idx_rides_dropoff", "rides", ["dropoff_point"], postgresql_using="gist"
    )
    op.create_index("idx_rides_status", "rides", ["status"])
    op.create_index("idx_rides_user", "rides", ["user_id"])
    op.create_index("idx_rides_group", "rides", ["ride_group_id"])
    op.create_index("idx_rides_idempotency", "rides", ["idempotency_key"])


def downgrade() -> None:
    op.drop_table("rides")
    op.drop_table("ride_groups")
    op.drop_table("cabs")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS ridestatus")
    op.execute("DROP TYPE IF EXISTS vehicletype")
