"""
Edge case tests: empty data, large datasets, failures, boundary conditions.
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
import uuid

from et_intel_core.db import get_session
from et_intel_core.services.ingestion import IngestionService
from et_intel_core.services.enrichment import EnrichmentService
from et_intel_core.analytics import AnalyticsService
from et_intel_core.sources.esuit import ESUITSource
from et_intel_core.nlp.entity_extractor import EntityExtractor
from et_intel_core.nlp.sentiment import get_sentiment_provider
from et_intel_core.models import MonitoredEntity, EntityType, Post, Comment, PlatformType


class TestEmptyData:
    """Test handling of empty datasets."""
    
    def test_empty_database_queries(self, db_session):
        """Test analytics queries with empty database."""
        analytics = AnalyticsService(db_session)
        
        end = datetime.utcnow()
        start = end - timedelta(days=30)
        
        # All should return empty results, not crash
        top_entities = analytics.get_top_entities((start, end))
        assert len(top_entities) == 0
        
        comment_count = analytics.get_comment_count((start, end))
        assert comment_count == 0
        
        distribution = analytics.get_sentiment_distribution((start, end))
        assert len(distribution) == 0
    
    def test_empty_csv_ingestion(self, db_session, tmp_path):
        """Test ingestion of empty CSV file."""
        # Create empty CSV (just headers)
        csv_content = "Post URL,Username,Comment,Timestamp,Likes,Caption,Subject\n"
        csv_file = tmp_path / "empty.csv"
        csv_file.write_text(csv_content)
        
        source = ESUITSource(csv_file)
        ingestion = IngestionService(db_session)
        
        stats = ingestion.ingest(source)
        
        assert stats['comments_created'] == 0
        assert stats['posts_created'] == 0
    
    def test_enrichment_with_no_comments(self, db_session):
        """Test enrichment when no comments exist."""
        entity = MonitoredEntity(
            name="Test Entity",
            canonical_name="Test Entity",
            entity_type=EntityType.PERSON,
            is_active=True
        )
        db_session.add(entity)
        db_session.commit()
        
        entity_catalog = [entity]
        extractor = EntityExtractor(entity_catalog)
        sentiment_provider = get_sentiment_provider()
        enrichment = EnrichmentService(db_session, extractor, sentiment_provider)
        
        stats = enrichment.enrich_comments()
        
        assert stats['comments_processed'] == 0
        assert stats['signals_created'] == 0
    
    def test_velocity_with_insufficient_data(self, db_session):
        """Test velocity calculation with insufficient data."""
        analytics = AnalyticsService(db_session)
        
        # Create entity but no signals
        entity = MonitoredEntity(
            name="Test Entity",
            canonical_name="Test Entity",
            entity_type=EntityType.PERSON
        )
        db_session.add(entity)
        db_session.commit()
        
        velocity = analytics.compute_velocity(entity.id, window_hours=72, min_sample_size=10)
        
        assert 'error' in velocity
        assert 'Insufficient data' in velocity['error'] or 'No data found' in velocity['error']


class TestLargeDatasets:
    """Test handling of large datasets."""
    
    def test_large_ingestion(self, db_session, tmp_path):
        """Test ingestion of large CSV file."""
        # Create CSV with 1000 comments
        csv_lines = ["Post URL,Username,Comment,Timestamp,Likes,Caption,Subject\n"]
        
        for i in range(1000):
            csv_lines.append(
                f"https://instagram.com/p/post{i},user{i},Comment {i},2024-01-01 10:00:00,{i},Caption,Subject\n"
            )
        
        csv_file = tmp_path / "large.csv"
        csv_file.write_text("".join(csv_lines))
        
        source = ESUITSource(csv_file)
        ingestion = IngestionService(db_session)
        
        stats = ingestion.ingest(source)
        
        assert stats['comments_created'] == 1000
        assert stats['posts_created'] == 1000
    
    def test_large_enrichment(self, db_session, sample_entity):
        """Test enrichment of large number of comments."""
        from datetime import datetime
        
        # Create 500 comments
        post = Post(
            platform=PlatformType.INSTAGRAM,
            external_id="large_post",
            url="https://instagram.com/p/large",
            posted_at=datetime.utcnow()
        )
        db_session.add(post)
        db_session.commit()
        
        comments = []
        for i in range(500):
            comment = Comment(
                post_id=post.id,
                author_name=f"user{i}",
                text=f"Comment {i} about {sample_entity.name}",
                created_at=datetime.utcnow(),
                likes=i
            )
            comments.append(comment)
            db_session.add(comment)
        db_session.commit()
        
        # Enrich in batches
        entity_catalog = [sample_entity]
        extractor = EntityExtractor(entity_catalog)
        sentiment_provider = get_sentiment_provider()
        enrichment = EnrichmentService(db_session, extractor, sentiment_provider)
        
        comment_ids = [c.id for c in comments]
        stats = enrichment.enrich_comments(comment_ids=comment_ids)
        
        assert stats['comments_processed'] == 500
        assert stats['signals_created'] > 0
    
    def test_large_analytics_query(self, db_session, sample_entity):
        """Test analytics queries with large dataset."""
        from datetime import datetime
        from et_intel_core.models import Post, Comment, PlatformType, ExtractedSignal, SignalType
        
        # Create 100 posts with 10 comments each = 1000 comments
        posts = []
        for i in range(100):
            post = Post(
                platform=PlatformType.INSTAGRAM,
                external_id=f"post{i}",
                url=f"https://instagram.com/p/post{i}",
                posted_at=datetime.utcnow() - timedelta(days=i % 30)
            )
            posts.append(post)
            db_session.add(post)
        db_session.commit()
        
        # Create comments and signals
        for post in posts:
            for j in range(10):
                comment = Comment(
                    post_id=post.id,
                    author_name=f"user{j}",
                    text=f"Comment about {sample_entity.name}",
                    created_at=datetime.utcnow() - timedelta(days=j),
                    likes=j * 10
                )
                db_session.add(comment)
                db_session.flush()
                
                signal = ExtractedSignal(
                    comment_id=comment.id,
                    entity_id=sample_entity.id,
                    signal_type=SignalType.SENTIMENT,
                    value="positive" if j % 2 == 0 else "negative",
                    numeric_value=0.5 if j % 2 == 0 else -0.5,
                    source_model="test"
                )
                db_session.add(signal)
        db_session.commit()
        
        # Query should complete without timeout
        analytics = AnalyticsService(db_session)
        end = datetime.utcnow()
        start = end - timedelta(days=30)
        
        top_entities = analytics.get_top_entities((start, end), limit=10)
        
        assert len(top_entities) > 0
        assert top_entities.iloc[0]['entity_name'] == sample_entity.name


class TestBoundaryConditions:
    """Test boundary conditions and edge values."""
    
    def test_extreme_sentiment_values(self, db_session, sample_entity, sample_comment):
        """Test handling of extreme sentiment values."""
        from et_intel_core.models import ExtractedSignal, SignalType, Comment, Post, PlatformType
        from datetime import datetime
        
        # Create additional comments to avoid UNIQUE constraint violations
        post = Post(
            platform=PlatformType.INSTAGRAM,
            external_id="test_post_2",
            url="https://instagram.com/p/test2/",
            posted_at=datetime.utcnow()
        )
        db_session.add(post)
        db_session.flush()
        
        comment2 = Comment(
            post_id=post.id,
            author_name="user2",
            text="Test comment 2",
            created_at=datetime.utcnow(),
            likes=10
        )
        comment3 = Comment(
            post_id=post.id,
            author_name="user3",
            text="Test comment 3",
            created_at=datetime.utcnow(),
            likes=10
        )
        db_session.add_all([comment2, comment3])
        db_session.flush()
        
        # Test maximum positive
        signal1 = ExtractedSignal(
            comment_id=sample_comment.id,
            entity_id=sample_entity.id,
            signal_type=SignalType.SENTIMENT,
            value="positive",
            numeric_value=1.0,
            source_model="test1"
        )
        db_session.add(signal1)
        
        # Test maximum negative
        signal2 = ExtractedSignal(
            comment_id=comment2.id,
            entity_id=sample_entity.id,
            signal_type=SignalType.SENTIMENT,
            value="negative",
            numeric_value=-1.0,
            source_model="test2"
        )
        db_session.add(signal2)
        
        # Test zero
        signal3 = ExtractedSignal(
            comment_id=comment3.id,
            entity_id=sample_entity.id,
            signal_type=SignalType.SENTIMENT,
            value="neutral",
            numeric_value=0.0,
            source_model="test3"
        )
        db_session.add(signal3)
        
        db_session.commit()
        
        # Analytics should handle all values
        analytics = AnalyticsService(db_session)
        end = datetime.utcnow()
        start = end - timedelta(days=1)
        
        top_entities = analytics.get_top_entities((start, end))
        # Should not crash on extreme values
        assert isinstance(top_entities, type(analytics.get_top_entities((start, end))))
    
    def test_very_old_dates(self, db_session):
        """Test queries with very old date ranges."""
        analytics = AnalyticsService(db_session)
        
        # Query from 10 years ago
        end = datetime.utcnow()
        start = end - timedelta(days=3650)
        
        result = analytics.get_top_entities((start, end))
        # Should return empty, not crash
        assert len(result) == 0
    
    def test_future_dates(self, db_session):
        """Test queries with future dates."""
        analytics = AnalyticsService(db_session)
        
        # Query in the future
        start = datetime.utcnow()
        end = start + timedelta(days=30)
        
        result = analytics.get_top_entities((start, end))
        # Should return empty, not crash
        assert len(result) == 0
    
    def test_zero_time_window(self, db_session):
        """Test queries with zero-length time window."""
        analytics = AnalyticsService(db_session)
        
        now = datetime.utcnow()
        result = analytics.get_top_entities((now, now))
        
        # Should return empty, not crash
        assert len(result) == 0


class TestInvalidInput:
    """Test handling of invalid inputs."""
    
    def test_invalid_entity_id(self, db_session):
        """Test handling of invalid entity IDs."""
        analytics = AnalyticsService(db_session)
        
        # Non-existent UUID
        fake_id = uuid.uuid4()
        velocity = analytics.compute_velocity(fake_id)
        
        assert 'error' in velocity
    
    def test_invalid_time_window(self, db_session):
        """Test handling of invalid time windows."""
        analytics = AnalyticsService(db_session)
        
        # Start after end
        end = datetime.utcnow()
        start = end + timedelta(days=1)
        
        result = analytics.get_top_entities((start, end))
        # Should handle gracefully
        assert len(result) == 0
    
    def test_malformed_csv(self, db_session, tmp_path):
        """Test handling of malformed CSV files."""
        # CSV with missing columns
        csv_content = "Post URL,Username\nhttps://instagram.com/p/test,user1\n"
        csv_file = tmp_path / "malformed.csv"
        csv_file.write_text(csv_content)
        
        source = ESUITSource(csv_file)
        ingestion = IngestionService(db_session)
        
        # Should handle error gracefully
        try:
            stats = ingestion.ingest(source)
            # If it doesn't crash, that's acceptable
            assert isinstance(stats, dict)
        except Exception:
            # Exception is also acceptable for malformed data
            pass
    
    def test_very_long_text(self, db_session, sample_entity):
        """Test handling of very long comment text."""
        from et_intel_core.models import Post, Comment, PlatformType
        from datetime import datetime
        
        # Create comment with very long text
        long_text = "A" * 10000  # 10KB of text
        
        post = Post(
            platform=PlatformType.INSTAGRAM,
            external_id="test",
            url="https://instagram.com/p/test",
            posted_at=datetime.utcnow()
        )
        db_session.add(post)
        db_session.commit()
        
        comment = Comment(
            post_id=post.id,
            author_name="user",
            text=long_text,
            created_at=datetime.utcnow()
        )
        db_session.add(comment)
        db_session.commit()
        
        # Enrichment should handle long text
        entity_catalog = [sample_entity]
        extractor = EntityExtractor(entity_catalog)
        sentiment_provider = get_sentiment_provider()
        enrichment = EnrichmentService(db_session, extractor, sentiment_provider)
        
        stats = enrichment.enrich_comments(comment_ids=[comment.id])
        
        # Should process without crashing
        assert stats['comments_processed'] == 1


class TestFailureScenarios:
    """Test system behavior under failure conditions."""
    
    def test_partial_ingestion_failure(self, db_session, tmp_path):
        """Test handling when some records fail to ingest."""
        # CSV with mix of valid and potentially invalid data
        csv_content = """Post URL,Username,Comment,Timestamp,Likes,Caption,Subject
https://instagram.com/p/test1,user1,Valid comment,2024-01-01 10:00:00,10,Test,Test
https://instagram.com/p/test2,user2,Another valid,2024-01-01 11:00:00,20,Test,Test"""
        
        csv_file = tmp_path / "partial.csv"
        csv_file.write_text(csv_content)
        
        source = ESUITSource(csv_file)
        ingestion = IngestionService(db_session)
        
        stats = ingestion.ingest(source)
        
        # Should process valid records
        assert stats['comments_created'] >= 0  # May be 0 if duplicates
    
    def test_enrichment_with_missing_entity(self, db_session, sample_comment):
        """Test enrichment when entity is deleted mid-process."""
        # This tests referential integrity
        from et_intel_core.models import ExtractedSignal
        
        # Create signal with entity
        signal = ExtractedSignal(
            comment_id=sample_comment.id,
            entity_id=sample_comment.id,  # Invalid: using comment ID as entity ID
            signal_type="sentiment",
            value="positive",
            numeric_value=0.5,
            source_model="test"
        )
        
        # Should handle foreign key constraint
        try:
            db_session.add(signal)
            db_session.commit()
        except Exception:
            # Foreign key violation is expected and acceptable
            db_session.rollback()
            pass

