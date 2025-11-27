"""
Tests for analytics service.
"""

from datetime import datetime, timedelta
import pytest

from et_intel_core.models import (
    Post,
    Comment,
    MonitoredEntity,
    ExtractedSignal,
    EntityType,
    SignalType,
    PlatformType
)
from et_intel_core.analytics import AnalyticsService


def create_test_data(db_session):
    """Helper to create test data for analytics."""
    # Create entities
    taylor = MonitoredEntity(
        name="Taylor Swift",
        canonical_name="Taylor Swift",
        entity_type=EntityType.PERSON,
        is_active=True
    )
    blake = MonitoredEntity(
        name="Blake Lively",
        canonical_name="Blake Lively",
        entity_type=EntityType.PERSON,
        is_active=True
    )
    db_session.add_all([taylor, blake])
    db_session.flush()
    
    # Create post
    post = Post(
        platform=PlatformType.INSTAGRAM,
        external_id="ABC123",
        url="https://instagram.com/p/ABC123/",
        posted_at=datetime.utcnow()
    )
    db_session.add(post)
    db_session.flush()
    
    # Create comments with different timestamps
    # Need enough data for velocity computation (72-hour windows need at least 10 points each)
    # Recent window: last 72 hours
    # Previous window: 72-144 hours ago
    # So we need data spanning at least 144 hours (6 days)
    now = datetime.utcnow()
    comments = []
    
    # Create 40 comments spread over the last 7 days (168 hours)
    # This ensures we have enough data in both recent (last 72h) and previous (72-144h) windows
    # For velocity: recent window = last 72h, previous window = 72-144h ago
    # We need at least 10 points in each window
    for i in range(40):
        # Spread over 7 days (168 hours)
        # Create comments at: 0, 4, 8, 12, ... 156 hours ago
        # Recent window (0-72h): 18 comments (0, 4, 8, ..., 68)
        # Previous window (72-144h): 18 comments (72, 76, 80, ..., 140)
        hours_ago = i * 4  # 0, 4, 8, 12, ... 156 hours ago
        comment = Comment(
            post_id=post.id,
            author_name=f"user_{i}",
            text=f"Comment {i}",
            created_at=now - timedelta(hours=hours_ago),
            likes=10 * i
        )
        comments.append(comment)
        db_session.add(comment)
    
    db_session.commit()
    
    # Create signals
    for i, comment in enumerate(comments):
        # Taylor sentiment (getting more positive over time - recent comments more positive)
        # Recent comments (low i = recent) should have higher sentiment
        # i=0 is most recent, i=39 is oldest
        sentiment_value = -0.5 + ((40 - i) * 0.025)  # -0.5 to +0.5
        signal_taylor = ExtractedSignal(
            comment_id=comment.id,
            entity_id=taylor.id,
            signal_type=SignalType.SENTIMENT,
            value="positive" if sentiment_value > 0 else "negative",
            numeric_value=sentiment_value,
            weight_score=1.0,
            confidence=0.8,
            source_model="test",
            created_at=comment.created_at
        )
        db_session.add(signal_taylor)
        
        # Blake sentiment (getting more negative over time)
        sentiment_value = 0.5 - ((40 - i) * 0.025)  # +0.5 to -0.5
        signal_blake = ExtractedSignal(
            comment_id=comment.id,
            entity_id=blake.id,
            signal_type=SignalType.SENTIMENT,
            value="positive" if sentiment_value > 0 else "negative",
            numeric_value=sentiment_value,
            weight_score=1.0,
            confidence=0.8,
            source_model="test",
            created_at=comment.created_at
        )
        db_session.add(signal_blake)
    
    db_session.commit()
    
    return taylor, blake, comments


def test_get_top_entities(db_session):
    """Test getting top entities."""
    taylor, blake, comments = create_test_data(db_session)
    
    analytics = AnalyticsService(db_session)
    
    # Get top entities for last 30 days
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)
    
    df = analytics.get_top_entities((start_date, end_date), limit=10)
    
    # Should have 2 entities
    assert len(df) == 2
    
    # Check columns
    assert 'entity_name' in df.columns
    assert 'mention_count' in df.columns
    assert 'avg_sentiment' in df.columns
    
    # Both entities should have 40 mentions (we create 40 comments with signals for each)
    assert df['mention_count'].iloc[0] == 40
    assert df['mention_count'].iloc[1] == 40


