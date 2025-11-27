"""
Pytest configuration and fixtures.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy import JSON
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler
from datetime import datetime
import uuid

from et_intel_core.models.base import Base
from et_intel_core.models import (
    Post, Comment, MonitoredEntity, ExtractedSignal, DiscoveredEntity
)
from et_intel_core.models.enums import PlatformType, EntityType, SignalType, ContextType


# Patch SQLite TypeCompiler to handle JSONB as JSON
_original_process = None
_original_visit_jsonb = None

def _setup_sqlite_jsonb_support():
    """Set up JSONB support for SQLite by converting it to JSON."""
    global _original_process, _original_visit_jsonb
    
    # Store original process method
    _original_process = SQLiteTypeCompiler.process
    
    # Wrap process to intercept JSONB types
    def process(self, type_, **kw):
        """Process type, converting JSONB to JSON for SQLite."""
        from sqlalchemy.dialects.postgresql import JSONB
        
        # If it's a JSONB type, convert to JSON
        if isinstance(type_, JSONB):
            return self.visit_JSON(JSON(), **kw)
        
        # Otherwise use original process
        return _original_process(self, type_, **kw)
    
    SQLiteTypeCompiler.process = process
    
    # Also add visit_jsonb method for direct calls
    if not hasattr(SQLiteTypeCompiler, 'visit_jsonb'):
        def visit_jsonb(self, type_, **kw):
            """Convert JSONB to JSON for SQLite compatibility."""
            return self.visit_JSON(JSON(), **kw)
        
        SQLiteTypeCompiler.visit_jsonb = visit_jsonb
        _original_visit_jsonb = None
    else:
        _original_visit_jsonb = SQLiteTypeCompiler.visit_jsonb


def _teardown_sqlite_jsonb_support():
    """Restore original JSONB handling."""
    global _original_process, _original_visit_jsonb
    
    if _original_process is not None:
        SQLiteTypeCompiler.process = _original_process
    
    if _original_visit_jsonb is not None:
        SQLiteTypeCompiler.visit_jsonb = _original_visit_jsonb
    elif hasattr(SQLiteTypeCompiler, 'visit_jsonb'):
        delattr(SQLiteTypeCompiler, 'visit_jsonb')


@pytest.fixture(scope="function")
def db_session() -> Session:
    """
    Create a test database session.
    
    Uses an in-memory SQLite database for fast testing.
    Each test gets a fresh database.
    
    Note: SQLite doesn't support JSONB, so we convert it to JSON for tests.
    """
    # Set up JSONB -> JSON conversion for SQLite
    _setup_sqlite_jsonb_support()
    
    try:
        # Create in-memory SQLite database
        engine = create_engine("sqlite:///:memory:", echo=False)
        
        # Create all tables
        Base.metadata.create_all(engine)
        
        # Create session
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()
        
        yield session
        
        # Cleanup
        session.close()
        Base.metadata.drop_all(engine)
    finally:
        # Restore original JSONB handling
        _teardown_sqlite_jsonb_support()


# Alias for consistency with CLI tests
@pytest.fixture
def test_session(db_session, monkeypatch):
    """Alias for db_session for CLI tests, with mocked get_session."""
    # Mock get_session to return our test session
    from et_intel_core import db
    monkeypatch.setattr(db, 'get_session', lambda: db_session)
    
    # Mock init_db and drop_db to use test session's bind
    def mock_init_db():
        from et_intel_core.models.base import Base
        try:
            Base.metadata.create_all(bind=db_session.bind)
        except Exception:
            # Tables might already exist, that's OK
            pass
    
    def mock_drop_db():
        from et_intel_core.models.base import Base
        Base.metadata.drop_all(bind=db_session.bind)
    
    monkeypatch.setattr(db, 'init_db', mock_init_db)
    monkeypatch.setattr(db, 'drop_db', mock_drop_db)
    
    # Note: cli module imports init_db at module level, but drop_db is imported inside functions
    # So we only need to patch the db module, which cli will use
    
    return db_session


@pytest.fixture
def sample_entity(db_session) -> MonitoredEntity:
    """Create a sample monitored entity."""
    entity = MonitoredEntity(
        name="Test Entity",
        canonical_name="Test Entity",
        entity_type=EntityType.PERSON,
        is_active=True,
        aliases=["TE", "Test"]
    )
    db_session.add(entity)
    db_session.commit()
    return entity


@pytest.fixture
def sample_post(db_session) -> Post:
    """Create a sample post."""
    post = Post(
        platform=PlatformType.INSTAGRAM,
        external_id="test_post_123",
        url="https://instagram.com/p/test_post_123",
        subject_line="Test Post",
        posted_at=datetime.utcnow(),
        raw_data={"test": "data"}
    )
    db_session.add(post)
    db_session.commit()
    return post


@pytest.fixture
def sample_comment(db_session, sample_post) -> Comment:
    """Create a sample comment."""
    comment = Comment(
        post_id=sample_post.id,
        author_name="test_user",
        text="This is a test comment",
        created_at=datetime.utcnow(),
        likes=10,
        reply_count=0,
        context_type=ContextType.DIRECT,
        metadata={}
    )
    db_session.add(comment)
    db_session.commit()
    return comment


@pytest.fixture
def sample_discovered_entity(db_session) -> DiscoveredEntity:
    """Create a sample discovered entity."""
    entity = DiscoveredEntity(
        name="Discovered Person",
        entity_type="PERSON",
        first_seen_at=datetime.utcnow(),
        last_seen_at=datetime.utcnow(),
        mention_count=10,
        sample_mentions=["This is a mention of Discovered Person"],
        reviewed=False
    )
    db_session.add(entity)
    db_session.commit()
    return entity


@pytest.fixture
def enriched_comment(db_session, sample_entity, sample_comment) -> ExtractedSignal:
    """Create a sample enriched comment with signal."""
    signal = ExtractedSignal(
        comment_id=sample_comment.id,
        entity_id=sample_entity.id,
        signal_type=SignalType.SENTIMENT,
        value="positive",
        numeric_value=0.8,
        weight_score=1.0,
        confidence=0.9,
        source_model="test",
        created_at=datetime.utcnow()
    )
    db_session.add(signal)
    db_session.commit()
    
    # Attach entity reference for easier access in tests
    signal.entity = sample_entity
    return signal

