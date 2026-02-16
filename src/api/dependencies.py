"""FastAPI dependency injection helpers."""

from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database import async_session_factory


async def get_db() -> AsyncSession:  # type: ignore[misc]
    """Yield an async DB session; commit on success, rollback on error."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
