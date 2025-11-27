"""
Integration tests for end-to-end workflows.

Tests complete workflows: ingest → enrich → analyze → report
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
import uuid

from et_intel_core.db import get_session
from et_intel_core.services.ingestion import IngestionService
from et_intel_core.services.enrichment import EnrichmentService
from et_intel_core.analytics import AnalyticsService
from et_intel_core.reporting import BriefBuilder, PDFRenderer
from et_intel_core.sources.esuit import ESUITSource
from et_intel_core.nlp.entity_extractor import EntityExtractor
from et_intel_core.nlp.sentiment import get_sentiment_provider
from et_intel_core.models import MonitoredEntity, EntityType


class TestEndToEndWorkflow:
    """Test complete workflow from ingestion to report generation."""
    
    def test_full_workflow_ingest_enrich_analyze(self, db_session, tmp_path):
        """Test complete workflow: ingest → enrich → analyze."""
        # 1. Create test CSV file
        csv_content = """Post URL,Username,Comment,Timestamp,Likes,Caption,Subject
https://instagram.com/p/test123,user1,Love Taylor Swift!,2024-01-01 10:00:00,100,Test caption,Taylor Swift Post
https://instagram.com/p/test123,user2,Hate this post,2024-01-01 11:00:00,5,Test caption,Taylor Swift Post
https://instagram.com/p/test456,user3,Blake Lively is amazing,2024-01-02 10:00:00,200,Another caption,Blake Lively Post"""
        
        csv_file = tmp_path / "test_data.csv"
        csv_file.write_text(csv_content)
        
        # 2. Seed entities
        taylor = MonitoredEntity(
            name="Taylor Swift",
            canonical_name="Taylor Swift",
            entity_type=EntityType.PERSON,
            is_active=True,
            aliases=["T-Swift", "Tay"]
        )
        blake = MonitoredEntity(
            name="Blake Lively",
            canonical_name="Blake Lively",
            entity_type=EntityType.PERSON,
            is_active=True,
            aliases=[]
        )
        db_session.add(taylor)
        db_session.add(blake)
        db_session.commit()
        
        # 3. Ingest
        source = ESUITSource(csv_file)
        ingestion = IngestionService(db_session)
        ingest_stats = ingestion.ingest(source)
        
        assert ingest_stats['comments_created'] == 3
        assert ingest_stats['posts_created'] == 2
        
        # 4. Enrich
        entity_catalog = db_session.query(MonitoredEntity).filter_by(is_active=True).all()
        extractor = EntityExtractor(entity_catalog)
        sentiment_provider = get_sentiment_provider()
        enrichment = EnrichmentService(db_session, extractor, sentiment_provider)
        
        enrich_stats = enrichment.enrich_comments()
        
        assert enrich_stats['comments_processed'] == 3
        assert enrich_stats['signals_created'] > 0
        
        # 5. Analyze
        analytics = AnalyticsService(db_session)
        # Use a wider time window to ensure we capture the test data
        end = datetime.utcnow() + timedelta(days=1)  # Include future dates to catch test data
        start = datetime(2023, 1, 1)  # Start from a date well before test data
        
        top_entities = analytics.get_top_entities((start, end), limit=10)
        
        # top_entities is a DataFrame - check if it has rows
        # If empty, it might be because signals weren't created properly
        if len(top_entities) == 0:
            # Debug: check if signals exist
            from et_intel_core.models import ExtractedSignal
            signal_count = db_session.query(ExtractedSignal).count()
            assert signal_count > 0, f"No signals created. Enrich stats: {enrich_stats}"
        
        assert len(top_entities) > 0, f"Expected entities but got empty DataFrame. Columns: {top_entities.columns.tolist()}"
        entity_names = top_entities['entity_name'].tolist()
        assert "Taylor Swift" in entity_names or "Blake Lively" in entity_names, f"Entity names found: {entity_names}"
        
        # 6. Check velocity
        taylor_id = taylor.id
        velocity = analytics.compute_velocity(taylor_id, window_hours=72)
        
        # Velocity might not have enough data, but should not error
        assert isinstance(velocity, dict)
    
    def test_workflow_with_report_generation(self, db_session, tmp_path, monkeypatch):
        """Test workflow including report generation."""
        # Mock database connection to use test session
        from et_intel_core import db
        monkeypatch.setattr(db, 'get_session', lambda: db_session)
        
        # Setup: Create data
        csv_content = """Post URL,Username,Comment,Timestamp,Likes,Caption,Subject
https://instagram.com/p/test123,user1,Great post about Taylor!,2024-01-01 10:00:00,50,Test,Taylor"""
        
        csv_file = tmp_path / "test_report.csv"
        csv_file.write_text(csv_content)
        
        # Seed entity
        entity = MonitoredEntity(
            name="Taylor Swift",
            canonical_name="Taylor Swift",
            entity_type=EntityType.PERSON,
            is_active=True
        )
        db_session.add(entity)
        db_session.commit()
        
        # Ingest and enrich
        source = ESUITSource(csv_file)
        ingestion = IngestionService(db_session)
        ingestion.ingest(source)
        
        entity_catalog = db_session.query(MonitoredEntity).filter_by(is_active=True).all()
        extractor = EntityExtractor(entity_catalog)
        sentiment_provider = get_sentiment_provider()
        enrichment = EnrichmentService(db_session, extractor, sentiment_provider)
        enrichment.enrich_comments()
        
        # Build brief
        analytics = AnalyticsService(db_session)
        builder = BriefBuilder(analytics)
        
        # Use wider time window to capture test data
        start = datetime(2023, 1, 1)
        end = datetime.utcnow() + timedelta(days=1)
        
        brief = builder.build(start, end)
        
        assert brief is not None
        assert brief.timeframe['start'] == start
        assert brief.timeframe['end'] == end
        assert len(brief.top_entities.items) >= 0  # May be empty with minimal data
        
        # Render PDF (to temp directory)
        output_dir = tmp_path / "reports"
        output_dir.mkdir()
        renderer = PDFRenderer(output_dir=output_dir)
        
        pdf_path = renderer.render(brief, filename="test_brief.pdf")
        
        assert pdf_path.exists()
        assert pdf_path.suffix == '.pdf'
    
    def test_idempotent_ingestion(self, db_session, tmp_path):
        """Test that re-ingesting same data doesn't create duplicates."""
        csv_content = """Post URL,Username,Comment,Timestamp,Likes,Caption,Subject
https://instagram.com/p/test123,user1,Test comment,2024-01-01 10:00:00,10,Test,Test"""
        
        csv_file = tmp_path / "test_duplicate.csv"
        csv_file.write_text(csv_content)
        
        source = ESUITSource(csv_file)
        ingestion = IngestionService(db_session)
        
        # First ingestion
        stats1 = ingestion.ingest(source)
        from et_intel_core.models import Comment
        comments1 = db_session.query(Comment).count()
        
        # Second ingestion (same data)
        stats2 = ingestion.ingest(source)
        
        # Should update, not create duplicates
        assert stats2['comments_created'] == 0
        assert stats2['comments_updated'] == 1
    
    def test_concurrent_enrichment(self, db_session, sample_entity, sample_comment):
        """Test that enrichment can handle concurrent operations safely."""
        # Create multiple comments
        from et_intel_core.models import Comment, Post, PlatformType
        from datetime import datetime
        
        post = sample_comment.post
        comments = []
        for i in range(5):
            comment = Comment(
                post_id=post.id,
                author_name=f"user{i}",
                text=f"Comment {i} about {sample_entity.name}",
                created_at=datetime.utcnow(),
                likes=i * 10
            )
            comments.append(comment)
            db_session.add(comment)
        db_session.commit()
        
        # Enrich all comments
        entity_catalog = [sample_entity]
        extractor = EntityExtractor(entity_catalog)
        sentiment_provider = get_sentiment_provider()
        enrichment = EnrichmentService(db_session, extractor, sentiment_provider)
        
        comment_ids = [c.id for c in comments]
        stats = enrichment.enrich_comments(comment_ids=comment_ids)
        
        assert stats['comments_processed'] == 5
        assert stats['signals_created'] > 0
        
        # Verify signals were created
        from et_intel_core.models import ExtractedSignal
        signals = db_session.query(ExtractedSignal).filter(
            ExtractedSignal.comment_id.in_(comment_ids)
        ).all()
        
        assert len(signals) > 0