def test_compute_velocity_with_data(db_session):
    """Test velocity computation with sufficient data."""
    taylor, blake, comments = create_test_data(db_session)
    
    # Verify signals were created
    from et_intel_core.models import ExtractedSignal
    signal_count = db_session.query(ExtractedSignal).filter_by(entity_id=taylor.id).count()
    assert signal_count == 40, f"Expected 40 signals for Taylor, got {signal_count}"
    
    # Verify signals have correct timestamps
    now = datetime.utcnow()
    recent_start = now - timedelta(hours=72)
    previous_start = now - timedelta(hours=144)
    
    # Count signals in each window
    recent_signals = db_session.query(ExtractedSignal).join(
        comments[0].__class__
    ).filter(
        ExtractedSignal.entity_id == taylor.id,
        ExtractedSignal.signal_type == SignalType.SENTIMENT,
        comments[0].__class__.created_at >= recent_start,
        comments[0].__class__.created_at <= now
    ).count()
    
    analytics = AnalyticsService(db_session)
    
    # Compute velocity for Taylor (sentiment improving)
    velocity = analytics.compute_velocity(taylor.id, window_hours=72)
    
    # Debug: print velocity if error
    if 'error' in velocity:
        print(f"Velocity error: {velocity}")
        print(f"Recent signals count: {recent_signals}")
        print(f"Taylor ID: {taylor.id} (type: {type(taylor.id)})")
        # Check what's actually in the database
        from sqlalchemy import text
        result = db_session.execute(text("""
            SELECT COUNT(*) as cnt, es.entity_id, c.created_at
            FROM extracted_signals es
            JOIN comments c ON es.comment_id = c.id
            WHERE es.signal_type = 'sentiment'
            GROUP BY es.entity_id
            LIMIT 5
        """)).fetchall()
        print(f"Signals in DB: {result}")
    
    # Should have data
    assert 'error' not in velocity, f"Velocity computation failed: {velocity}"
    assert 'percent_change' in velocity
    assert 'recent_sentiment' in velocity
    assert 'previous_sentiment' in velocity
    
    # Taylor's sentiment is improving (more recent = more positive)
    # So percent change should be positive
    assert velocity['direction'] == 'up'


def test_compute_velocity_insufficient_data(db_session):
    """Test velocity computation with insufficient data."""
    # Create entity with no signals
    entity = MonitoredEntity(
        name="Test Entity",
        canonical_name="Test Entity",
        entity_type=EntityType.PERSON
    )
    db_session.add(entity)
    db_session.commit()
    
    analytics = AnalyticsService(db_session)
    
    # Should return error
    velocity = analytics.compute_velocity(entity.id)
    assert 'error' in velocity


def test_compute_brief_velocity(db_session):
    """Test brief velocity computation."""
    taylor, blake, comments = create_test_data(db_session)
    
    analytics = AnalyticsService(db_session)
    
    # Compute velocity for last 10 days
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=10)
    
    velocity = analytics.compute_brief_velocity(taylor.id, (start_date, end_date))
    
    # Should have data
    assert 'error' not in velocity
    assert 'percent_change' in velocity
    assert 'first_half_sentiment' in velocity
    assert 'second_half_sentiment' in velocity


def test_get_entity_sentiment_history(db_session):
    """Test sentiment history retrieval."""
    taylor, blake, comments = create_test_data(db_session)
    
    analytics = AnalyticsService(db_session)
    
    # Get history
    df = analytics.get_entity_sentiment_history(taylor.id, days=30)
    
    # Should have data
    assert len(df) > 0
    
    # Check columns
    assert 'date' in df.columns
    assert 'avg_sentiment' in df.columns
    assert 'mention_count' in df.columns


def test_get_comment_count(db_session):
    """Test comment counting."""
    taylor, blake, comments = create_test_data(db_session)
    
    analytics = AnalyticsService(db_session)
    
    # Count comments in last 30 days
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)
    
    count = analytics.get_comment_count((start_date, end_date))
    
    # Should have 40 comments (create_test_data creates 40)
    assert count == 40


def test_get_entity_comparison(db_session):
    """Test entity comparison."""
    taylor, blake, comments = create_test_data(db_session)
    
    analytics = AnalyticsService(db_session)
    
    # Compare entities
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)
    
    df = analytics.get_entity_comparison([taylor.id, blake.id], (start_date, end_date))
    
    # Should have 2 entities
    assert len(df) == 2
    
    # Check columns
    assert 'entity_name' in df.columns
    assert 'avg_sentiment' in df.columns
    assert 'mention_count' in df.columns


def test_get_sentiment_distribution(db_session):
    """Test sentiment distribution."""
    taylor, blake, comments = create_test_data(db_session)
    
    analytics = AnalyticsService(db_session)
    
    # Get distribution
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)
    
    distribution = analytics.get_sentiment_distribution((start_date, end_date))
    
    # Should have positive and negative
    assert 'positive' in distribution or 'negative' in distribution
    assert isinstance(distribution, dict)


def test_velocity_alert_threshold(db_session):
    """Test that velocity alerts trigger at 30% threshold."""
    taylor, blake, comments = create_test_data(db_session)
    
    analytics = AnalyticsService(db_session)
    
    # Blake's sentiment is declining significantly
    velocity = analytics.compute_velocity(blake.id, window_hours=72)
    
    # Check alert logic
    if 'error' not in velocity:
        if abs(velocity['percent_change']) > 30:
            assert velocity['alert'] == True
        else:
            assert velocity['alert'] == False


def test_top_entities_with_platform_filter(db_session):
    """Test top entities with platform filtering."""
    taylor, blake, comments = create_test_data(db_session)
    
    analytics = AnalyticsService(db_session)
    
    # Get top entities for Instagram only
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)
    
    df = analytics.get_top_entities((start_date, end_date), platforms=["instagram"], limit=10)
    
    # Should still have data (all our test data is Instagram)
    assert len(df) == 2

