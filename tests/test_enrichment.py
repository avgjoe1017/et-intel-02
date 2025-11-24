"""
Tests for enrichment service.
"""

from datetime import datetime
import pytest

from et_intel_core.models import (
    Post,
    Comment,
    MonitoredEntity,
    ExtractedSignal,
    DiscoveredEntity,
    EntityType,
    SignalType,
    PlatformType
)
from et_intel_core.services import EnrichmentService
from et_intel_core.nlp import EntityExtractor, RuleBasedSentimentProvider


def test_enrichment_creates_signals(db_session):
    """Test that enrichment creates sentiment signals."""
    # Create post and comment
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
        text="I love this so much!",
        created_at=datetime.utcnow(),
        likes=42
    )
    db_session.add(comment)
    db_session.commit()
    
    # Create enrichment service
    extractor = EntityExtractor([])  # Empty catalog
    sentiment_provider = RuleBasedSentimentProvider()
    service = EnrichmentService(db_session, extractor, sentiment_provider)
    
    # Enrich
    stats = service.enrich_comments()
    
    # Verify stats
    assert stats["comments_processed"] == 1
    assert stats["signals_created"] >= 1  # At least general sentiment
    
    # Verify signal in database
    signals = db_session.query(ExtractedSignal).all()
    assert len(signals) >= 1
    
    signal = signals[0]
    assert signal.comment_id == comment.id
    assert signal.signal_type == SignalType.SENTIMENT
    assert signal.numeric_value is not None
    assert -1.0 <= signal.numeric_value <= 1.0


def test_enrichment_with_entities(db_session):
    """Test enrichment with entity extraction."""
    # Create entity
    taylor = MonitoredEntity(
        name="Taylor Swift",
        canonical_name="Taylor Swift",
        entity_type=EntityType.PERSON,
        aliases=["Taylor"]
    )
    db_session.add(taylor)
    db_session.flush()
    
    # Create post and comment mentioning entity
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
        text="Taylor Swift is amazing!",
        created_at=datetime.utcnow()
    )
    db_session.add(comment)
    db_session.commit()
    
    # Enrich
    extractor = EntityExtractor([taylor])
    sentiment_provider = RuleBasedSentimentProvider()
    service = EnrichmentService(db_session, extractor, sentiment_provider)
    
    stats = service.enrich_comments()
    
    # Should create 2 signals: general + entity-specific
    assert stats["signals_created"] >= 2
    
    # Verify entity-specific signal
    entity_signal = db_session.query(ExtractedSignal).filter(
        ExtractedSignal.entity_id == taylor.id
    ).first()
    
    assert entity_signal is not None
    assert entity_signal.signal_type == SignalType.SENTIMENT


def test_enrichment_tracks_discovered_entities(db_session):
    """Test that enrichment tracks discovered entities."""
    # Create post and comment with unknown entity
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
        text="Blake Lively is so talented",
        created_at=datetime.utcnow()
    )
    db_session.add(comment)
    db_session.commit()
    
    # Enrich with empty catalog
    extractor = EntityExtractor([])
    sentiment_provider = RuleBasedSentimentProvider()
    service = EnrichmentService(db_session, extractor, sentiment_provider)
    
    stats = service.enrich_comments()
    
    # Should discover entity
    assert stats["entities_discovered"] >= 1
    
    # Verify in database
    discovered = db_session.query(DiscoveredEntity).all()
    assert len(discovered) >= 1


def test_enrichment_idempotent(db_session):
    """Test that enrichment is idempotent (can re-run)."""
    # Create post and comment
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
        text="This is great!",
        created_at=datetime.utcnow()
    )
    db_session.add(comment)
    db_session.commit()
    
    # Enrich
    extractor = EntityExtractor([])
    sentiment_provider = RuleBasedSentimentProvider()
    service = EnrichmentService(db_session, extractor, sentiment_provider)
    
    # First run
    stats1 = service.enrich_comments()
    signal_count_1 = db_session.query(ExtractedSignal).count()
    
    # Second run (should update, not duplicate)
    stats2 = service.enrich_comments(comment_ids=[comment.id])
    signal_count_2 = db_session.query(ExtractedSignal).count()
    
    # Signal count should be same (updated, not duplicated)
    assert signal_count_1 == signal_count_2


def test_enrichment_like_weighting(db_session):
    """Test that like-weighted scoring works."""
    # Create post and comment with high likes
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
        text="Love this!",
        created_at=datetime.utcnow(),
        likes=500  # High engagement
    )
    db_session.add(comment)
    db_session.commit()
    
    # Enrich
    extractor = EntityExtractor([])
    sentiment_provider = RuleBasedSentimentProvider()
    service = EnrichmentService(db_session, extractor, sentiment_provider)
    
    service.enrich_comments()
    
    # Check weight score
    signal = db_session.query(ExtractedSignal).first()
    assert signal.weight_score > 1.0  # Should be weighted by likes
    # Formula: 1.0 + (500 / 100) = 6.0
    assert signal.weight_score == pytest.approx(6.0, rel=0.1)


def test_enrichment_sentiment_labels(db_session):
    """Test sentiment label conversion."""
    # Create post and comments with different sentiments
    post = Post(
        platform=PlatformType.INSTAGRAM,
        external_id="ABC123",
        url="https://instagram.com/p/ABC123/",
        posted_at=datetime.utcnow()
    )
    db_session.add(post)
    db_session.flush()
    
    comments = [
        Comment(post_id=post.id, author_name="user1", text="I love this!", created_at=datetime.utcnow()),
        Comment(post_id=post.id, author_name="user2", text="This is okay", created_at=datetime.utcnow()),
        Comment(post_id=post.id, author_name="user3", text="I hate this", created_at=datetime.utcnow()),
    ]
    db_session.add_all(comments)
    db_session.commit()
    
    # Enrich
    extractor = EntityExtractor([])
    sentiment_provider = RuleBasedSentimentProvider()
    service = EnrichmentService(db_session, extractor, sentiment_provider)
    
    service.enrich_comments()
    
    # Check labels
    signals = db_session.query(ExtractedSignal).all()
    labels = [s.value for s in signals]
    
    assert "positive" in labels or "negative" in labels or "neutral" in labels

