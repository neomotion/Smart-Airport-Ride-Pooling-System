"""
FastAPI application factory.

* Registers routes for rides and admin.
* Starts / stops the background matching worker via lifespan events.
* Applies rate-limiting middleware.
* Swagger / OpenAPI UI available at ``/docs``.
"""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from src.api.middleware import limiter
from src.api.routes import admin, rides
from src.workers import matcher as _matcher

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the matching worker on startup; stop on shutdown."""
    await _matcher.start_matching_loop()
    yield
    await _matcher.stop_matching_loop()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Smart Airport Ride Pooling API",
        description=(
            "Groups airport passengers into shared cabs while optimising "
            "routes and pricing.  Supports real-time cancellations, "
            "dynamic surge pricing, and concurrent operations."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )

    # Rate limiter
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Routers
    app.include_router(rides.router, prefix="/api/v1")
    app.include_router(admin.router, prefix="/api/v1")

    return app