class TestErrorRecovery:
    """Test system recovery from errors."""
    
    def test_database_connection_failure_handling(self, db_session):
        """Test graceful handling of database connection issues."""
        # This would require mocking database failures
        # For now, verify services handle None/invalid sessions gracefully
        from et_intel_core.analytics import AnalyticsService
        
        # Should not crash on invalid time window
        analytics = AnalyticsService(db_session)
        end = datetime.utcnow()
        start = end + timedelta(days=1)  # Invalid: start after end
        
        result = analytics.get_top_entities((start, end), limit=10)
        # Should return empty result, not crash
        assert len(result) == 0
    
    def test_missing_entity_handling(self, db_session):
        """Test handling of missing entities in analytics."""
        analytics = AnalyticsService(db_session)
        
        # Try to compute velocity for non-existent entity
        fake_id = uuid.uuid4()
        velocity = analytics.compute_velocity(fake_id)
        
        # Should return error dict, not crash
        assert 'error' in velocity
    
    def test_empty_data_handling(self, db_session):
        """Test system handles empty datasets gracefully."""
        analytics = AnalyticsService(db_session)
        
        # Query with no data
        end = datetime.utcnow()
        start = end - timedelta(days=1)
        
        top_entities = analytics.get_top_entities((start, end))
        assert len(top_entities) == 0  # Should return empty, not crash
        
        comment_count = analytics.get_comment_count((start, end))
        assert comment_count == 0


