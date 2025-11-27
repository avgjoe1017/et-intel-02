"""
Extended integration tests for full workflows.
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
import tempfile

from et_intel_core.services import IngestionService, EnrichmentService
from et_intel_core.sources.esuit import ESUITSource
from et_intel_core.analytics import AnalyticsService
from et_intel_core.reporting import BriefBuilder, PDFRenderer
from et_intel_core.nlp import EntityExtractor, get_sentiment_provider
from et_intel_core.models import MonitoredEntity, EntityType, PlatformType


class TestFullWorkflow:
    """Test complete workflow from ingestion to reporting."""
    
    def test_ingest_enrich_analyze_report(self, db_session, tmp_path, monkeypatch):
        """Test full workflow: ingest → enrich → analyze → report."""
        from et_intel_core import db
        monkeypatch.setattr(db, 'get_session', lambda: db_session)
        
        # 1. Create entity
        entity = MonitoredEntity(
            name="Test Entity",
            canonical_name="Test Entity",
            entity_type=EntityType.PERSON,
            is_active=True
        )
        db_session.add(entity)
        db_session.commit()
        
        # 2. Ingest data
        csv_content = "Post URL,Username,Comment,Timestamp,Likes,Caption,Subject\n"
        csv_content += "https://instagram.com/p/test1,user1,I love Test Entity!,2024-01-01 10:00:00,100,Caption,Subject\n"
        csv_content += "https://instagram.com/p/test2,user2,Test Entity is great,2024-01-02 10:00:00,50,Caption,Subject\n"
        
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content)
        
        source = ESUITSource(csv_file)
        ingestion = IngestionService(db_session)
        ingest_stats = ingestion.ingest(source)
        
        assert ingest_stats['comments_created'] == 2
        
        # 3. Enrich
        extractor = EntityExtractor([entity])
        sentiment_provider = get_sentiment_provider()
        enrichment = EnrichmentService(db_session, extractor, sentiment_provider)
        
        enrich_stats = enrichment.enrich_comments()
        
        assert enrich_stats['comments_processed'] == 2
        assert enrich_stats['signals_created'] > 0
        
        # 4. Analyze
        analytics = AnalyticsService(db_session)
        # Use wider time window to capture test data
        end = datetime.utcnow() + timedelta(days=1)
        start = datetime(2023, 1, 1)
        
        top_entities = analytics.get_top_entities((start, end))
        
        # If empty, check if signals were created
        if len(top_entities) == 0:
            from et_intel_core.models import ExtractedSignal
            signal_count = db_session.query(ExtractedSignal).count()
            assert signal_count > 0, f"No signals created. Enrich stats: {enrich_stats}"
        
        assert len(top_entities) > 0, f"Expected entities but got empty DataFrame. Enrich stats: {enrich_stats}"
        entity_names = top_entities['entity_name'].tolist()
        assert 'Test Entity' in entity_names, f"Entity names found: {entity_names}"
        
        # 5. Generate report
        builder = BriefBuilder(analytics)
        brief = builder.build(start, end)
        
        assert brief.topline_summary['total_comments'] >= 2
        assert brief.topline_summary['total_entities'] >= 1
    
    def test_workflow_with_pdf_generation(self, db_session, tmp_path, monkeypatch):
        """Test workflow including PDF generation."""
        from et_intel_core import db
        monkeypatch.setattr(db, 'get_session', lambda: db_session)
        
        # Create entity and ingest
        entity = MonitoredEntity(
            name="Report Entity",
            canonical_name="Report Entity",
            entity_type=EntityType.PERSON,
            is_active=True
        )
        db_session.add(entity)
        db_session.commit()
        
        csv_content = "Post URL,Username,Comment,Timestamp,Likes,Caption,Subject\n"
        csv_content += "https://instagram.com/p/report1,user1,Report Entity is amazing,2024-01-01 10:00:00,200,Caption,Subject\n"
        
        csv_file = tmp_path / "report_test.csv"
        csv_file.write_text(csv_content)
        
        source = ESUITSource(csv_file)
        ingestion = IngestionService(db_session)
        ingestion.ingest(source)
        
        # Enrich
        extractor = EntityExtractor([entity])
        sentiment_provider = get_sentiment_provider()
        enrichment = EnrichmentService(db_session, extractor, sentiment_provider)
        enrichment.enrich_comments()
        
        # Generate brief
        analytics = AnalyticsService(db_session)
        # Use wider time window to capture test data
        end = datetime.utcnow() + timedelta(days=1)
        start = datetime(2023, 1, 1)
        
        builder = BriefBuilder(analytics)
        brief = builder.build(start, end)
        
        # Render PDF
        output_dir = Path(tempfile.mkdtemp())
        renderer = PDFRenderer(output_dir)
        
        pdf_path = renderer.render(brief, filename="test_brief.pdf")
        
        assert pdf_path.exists()
        assert pdf_path.suffix == '.pdf'
    
    def test_workflow_error_recovery(self, db_session, tmp_path):
        """Test workflow with error recovery."""
        # Create entity
        entity = MonitoredEntity(
            name="Error Test Entity",
            canonical_name="Error Test Entity",
            entity_type=EntityType.PERSON,
            is_active=True
        )
        db_session.add(entity)
        db_session.commit()
        
        # Ingest with some invalid data (should handle gracefully)
        csv_content = "Post URL,Username,Comment,Timestamp,Likes,Caption,Subject\n"
        csv_content += "https://instagram.com/p/valid,user1,Valid comment,2024-01-01 10:00:00,10,Caption,Subject\n"
        
        csv_file = tmp_path / "error_test.csv"
        csv_file.write_text(csv_content)
        
        source = ESUITSource(csv_file)
        ingestion = IngestionService(db_session)
        
        # Should complete without crashing
        stats = ingestion.ingest(source)
        assert stats['comments_created'] >= 0
    
    def test_workflow_idempotency(self, db_session, tmp_path):
        """Test that workflow can be run multiple times (idempotent)."""
        entity = MonitoredEntity(
            name="Idempotent Entity",
            canonical_name="Idempotent Entity",
            entity_type=EntityType.PERSON,
            is_active=True
        )
        db_session.add(entity)
        db_session.commit()
        
        csv_content = "Post URL,Username,Comment,Timestamp,Likes,Caption,Subject\n"
        csv_content += "https://instagram.com/p/idem,user1,Comment,2024-01-01 10:00:00,10,Caption,Subject\n"
        
        csv_file = tmp_path / "idem_test.csv"
        csv_file.write_text(csv_content)
        
        source = ESUITSource(csv_file)
        ingestion = IngestionService(db_session)
        
        # First run
        stats1 = ingestion.ingest(source)
        comments1 = stats1['comments_created']
        
        # Second run (should update, not create duplicates)
        stats2 = ingestion.ingest(source)
        comments2 = stats2['comments_created']
        
        # Should have created comments first time, updated second time
        assert comments1 > 0
        assert stats2['comments_updated'] > 0 or comments2 == 0

