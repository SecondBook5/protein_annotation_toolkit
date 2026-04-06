"""
Database session management.

Provides session factory and context managers for database operations.
"""

from contextlib import asynccontextmanager, contextmanager
from typing import AsyncGenerator, Generator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from protein_annotation_toolkit.config import get_settings


def get_sync_engine():
    """
    Create synchronous SQLAlchemy engine.

    Used for Alembic migrations and non-async operations.

    Returns:
        Engine: SQLAlchemy sync engine
    """
    settings = get_settings()
    # Convert async URL to sync URL for synchronous engine
    database_url = str(settings.database_url).replace("+psycopg", "")
    # Create engine with connection pooling
    engine = create_engine(
        database_url,
        pool_pre_ping=True,  # Verify connections before using
        pool_size=5,  # Connection pool size
        max_overflow=10,  # Max connections above pool_size
        echo=False,  # Set to True for SQL query logging
    )
    return engine


def get_async_engine():
    """
    Create async SQLAlchemy engine.

    Used for async database operations in the application.

    Returns:
        AsyncEngine: SQLAlchemy async engine
    """
    settings = get_settings()
    database_url = str(settings.database_url)

    # Create async engine with connection pooling
    engine = create_async_engine(
        database_url,
        pool_pre_ping=True,  # Verify connections before using
        pool_size=10,  # Larger pool for async operations
        max_overflow=20,  # Allow more overflow for async
        echo=False,  # Set to True for SQL query logging
    )
    return engine


# Lazy session factories - create on first use
_sync_session_local = None
_async_session_local = None


def get_sync_session_local():
    """Get or create sync session factory."""
    global _sync_session_local
    if _sync_session_local is None:
        _sync_session_local = sessionmaker(
            bind=get_sync_engine(),
            class_=Session,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _sync_session_local


def get_async_session_local():
    """Get or create async session factory."""
    global _async_session_local
    if _async_session_local is None:
        _async_session_local = async_sessionmaker(
            bind=get_async_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _async_session_local




@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    Context manager for synchronous database sessions.

    Automatically handles commit/rollback and session cleanup.

    Usage:
        with get_db_session() as session:
            protein = session.query(Protein).first()

    Yields:
        Session: SQLAlchemy synchronous session
    """
    session_local = get_sync_session_local()
    session = session_local()
    try:
        yield session
        # Commit if no exceptions occurred
        session.commit()
    except Exception:
        # Rollback on any exception
        session.rollback()
        raise
    finally:
        # Always close the session
        session.close()


@asynccontextmanager
async def get_async_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for asynchronous database sessions.

    Automatically handles commit/rollback and session cleanup.

    Usage:
        async with get_async_db_session() as session:
            result = await session.execute(select(Protein))
            proteins = result.scalars().all()

    Yields:
        AsyncSession: SQLAlchemy asynchronous session
    """
    session_local = get_async_session_local()
    session = session_local()
    try:
        yield session
        # Commit if no exceptions occurred
        await session.commit()
    except Exception:
        # Rollback on any exception
        await session.rollback()
        raise
    finally:
        # Always close the session
        await session.close()


async def init_db() -> None:
    """
    Initialize database tables.

    Creates all tables defined in models. This is used for initial setup.
    For production, use Alembic migrations instead.
    """
    from protein_annotation_toolkit.db.base import Base

    # Create async engine
    engine = get_async_engine()

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_db() -> None:
    """
    Drop all database tables.

    WARNING: This will delete all data!
    Use with caution - only for testing/development.
    """
    from protein_annotation_toolkit.db.base import Base

    # Create async engine
    engine = get_async_engine()

    # Drop all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
