"""
Performance tests and benchmarks.

Tests system performance under various loads and conditions.
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path

# Note: Performance tests use db_session fixture, not get_session
from et_intel_core.services.ingestion import IngestionService
from et_intel_core.services.enrichment import EnrichmentService
from et_intel_core.analytics import AnalyticsService
from et_intel_core.sources.esuit import ESUITSource
from et_intel_core.nlp.entity_extractor import EntityExtractor
from et_intel_core.nlp.sentiment import get_sentiment_provider
from et_intel_core.models import MonitoredEntity, EntityType, Post, Comment, PlatformType, ExtractedSignal, SignalType


class TestIngestionPerformance:
    """Benchmark ingestion performance."""
    
    @pytest.mark.benchmark
    def test_ingestion_throughput(self, db_session, tmp_path):
        """Benchmark ingestion speed."""
        # Create CSV with 100 comments
        csv_lines = ["Post URL,Username,Comment,Timestamp,Likes,Caption,Subject\n"]
        for i in range(100):
            csv_lines.append(
                f"https://instagram.com/p/post{i},user{i},Comment {i},2024-01-01 10:00:00,{i},Caption,Subject\n"
            )
        
        csv_file = tmp_path / "perf_test.csv"
        csv_file.write_text("".join(csv_lines))
        
        source = ESUITSource(csv_file)
        ingestion = IngestionService(db_session)
        
        result = ingestion.ingest(source)
        
        # Target: 100 comments/second
        # This is a benchmark, not a strict assertion
        assert result['comments_created'] == 100
    
    def test_large_file_ingestion(self, db_session, tmp_path):
        """Test ingestion of large file (1000+ comments)."""
        csv_lines = ["Post URL,Username,Comment,Timestamp,Likes,Caption,Subject\n"]
        for i in range(1000):
            csv_lines.append(
                f"https://instagram.com/p/post{i},user{i},Comment {i},2024-01-01 10:00:00,{i},Caption,Subject\n"
            )
        
        csv_file = tmp_path / "large_perf.csv"
        csv_file.write_text("".join(csv_lines))
        
        source = ESUITSource(csv_file)
        ingestion = IngestionService(db_session)
        
        import time
        start = time.time()
        stats = ingestion.ingest(source)
        elapsed = time.time() - start
        
        # Should complete in reasonable time (<30 seconds for 1000 comments)
        assert elapsed < 30
        assert stats['comments_created'] == 1000


class TestEnrichmentPerformance:
    """Benchmark enrichment performance."""
    
    @pytest.mark.benchmark
    def test_enrichment_throughput(self, db_session, sample_entity):
        """Benchmark enrichment speed."""
        # Create 50 comments
        post = Post(
            platform=PlatformType.INSTAGRAM,
            external_id="perf_post",
            url="https://instagram.com/p/perf",
            posted_at=datetime.utcnow()
        )
        db_session.add(post)
        db_session.commit()
        
        comments = []
        for i in range(50):
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
        
        entity_catalog = [sample_entity]
        extractor = EntityExtractor(entity_catalog)
        sentiment_provider = get_sentiment_provider()
        enrichment = EnrichmentService(db_session, extractor, sentiment_provider)
        
        comment_ids = [c.id for c in comments]
        
        result = enrichment.enrich_comments(comment_ids=comment_ids)
        
        # Target: 50 comments/second
        assert result['comments_processed'] == 50


class TestAnalyticsPerformance:
    """Benchmark analytics query performance."""
    
    def test_top_entities_query_performance(self, db_session):
        """Benchmark top entities query."""
        # Create test data
        entity = MonitoredEntity(
            name="Test Entity",
            canonical_name="Test Entity",
            entity_type=EntityType.PERSON
        )
        db_session.add(entity)
        db_session.commit()
        
        # Create 100 posts with signals
        for i in range(100):
            post = Post(
                platform=PlatformType.INSTAGRAM,
                external_id=f"post{i}",
                url=f"https://instagram.com/p/post{i}",
                posted_at=datetime.utcnow() - timedelta(days=i % 30)
            )
            db_session.add(post)
            db_session.flush()
            
            comment = Comment(
                post_id=post.id,
                author_name=f"user{i}",
                text=f"Comment about {entity.name}",
                created_at=datetime.utcnow() - timedelta(days=i % 30),
                likes=i
            )
            db_session.add(comment)
            db_session.flush()
            
            signal = ExtractedSignal(
                comment_id=comment.id,
                entity_id=entity.id,
                signal_type=SignalType.SENTIMENT,
                value="positive" if i % 2 == 0 else "negative",
                numeric_value=0.5 if i % 2 == 0 else -0.5,
                source_model="test"
            )
            db_session.add(signal)
        db_session.commit()
        
        analytics = AnalyticsService(db_session)
        end = datetime.utcnow()
        start = end - timedelta(days=30)
        
        result = analytics.get_top_entities((start, end), limit=20)
        
        # Target: <1 second (p95)
        assert len(result) > 0
    
    @pytest.mark.benchmark
    def test_velocity_computation_performance(self, db_session, sample_entity):
        """Benchmark velocity computation."""
        # Create signals over time
        for i in range(50):
            post = Post(
                platform=PlatformType.INSTAGRAM,
                external_id=f"vpost{i}",
                url=f"https://instagram.com/p/vpost{i}",
                posted_at=datetime.utcnow() - timedelta(hours=i)
            )
            db_session.add(post)
            db_session.flush()
            
            comment = Comment(
                post_id=post.id,
                author_name=f"user{i}",
                text=f"Comment about {sample_entity.name}",
                created_at=datetime.utcnow() - timedelta(hours=i),
                likes=i
            )
            db_session.add(comment)
            db_session.flush()
            
            signal = ExtractedSignal(
                comment_id=comment.id,
                entity_id=sample_entity.id,
                signal_type=SignalType.SENTIMENT,
                value="positive",
                numeric_value=0.5 + (i * 0.01),  # Varying sentiment
                source_model="test"
            )
            db_session.add(signal)
        db_session.commit()
        
        analytics = AnalyticsService(db_session)
        
        result = analytics.compute_velocity(sample_entity.id, window_hours=72)
        
        # Should complete quickly
        assert isinstance(result, dict)


class TestQueryOptimization:
    """Test query performance with indexes."""
    
    def test_indexed_query_performance(self, db_session):
        """Test that queries use indexes effectively."""
        # Create data
        entity = MonitoredEntity(
            name="Indexed Entity",
            canonical_name="Indexed Entity",
            entity_type=EntityType.PERSON
        )
        db_session.add(entity)
        db_session.commit()
        
        # Create signals
        for i in range(200):
            post = Post(
                platform=PlatformType.INSTAGRAM,
                external_id=f"idx_post{i}",
                url=f"https://instagram.com/p/idx{i}",
                posted_at=datetime.utcnow() - timedelta(days=i % 30)
            )
            db_session.add(post)
            db_session.flush()
            
            comment = Comment(
                post_id=post.id,
                author_name=f"user{i}",
                text=f"Comment {i}",
                created_at=datetime.utcnow() - timedelta(days=i % 30),
                likes=i
            )
            db_session.add(comment)
            db_session.flush()
            
            signal = ExtractedSignal(
                comment_id=comment.id,
                entity_id=entity.id,
                signal_type=SignalType.SENTIMENT,
                value="positive",
                numeric_value=0.5,
                source_model="test"
            )
            db_session.add(signal)
        db_session.commit()
        
        analytics = AnalyticsService(db_session)
        end = datetime.utcnow()
        start = end - timedelta(days=30)
        
        import time
        start_time = time.time()
        result = analytics.get_top_entities((start, end), limit=10)
        elapsed = time.time() - start_time
        
        # With indexes, should be fast (<0.5 seconds for 200 records)
        assert elapsed < 0.5
        assert len(result) > 0


class TestMemoryUsage:
    """Test memory usage under load."""
    
    def test_large_dataset_memory(self, db_session, sample_entity):
        """Test memory usage with large dataset."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Create 500 comments
        post = Post(
            platform=PlatformType.INSTAGRAM,
            external_id="mem_post",
            url="https://instagram.com/p/mem",
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
        
        # Enrich
        entity_catalog = [sample_entity]
        extractor = EntityExtractor(entity_catalog)
        sentiment_provider = get_sentiment_provider()
        enrichment = EnrichmentService(db_session, extractor, sentiment_provider)
        
        comment_ids = [c.id for c in comments]
        enrichment.enrich_comments(comment_ids=comment_ids)
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (<500MB for 500 comments)
        # This is a sanity check, not a strict limit
        assert memory_increase < 500

