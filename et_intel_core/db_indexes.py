"""
Database index creation for performance optimization.

Run this after initial schema creation to add performance indexes.
"""

from sqlalchemy import Index
from sqlalchemy.orm import Session

from et_intel_core.models import ExtractedSignal, Comment


def create_performance_indexes(session: Session):
    """
    Create performance indexes for analytics queries.
    
    These indexes significantly speed up:
    - Entity sentiment queries
    - Time-based filtering
    - Velocity calculations
    
    Args:
        session: SQLAlchemy database session
    """
    # Composite index for entity sentiment queries
    # Speeds up: "Blake Lively negative signals last week"
    idx_entity_signal_time = Index(
        'idx_entity_signal_time',
        ExtractedSignal.entity_id,
        ExtractedSignal.signal_type,
        ExtractedSignal.created_at
    )
    
    # Index for comment time-based queries (already in model, but ensuring it exists)
    # Speeds up: time window filtering
    idx_comment_created = Index(
        'idx_comment_created',
        Comment.created_at
    )
    
    # Composite index for signal type + time queries
    # Speeds up: "All sentiment signals from last month"
    idx_signal_type_time = Index(
        'idx_signal_type_time',
        ExtractedSignal.signal_type,
        ExtractedSignal.created_at
    )
    
    # Create indexes
    try:
        idx_entity_signal_time.create(session.bind, checkfirst=True)
        print("✓ Created index: idx_entity_signal_time")
    except Exception as e:
        print(f"  Index idx_entity_signal_time already exists or error: {e}")
    
    try:
        idx_comment_created.create(session.bind, checkfirst=True)
        print("✓ Created index: idx_comment_created")
    except Exception as e:
        print(f"  Index idx_comment_created already exists or error: {e}")
    
    try:
        idx_signal_type_time.create(session.bind, checkfirst=True)
        print("✓ Created index: idx_signal_type_time")
    except Exception as e:
        print(f"  Index idx_signal_type_time already exists or error: {e}")
    
    session.commit()
    print("\n✓ Performance indexes created successfully")


if __name__ == "__main__":
    from et_intel_core.db import get_session
    
    session = get_session()
    try:
        create_performance_indexes(session)
    finally:
        session.close()