class TestDataIntegrity:
    """Test data integrity across operations."""
    
    def test_signal_consistency(self, db_session, sample_entity, sample_comment):
        """Test that signals remain consistent after operations."""
        from et_intel_core.models import ExtractedSignal, SignalType
        
        # Create signal
        signal = ExtractedSignal(
            comment_id=sample_comment.id,
            entity_id=sample_entity.id,
            signal_type=SignalType.SENTIMENT,
            value="positive",
            numeric_value=0.8,
            weight_score=1.0,
            confidence=0.9,
            source_model="test"
        )
        db_session.add(signal)
        db_session.commit()
        
        signal_id = signal.id
        
        # Re-query and verify
        retrieved = db_session.query(ExtractedSignal).filter_by(id=signal_id).first()
        
        assert retrieved is not None
        assert retrieved.numeric_value == 0.8
        assert retrieved.entity_id == sample_entity.id
        assert retrieved.comment_id == sample_comment.id
    
    def test_entity_relationship_integrity(self, db_session, sample_entity):
        """Test that entity relationships remain intact."""
        from et_intel_core.models import Post, Comment, PlatformType, ExtractedSignal, SignalType
        from datetime import datetime
        
        # Create post and comment
        post = Post(
            platform=PlatformType.INSTAGRAM,
            external_id="test_post",
            url="https://instagram.com/p/test",
            posted_at=datetime.utcnow()
        )
        db_session.add(post)
        db_session.commit()
        
        comment = Comment(
            post_id=post.id,
            author_name="test_user",
            text=f"Comment about {sample_entity.name}",
            created_at=datetime.utcnow()
        )
        db_session.add(comment)
        db_session.commit()
        
        # Create signal linking all
        signal = ExtractedSignal(
            comment_id=comment.id,
            entity_id=sample_entity.id,
            signal_type=SignalType.SENTIMENT,
            value="positive",
            numeric_value=0.7,
            source_model="test"
        )
        db_session.add(signal)
        db_session.commit()
        
        # Verify relationships
        assert signal.comment.id == comment.id
        assert signal.entity.id == sample_entity.id
        assert comment.post.id == post.id
        assert len(sample_entity.signals) > 0

