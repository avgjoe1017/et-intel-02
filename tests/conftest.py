"""
Pytest configuration and fixtures.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from et_intel_core.models.base import Base


@pytest.fixture(scope="function")
def db_session() -> Session:
    """
    Create a test database session.
    
    Uses an in-memory SQLite database for fast testing.
    Each test gets a fresh database.
    """
    # Create in-memory SQLite database
    engine = create_engine("sqlite:///:memory:")
    
    # Create all tables
    Base.metadata.create_all(engine)
    
    # Create session
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    yield session
    
    # Cleanup
    session.close()
    Base.metadata.drop_all(engine)

