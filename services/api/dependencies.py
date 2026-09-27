"""Shared FastAPI dependencies."""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from database.session import create_engine, create_session_factory

engine = create_engine(settings.database_url)
session_factory = create_session_factory(engine)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with session_factory() as session:
        yield session
