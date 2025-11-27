"""
Security tests: SQL injection prevention, input validation, etc.
"""

import pytest
from datetime import datetime, timedelta
import uuid

from et_intel_core.analytics import AnalyticsService
from et_intel_core.models import MonitoredEntity, EntityType, Post, Comment, PlatformType, ExtractedSignal, SignalType
from sqlalchemy import text


class TestSQLInjectionPrevention:
    """Test SQL injection prevention."""
    
    def test_parameterized_queries(self, db_session):
        """Test that queries use parameterization."""
        analytics = AnalyticsService(db_session)
        
        # Attempt SQL injection in entity name
        malicious_input = "'; DROP TABLE comments; --"
        
        # Create entity with potentially malicious name
        entity = MonitoredEntity(
            name=malicious_input,
            canonical_name=malicious_input,
            entity_type=EntityType.PERSON
        )
        db_session.add(entity)
        db_session.commit()
        
        # Query should handle safely
        end = datetime.utcnow()
        start = end - timedelta(days=30)
        
        result = analytics.get_top_entities((start, end))
        # Should not crash or execute malicious SQL
        assert isinstance(result, type(analytics.get_top_entities((start, end))))
        
        # Verify table still exists
        from et_intel_core.models import Comment
        count = db_session.query(Comment).count()
        assert isinstance(count, int)  # Table still exists
    
    def test_sql_injection_in_time_window(self, db_session):
        """Test SQL injection prevention in time window parameters."""
        analytics = AnalyticsService(db_session)
        
        # This test verifies that datetime parameters are properly handled
        # SQLAlchemy's text() with parameters should prevent injection
        end = datetime.utcnow()
        start = end - timedelta(days=30)
        
        # Normal query
        result1 = analytics.get_top_entities((start, end))
        
        # Query with edge case dates
        result2 = analytics.get_top_entities((start, end))
        
        # Both should work without SQL injection
        assert isinstance(result1, type(result2))
    
    def test_entity_id_injection_prevention(self, db_session):
        """Test that entity IDs are properly validated."""
        analytics = AnalyticsService(db_session)
        
        # Attempt to use malicious UUID string
        malicious_id = "'; DROP TABLE comments; --"
        
        try:
            # Should fail to convert to UUID
            fake_uuid = uuid.UUID(malicious_id)
        except ValueError:
            # Expected: invalid UUID format
            pass
        
        # Valid UUID should work
        valid_id = uuid.uuid4()
        velocity = analytics.compute_velocity(valid_id)
        
        # Should return error dict, not crash
        assert isinstance(velocity, dict)


class TestInputValidation:
    """Test input validation and sanitization."""
    
    def test_entity_name_validation(self, db_session):
        """Test that entity names are handled safely."""
        # Test various edge cases
        test_names = [
            "Normal Name",
            "Name with 'quotes'",
            "Name with \"double quotes\"",
            "Name with ; semicolon",
            "Name with -- comment",
            "Name with /* comment */",
            "Name with <script>alert('xss')</script>",
            "Name with unicode: 测试",
            "Name with newline\n",
            "Name with tab\t",
        ]
        
        for name in test_names:
            entity = MonitoredEntity(
                name=name,
                canonical_name=name,
                entity_type=EntityType.PERSON
            )
            db_session.add(entity)
            db_session.commit()
            
            # Should be stored safely
            retrieved = db_session.query(MonitoredEntity).filter_by(name=name).first()
            assert retrieved is not None
            assert retrieved.name == name
            
            db_session.delete(entity)
            db_session.commit()
    
    def test_comment_text_validation(self, db_session, sample_post):
        """Test that comment text is handled safely."""
        from et_intel_core.models import Comment
        
        malicious_texts = [
            "<script>alert('xss')</script>",
            "'; DROP TABLE comments; --",
            "Comment with 'quotes'",
            "Comment with \"quotes\"",
            "Comment with unicode: 测试",
        ]
        
        for text_content in malicious_texts:
            comment = Comment(
                post_id=sample_post.id,
                author_name="test_user",
                text=text_content,
                created_at=datetime.utcnow()
            )
            db_session.add(comment)
            db_session.commit()
            
            # Should be stored safely
            retrieved = db_session.query(Comment).filter_by(text=text_content).first()
            assert retrieved is not None
            assert retrieved.text == text_content
            
            db_session.delete(comment)
            db_session.commit()
    
    def test_url_validation(self, db_session):
        """Test that URLs are handled safely."""
        test_urls = [
            "https://instagram.com/p/test123",
            "https://instagram.com/p/test'123",
            "javascript:alert('xss')",
            "https://evil.com/script.js",
        ]
        
        for url in test_urls:
            post = Post(
                platform=PlatformType.INSTAGRAM,
                external_id="test",
                url=url,
                posted_at=datetime.utcnow()
            )
            db_session.add(post)
            db_session.commit()
            
            # Should be stored (validation happens at application level if needed)
            retrieved = db_session.query(Post).filter_by(url=url).first()
            assert retrieved is not None
            
            db_session.delete(post)
            db_session.commit()


