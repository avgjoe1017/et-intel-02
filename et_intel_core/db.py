"""
Database connection and session management.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from et_intel_core.config import settings
from et_intel_core.models.base import Base

# Create engine
engine = create_engine(
    settings.database_url,
    echo=False,  # Set to True for SQL query logging
    pool_pre_ping=True,  # Verify connections before using
    pool_size=5,
    max_overflow=10
)

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def get_session() -> Session:
    """
    Get a database session.
    
    Usage:
        session = get_session()
        try:
            # Do work
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    """
    return SessionLocal()


def init_db() -> None:
    """
    Initialize database tables.
    
    Note: In production, use Alembic migrations instead.
    This is useful for testing and development.
    """
    Base.metadata.create_all(bind=engine)


def drop_db() -> None:
    """
    Drop all database tables.
    
    WARNING: This will delete all data!
    Only use in development/testing.
    """
    Base.metadata.drop_all(bind=engine)

