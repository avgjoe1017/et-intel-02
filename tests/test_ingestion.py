"""
Tests for ingestion service.
"""

from datetime import datetime
from pathlib import Path
import tempfile
import pandas as pd
import pytest

from et_intel_core.services import IngestionService
from et_intel_core.sources import ESUITSource, ApifySource
from et_intel_core.models import Post, Comment


def test_esuit_source_parsing():
    """Test ESUIT CSV parsing."""
    # Create temporary CSV file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        df = pd.DataFrame({
            'Post URL': ['https://instagram.com/p/ABC123/'],
            'Caption': ['Test caption'],
            'Subject': ['Test subject'],
            'Username': ['test_user'],
            'Comment': ['Test comment'],
            'Timestamp': ['2024-01-01 12:00:00'],
            'Likes': [42]
        })
        df.to_csv(f.name, index=False)
        csv_path = Path(f.name)
    
    try:
        # Parse CSV
        source = ESUITSource(csv_path)
        records = list(source.iter_records())
        
        assert len(records) == 1
        record = records[0]
        assert record.platform == "instagram"
        assert record.external_post_id == "ABC123"
        assert record.comment_author == "test_user"
        assert record.comment_text == "Test comment"
        assert record.like_count == 42
    finally:
        csv_path.unlink()


def test_apify_source_parsing():
    """Test Apify CSV parsing."""
    # Create temporary CSV file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        df = pd.DataFrame({
            'shortCode': ['ABC123'],
            'url': ['https://instagram.com/p/ABC123/'],
            'caption': ['Test caption'],
            'ownerUsername': ['test_user'],
            'text': ['Test comment'],
            'timestamp': ['2024-01-01 12:00:00'],
            'likesCount': [42]
        })
        df.to_csv(f.name, index=False)
        csv_path = Path(f.name)
    
    try:
        # Parse CSV
        source = ApifySource(csv_path)
        records = list(source.iter_records())
        
        assert len(records) == 1
        record = records[0]
        assert record.platform == "instagram"
        assert record.external_post_id == "ABC123"
        assert record.comment_author == "test_user"
        assert record.comment_text == "Test comment"
        assert record.like_count == 42
    finally:
        csv_path.unlink()


def test_ingestion_service_creates_posts_and_comments(db_session):
    """Test that ingestion service creates posts and comments."""
    # Create temporary CSV
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        df = pd.DataFrame({
            'Post URL': ['https://instagram.com/p/ABC123/'],
            'Caption': ['Test caption'],
            'Subject': ['Test subject'],
            'Username': ['test_user'],
            'Comment': ['Test comment'],
            'Timestamp': ['2024-01-01 12:00:00'],
            'Likes': [42]
        })
        df.to_csv(f.name, index=False)
        csv_path = Path(f.name)
    
    try:
        # Ingest
        source = ESUITSource(csv_path)
        service = IngestionService(db_session)
        stats = service.ingest(source)
        
        # Verify stats
        assert stats["posts_created"] == 1
        assert stats["comments_created"] == 1
        assert stats["posts_updated"] == 0
        assert stats["comments_updated"] == 0
        
        # Verify database
        posts = db_session.query(Post).all()
        comments = db_session.query(Comment).all()
        
        assert len(posts) == 1
        assert len(comments) == 1
        assert posts[0].external_id == "ABC123"
        assert comments[0].text == "Test comment"
    finally:
        csv_path.unlink()


def test_ingestion_service_idempotent(db_session):
    """Test that ingestion service is idempotent (no duplicates)."""
    # Create temporary CSV
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        df = pd.DataFrame({
            'Post URL': ['https://instagram.com/p/ABC123/'],
            'Caption': ['Test caption'],
            'Subject': ['Test subject'],
            'Username': ['test_user'],
            'Comment': ['Test comment'],
            'Timestamp': ['2024-01-01 12:00:00'],
            'Likes': [42]
        })
        df.to_csv(f.name, index=False)
        csv_path = Path(f.name)
    
    try:
        source = ESUITSource(csv_path)
        service = IngestionService(db_session)
        
        # First ingestion
        stats1 = service.ingest(source)
        assert stats1["posts_created"] == 1
        assert stats1["comments_created"] == 1
        
        # Second ingestion (should update, not create)
        source2 = ESUITSource(csv_path)
        stats2 = service.ingest(source2)
        assert stats2["posts_created"] == 0
        assert stats2["posts_updated"] == 1
        assert stats2["comments_created"] == 0
        assert stats2["comments_updated"] == 1
        
        # Verify no duplicates
        posts = db_session.query(Post).all()
        comments = db_session.query(Comment).all()
        assert len(posts) == 1
        assert len(comments) == 1
    finally:
        csv_path.unlink()


def test_ingestion_service_updates_likes(db_session):
    """Test that ingestion service updates like counts."""
    # Create first CSV with 42 likes
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        df = pd.DataFrame({
            'Post URL': ['https://instagram.com/p/ABC123/'],
            'Caption': ['Test caption'],
            'Subject': ['Test subject'],
            'Username': ['test_user'],
            'Comment': ['Test comment'],
            'Timestamp': ['2024-01-01 12:00:00'],
            'Likes': [42]
        })
        df.to_csv(f.name, index=False)
        csv_path = Path(f.name)
    
    try:
        # First ingestion
        source = ESUITSource(csv_path)
        service = IngestionService(db_session)
        service.ingest(source)
        
        comment = db_session.query(Comment).first()
        assert comment.likes == 42
        
        # Create second CSV with updated likes
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f2:
            df2 = pd.DataFrame({
                'Post URL': ['https://instagram.com/p/ABC123/'],
                'Caption': ['Test caption'],
                'Subject': ['Test subject'],
                'Username': ['test_user'],
                'Comment': ['Test comment'],
                'Timestamp': ['2024-01-01 12:00:00'],
                'Likes': [100]  # Updated
            })
            df2.to_csv(f2.name, index=False)
            csv_path2 = Path(f2.name)
        
        try:
            # Second ingestion
            source2 = ESUITSource(csv_path2)
            service.ingest(source2)
            
            # Verify likes updated
            db_session.expire_all()  # Refresh from database
            comment = db_session.query(Comment).first()
            assert comment.likes == 100
        finally:
            csv_path2.unlink()
    finally:
        csv_path.unlink()

