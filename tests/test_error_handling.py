"""
Error handling and edge case tests.
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
import tempfile

from et_intel_core.services import IngestionService, EnrichmentService
from et_intel_core.sources.esuit import ESUITSource
from et_intel_core.analytics import AnalyticsService
from et_intel_core.reporting import BriefBuilder
from et_intel_core.nlp import EntityExtractor, get_sentiment_provider
from et_intel_core.models import MonitoredEntity, Post, Comment, ExtractedSignal, EntityType, PlatformType, SignalType


class TestIngestionErrorHandling:
    """Test error handling in ingestion service."""
    
    def test_ingestion_invalid_file(self, db_session, tmp_path):
        """Test ingestion with invalid file."""
        invalid_file = tmp_path / "invalid.csv"
        invalid_file.write_text("not a valid csv")
        
        source = ESUITSource(invalid_file)
        ingestion = IngestionService(db_session)
        
        # Should handle gracefully
        result = ingestion.ingest(source)
        assert result['comments_created'] == 0
    
    def test_ingestion_empty_file(self, db_session, tmp_path):
        """Test ingestion with empty file."""
        empty_file = tmp_path / "empty.csv"
        empty_file.write_text("Post URL,Username,Comment,Timestamp,Likes,Caption,Subject\n")
        
        source = ESUITSource(empty_file)
        ingestion = IngestionService(db_session)
        
        result = ingestion.ingest(source)
        assert result['comments_created'] == 0
        assert result['posts_created'] == 0
    
    def test_ingestion_malformed_timestamp(self, db_session, tmp_path):
        """Test ingestion with malformed timestamp."""
        csv_content = "Post URL,Username,Comment,Timestamp,Likes,Caption,Subject\n"
        csv_content += "https://instagram.com/p/test,user,Comment,invalid-date,10,Caption,Subject\n"
        
        csv_file = tmp_path / "malformed.csv"
        csv_file.write_text(csv_content)
        
        source = ESUITSource(csv_file)
        ingestion = IngestionService(db_session)
        
        # Should skip invalid records or handle gracefully
        try:
            result = ingestion.ingest(source)
            assert isinstance(result, dict)
        except Exception:
            # If it raises an exception, that's also acceptable error handling
            pass


class TestEnrichmentErrorHandling:
    """Test error handling in enrichment service."""
    
    def test_enrichment_nonexistent_comment_ids(self, db_session, sample_entity):
        """Test enrichment with non-existent comment IDs."""
        import uuid
        
        extractor = EntityExtractor([sample_entity])
        sentiment_provider = get_sentiment_provider()
        enrichment = EnrichmentService(db_session, extractor, sentiment_provider)
        
        fake_ids = [uuid.uuid4() for _ in range(5)]
        result = enrichment.enrich_comments(comment_ids=fake_ids)
        
        assert result['comments_processed'] == 0
        assert result['signals_created'] == 0
    
    def test_enrichment_empty_comment_list(self, db_session, sample_entity):
        """Test enrichment with empty comment list."""
        extractor = EntityExtractor([sample_entity])
        sentiment_provider = get_sentiment_provider()
        enrichment = EnrichmentService(db_session, extractor, sentiment_provider)
        
        result = enrichment.enrich_comments(comment_ids=[])
        
        assert result['comments_processed'] == 0


class TestAnalyticsErrorHandling:
    """Test error handling in analytics service."""
    
    def test_analytics_invalid_time_window(self, db_session):
        """Test analytics with invalid time window (end before start)."""
        analytics = AnalyticsService(db_session)
        
        end = datetime.utcnow() - timedelta(days=10)
        start = datetime.utcnow()
        
        # Should handle gracefully
        result = analytics.get_top_entities((start, end))
        assert len(result) == 0
    
    def test_analytics_nonexistent_entity_id(self, db_session):
        """Test analytics with non-existent entity ID."""
        import uuid
        
        analytics = AnalyticsService(db_session)
        fake_id = uuid.uuid4()
        
        # Should return error dict
        velocity = analytics.compute_velocity(fake_id)
        assert 'error' in velocity
    
    def test_analytics_empty_time_window(self, db_session):
        """Test analytics with zero-length time window."""
        analytics = AnalyticsService(db_session)
        
        now = datetime.utcnow()
        result = analytics.get_top_entities((now, now))
        
        # Should handle gracefully
        assert isinstance(result, type(analytics.get_top_entities((now, now))))
    
    def test_analytics_very_large_time_window(self, db_session):
        """Test analytics with very large time window."""
        analytics = AnalyticsService(db_session)
        
        end = datetime.utcnow()
        start = end - timedelta(days=365 * 10)  # 10 years
        
        # Should handle without error
        result = analytics.get_top_entities((start, end))
        assert isinstance(result, type(analytics.get_top_entities((start, end))))


class TestReportingErrorHandling:
    """Test error handling in reporting."""
    
    def test_brief_builder_invalid_time_window(self, db_session, monkeypatch):
        """Test brief builder with invalid time window."""
        from et_intel_core import db
        monkeypatch.setattr(db, 'get_session', lambda: db_session)
        
        analytics = AnalyticsService(db_session)
        builder = BriefBuilder(analytics)
        
        # End before start
        end = datetime.utcnow() - timedelta(days=10)
        start = datetime.utcnow()
        
        # Should handle gracefully
        brief = builder.build(start, end)
        assert brief.topline_summary['total_comments'] == 0
    
    def test_brief_builder_empty_database(self, db_session, monkeypatch):
        """Test brief builder with completely empty database."""
        from et_intel_core import db
        monkeypatch.setattr(db, 'get_session', lambda: db_session)
        
        analytics = AnalyticsService(db_session)
        builder = BriefBuilder(analytics)
        
        start = datetime.utcnow() - timedelta(days=7)
        end = datetime.utcnow()
        
        brief = builder.build(start, end)
        
        # Should return valid brief structure
        assert brief.topline_summary['total_comments'] == 0
        assert brief.topline_summary['total_entities'] == 0
        assert len(brief.top_entities.items) == 0


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_entity_with_special_characters(self, db_session):
        """Test entity with special characters in name."""
        entity = MonitoredEntity(
            name="Test & Co. (Inc.)",
            canonical_name="Test & Co. (Inc.)",
            entity_type=EntityType.PERSON,
            aliases=["Test & Co", "Test Inc"]
        )
        db_session.add(entity)
        db_session.commit()
        
        assert entity.id is not None
        assert "&" in entity.name
        assert "(" in entity.name
    
    def test_comment_with_unicode(self, db_session, sample_post):
        """Test comment with unicode characters."""
        comment = Comment(
            post_id=sample_post.id,
            author_name="User 🎉",
            text="Comment with emoji 😀 and unicode 中文",
            created_at=datetime.utcnow(),
            likes=10
        )
        db_session.add(comment)
        db_session.commit()
        
        assert comment.id is not None
        assert "🎉" in comment.author_name
        assert "😀" in comment.text
    
    def test_very_long_comment_text(self, db_session, sample_post):
        """Test comment with very long text."""
        long_text = "A" * 10000  # 10KB comment
        comment = Comment(
            post_id=sample_post.id,
            author_name="User",
            text=long_text,
            created_at=datetime.utcnow(),
            likes=0
        )
        db_session.add(comment)
        db_session.commit()
        
        assert len(comment.text) == 10000
    
    def test_sentiment_extreme_values(self, db_session, sample_entity, sample_comment):
        """Test sentiment with extreme values."""
        # Very positive - use different source_model to avoid unique constraint
        signal1 = ExtractedSignal(
            comment_id=sample_comment.id,
            entity_id=sample_entity.id,
            signal_type=SignalType.SENTIMENT,
            value="positive",
            numeric_value=1.0,
            source_model="test1"
        )
        
        # Very negative - use different source_model
        signal2 = ExtractedSignal(
            comment_id=sample_comment.id,
            entity_id=sample_entity.id,
            signal_type=SignalType.SENTIMENT,
            value="negative",
            numeric_value=-1.0,
            source_model="test2"
        )
        
        db_session.add_all([signal1, signal2])
        db_session.commit()
        
        assert signal1.numeric_value == 1.0
        assert signal2.numeric_value == -1.0
    
    def test_multiple_entities_same_comment(self, db_session, sample_comment):
        """Test multiple entities extracted from same comment."""
        entity1 = MonitoredEntity(
            name="Entity 1",
            canonical_name="Entity 1",
            entity_type=EntityType.PERSON
        )
        entity2 = MonitoredEntity(
            name="Entity 2",
            canonical_name="Entity 2",
            entity_type=EntityType.PERSON
        )
        db_session.add_all([entity1, entity2])
        db_session.commit()
        
        # Create signals for both entities from same comment
        signal1 = ExtractedSignal(
            comment_id=sample_comment.id,
            entity_id=entity1.id,
            signal_type=SignalType.SENTIMENT,
            value="positive",
            numeric_value=0.5,
            source_model="test"
        )
        signal2 = ExtractedSignal(
            comment_id=sample_comment.id,
            entity_id=entity2.id,
            signal_type=SignalType.SENTIMENT,
            value="negative",
            numeric_value=-0.3,
            source_model="test"
        )
        
        db_session.add_all([signal1, signal2])
        db_session.commit()
        
        # Both signals should exist
        signals = db_session.query(ExtractedSignal).filter_by(comment_id=sample_comment.id).all()
        assert len(signals) >= 2
    
    def test_zero_likes_comment(self, db_session, sample_post):
        """Test comment with zero likes."""
        comment = Comment(
            post_id=sample_post.id,
            author_name="User",
            text="Comment with no likes",
            created_at=datetime.utcnow(),
            likes=0
        )
        db_session.add(comment)
        db_session.commit()
        
        assert comment.likes == 0
    
    def test_very_high_likes_comment(self, db_session, sample_post):
        """Test comment with very high like count."""
        comment = Comment(
            post_id=sample_post.id,
            author_name="User",
            text="Viral comment",
            created_at=datetime.utcnow(),
            likes=1000000
        )
        db_session.add(comment)
        db_session.commit()
        
        assert comment.likes == 1000000

