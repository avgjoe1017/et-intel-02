"""
Tests for SQLAlchemy models.
"""

from datetime import datetime
import pytest

from et_intel_core.models import (
    Post,
    Comment,
    MonitoredEntity,
    ExtractedSignal,
    DiscoveredEntity,
    PlatformType,
    SignalType,
    ContextType,
    EntityType
)


def test_create_post(db_session):
    """Test creating a post."""
    post = Post(
        platform=PlatformType.INSTAGRAM,
        external_id="ABC123",
        url="https://instagram.com/p/ABC123/",
        subject_line="Test Post",
        posted_at=datetime.utcnow(),
        raw_data={"test": "data"}
    )
    
    db_session.add(post)
    db_session.commit()
    
    assert post.id is not None
    assert post.platform == PlatformType.INSTAGRAM
    assert post.external_id == "ABC123"


def test_create_comment(db_session):
    """Test creating a comment."""
    # Create post first
    post = Post(
        platform=PlatformType.INSTAGRAM,
        external_id="ABC123",
        url="https://instagram.com/p/ABC123/",
        posted_at=datetime.utcnow()
    )
    db_session.add(post)
    db_session.flush()
    
    # Create comment
    comment = Comment(
        post_id=post.id,
        author_name="test_user",
        text="This is a test comment",
        created_at=datetime.utcnow(),
        likes=42,
        context_type=ContextType.DIRECT
    )
    
    db_session.add(comment)
    db_session.commit()
    
    assert comment.id is not None
    assert comment.author_name == "test_user"
    assert comment.likes == 42


def test_create_monitored_entity(db_session):
    """Test creating a monitored entity."""
    entity = MonitoredEntity(
        name="Taylor Swift",
        canonical_name="Taylor Swift",
        entity_type=EntityType.PERSON,
        is_active=True,
        aliases=["T-Swift", "Tay"]
    )
    
    db_session.add(entity)
    db_session.commit()
    
    assert entity.id is not None
    assert entity.name == "Taylor Swift"
    assert len(entity.aliases) == 2


def test_create_extracted_signal(db_session):
    """Test creating an extracted signal."""
    # Create post and comment first
    post = Post(
        platform=PlatformType.INSTAGRAM,
        external_id="ABC123",
        url="https://instagram.com/p/ABC123/",
        posted_at=datetime.utcnow()
    )
    db_session.add(post)
    db_session.flush()
    
    comment = Comment(
        post_id=post.id,
        author_name="test_user",
        text="I love this!",
        created_at=datetime.utcnow()
    )
    db_session.add(comment)
    db_session.flush()
    
    # Create signal
    signal = ExtractedSignal(
        comment_id=comment.id,
        entity_id=None,  # General sentiment
        signal_type=SignalType.SENTIMENT,
        value="positive",
        numeric_value=0.8,
        weight_score=1.0,
        confidence=0.9,
        source_model="textblob"
    )
    
    db_session.add(signal)
    db_session.commit()
    
    assert signal.id is not None
    assert signal.signal_type == SignalType.SENTIMENT
    assert signal.numeric_value == 0.8


def test_create_discovered_entity(db_session):
    """Test creating a discovered entity."""
    entity = DiscoveredEntity(
        name="Unknown Person",
        entity_type="PERSON",
        first_seen_at=datetime.utcnow(),
        last_seen_at=datetime.utcnow(),
        mention_count=5,
        sample_mentions=["mention 1", "mention 2"],
        reviewed=False
    )
    
    db_session.add(entity)
    db_session.commit()
    
    assert entity.id is not None
    assert entity.name == "Unknown Person"
    assert entity.mention_count == 5
    assert not entity.reviewed


def test_post_comment_relationship(db_session):
    """Test relationship between post and comments."""
    post = Post(
        platform=PlatformType.INSTAGRAM,
        external_id="ABC123",
        url="https://instagram.com/p/ABC123/",
        posted_at=datetime.utcnow()
    )
    db_session.add(post)
    db_session.flush()
    
    # Add multiple comments
    for i in range(3):
        comment = Comment(
            post_id=post.id,
            author_name=f"user_{i}",
            text=f"Comment {i}",
            created_at=datetime.utcnow()
        )
        db_session.add(comment)
    
    db_session.commit()
    
    # Verify relationship
    assert len(post.comments) == 3
    assert post.comments[0].post == post


def test_comment_signal_relationship(db_session):
    """Test relationship between comment and signals."""
    post = Post(
        platform=PlatformType.INSTAGRAM,
        external_id="ABC123",
        url="https://instagram.com/p/ABC123/",
        posted_at=datetime.utcnow()
    )
    db_session.add(post)
    db_session.flush()
    
    comment = Comment(
        post_id=post.id,
        author_name="test_user",
        text="I love this!",
        created_at=datetime.utcnow()
    )
    db_session.add(comment)
    db_session.flush()
    
    # Add multiple signals
    signal1 = ExtractedSignal(
        comment_id=comment.id,
        signal_type=SignalType.SENTIMENT,
        value="positive",
        numeric_value=0.8,
        source_model="textblob"
    )
    signal2 = ExtractedSignal(
        comment_id=comment.id,
        signal_type=SignalType.EMOTION,
        value="joy",
        source_model="textblob"
    )
    
    db_session.add_all([signal1, signal2])
    db_session.commit()
    
    # Verify relationship
    assert len(comment.signals) == 2
    assert comment.signals[0].comment == comment

