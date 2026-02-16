"""Centralised application settings loaded from environment / .env file."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://ridepooling:ridepooling@localhost:5432/ridepooling"
    database_url_sync: str = "postgresql+psycopg2://ridepooling:ridepooling@localhost:5432/ridepooling"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Matching engine
    matching_interval_seconds: int = 15  # temporal batching window
    detour_tolerance: float = 0.4  # 40 % max detour per passenger
    h3_resolution: int = 7  # ~5.16 km² hexagons

    # Pricing
    base_fare: float = 50.0  # INR
    rate_per_km: float = 15.0  # INR / km

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
