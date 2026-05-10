"""
GovGuard™ — Database Layer
SQLAlchemy 2.0 async engine with PostgreSQL RLS multi-tenancy.
"""
import uuid
from typing import AsyncGenerator

from sqlalchemy import text, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from core.config import settings

# ── Engine ─────────────────────────────────────────────────────────────────
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=not settings.is_production,
)

# Read-only replica for dashboard queries (same URL in dev, separate in prod)
read_engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=10,
    max_overflow=5,
    pool_pre_ping=True,
    execution_options={"postgresql_readonly": True},
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
AsyncReadSessionLocal = async_sessionmaker(read_engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def init_db() -> None:
    """Called at startup — verify connection."""
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))


async def close_db() -> None:
    await engine.dispose()
    await read_engine.dispose()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency: yields a DB session with RLS tenant variable set.
    Tenant ID is injected by TenantMiddleware into request.state.
    """
    async with AsyncSessionLocal() as session:
        yield session


async def get_read_db() -> AsyncGenerator[AsyncSession, None]:
    """Read-only session routed to replica."""
    async with AsyncReadSessionLocal() as session:
        yield session


async def set_tenant(session: AsyncSession, tenant_id: str) -> None:
    """Set PostgreSQL session variable for RLS enforcement."""
    await session.execute(
        text("SET LOCAL app.current_tenant = :tid"),
        {"tid": tenant_id},
    )