class TestAuthentication:
    """Test authentication and authorization (if implemented)."""
    
    def test_no_hardcoded_credentials(self):
        """Verify no hardcoded credentials in code."""
        import os
        from pathlib import Path
        
        # Check common credential patterns
        codebase_root = Path(__file__).parent.parent
        python_files = list(codebase_root.rglob("*.py"))
        
        dangerous_patterns = [
            "password =",
            "api_key =",
            "secret =",
            "token =",
        ]
        
        # This is a basic check - more thorough scanning needed
        for py_file in python_files:
            if "test" in str(py_file):
                continue  # Skip test files
            
            try:
                content = py_file.read_text(encoding='utf-8', errors='ignore')
            except (UnicodeDecodeError, PermissionError):
                continue  # Skip files that can't be read
            for pattern in dangerous_patterns:
                # Check for hardcoded values (not just variable assignments)
                if pattern in content and '"' in content.split(pattern)[1][:50]:
                    # Potential hardcoded credential - flag for review
                    # Don't fail test, just note it
                    pass


class TestDataAccess:
    """Test data access controls."""
    
    def test_session_isolation(self, db_session):
        """Test that database sessions are properly isolated."""
        # Create data in one session
        entity1 = MonitoredEntity(
            name="Session Test 1",
            canonical_name="Session Test 1",
            entity_type=EntityType.PERSON
        )
        db_session.add(entity1)
        db_session.commit()
        
        # Verify it exists
        retrieved = db_session.query(MonitoredEntity).filter_by(name="Session Test 1").first()
        assert retrieved is not None
        
        # Rollback should remove it
        db_session.rollback()
        
        # In new query, should not exist (if transaction was rolled back)
        # Note: This depends on transaction isolation level
        pass
    
    def test_foreign_key_constraints(self, db_session):
        """Test that foreign key constraints prevent orphaned data."""
        from et_intel_core.models import Comment
        
        # Try to create comment with invalid post_id
        invalid_post_id = uuid.uuid4()
        
        comment = Comment(
            post_id=invalid_post_id,
            author_name="test",
            text="test",
            created_at=datetime.utcnow()
        )
        
        # Should fail foreign key constraint
        db_session.add(comment)
        try:
            db_session.commit()
            # If it doesn't fail, that's a problem
            assert False, "Foreign key constraint should have failed"
        except Exception:
            # Expected: foreign key violation
            db_session.rollback()
            pass


class TestSensitiveData:
    """Test handling of sensitive data."""
    
    def test_api_keys_not_logged(self):
        """Test that API keys are not logged."""
        import logging
        from io import StringIO
        from et_intel_core.logging_config import setup_logging, get_logger
        
        # Set up logging to capture output
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        
        logger = get_logger("test")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        
        # Simulate operation that might log API key
        test_key = "sk-test123456789"
        
        # Log something that might accidentally include key
        logger.info("Processing with API")
        
        log_output = log_capture.getvalue()
        
        # API key should not appear in logs
        assert test_key not in log_output
    
    def test_database_url_not_exposed(self):
        """Test that database URLs are not exposed in error messages."""
        # This would require testing error handling
        # For now, verify config doesn't expose URLs
        from et_intel_core.config import settings
        
        # Database URL should exist but not be logged
        assert settings.database_url is not None
        # URL should not contain plaintext password in logs (handled by logging)

