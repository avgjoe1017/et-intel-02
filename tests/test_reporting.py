"""
Tests for reporting module (BriefBuilder and PDFRenderer).
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import shutil

from et_intel_core.reporting import BriefBuilder, BriefSection, IntelligenceBriefData, PDFRenderer
from et_intel_core.analytics import AnalyticsService
from et_intel_core.models import MonitoredEntity, Post, Comment, ExtractedSignal
from et_intel_core.models.enums import PlatformType, EntityType, SignalType, ContextType


@pytest.fixture(autouse=True)
def mock_get_session(db_session, monkeypatch):
    """Automatically mock get_session for all reporting tests."""
    from et_intel_core import db
    monkeypatch.setattr(db, 'get_session', lambda: db_session)


@pytest.fixture
def sample_brief_data():
    """Create sample brief data for testing."""
    return IntelligenceBriefData(
        timeframe={
            'start': datetime(2024, 1, 1),
            'end': datetime(2024, 1, 7)
        },
        topline_summary={
            'total_comments': 1000,
            'total_entities': 5,
            'critical_alerts': 1,
            'velocity_alerts_count': 2
        },
        top_entities=BriefSection(
            title="Top Entities",
            items=[
                {'entity_name': 'Test Entity 1', 'mention_count': 100, 'avg_sentiment': 0.5},
                {'entity_name': 'Test Entity 2', 'mention_count': 50, 'avg_sentiment': -0.3}
            ],
            summary="Test Entity 1 dominated with 100 mentions"
        ),
        velocity_alerts=BriefSection(
            title="Velocity Alerts",
            items=[
                {
                    'entity_name': 'Test Entity 1',
                    'percent_change': -45.0,
                    'recent_sentiment': -0.5,
                    'previous_sentiment': -0.2,
                    'direction': 'down'
                }
            ],
            summary="1 entity with significant sentiment shift"
        ),
        discovered_entities=BriefSection(
            title="Discovered Entities",
            items=[],
            summary="No new entities"
        ),
        platform_breakdown=BriefSection(
            title="Platform Breakdown",
            items=[],
            summary="Platform data"
        ),
        sentiment_distribution={},
        contextual_narrative="Test narrative",
        entity_comparison=BriefSection(
            title="Entity Comparison",
            items=[],
            summary=""
        ),
        what_changed=BriefSection(
            title="What Changed",
            items=[],
            summary=""
        ),
        key_risks=BriefSection(
            title="Key Risks",
            items=[],
            summary=""
        ),
        entity_micro_insights={},
        cross_platform_deltas=BriefSection(
            title="Cross Platform Deltas",
            items=[],
            summary=""
        ),
        storylines=BriefSection(
            title="Storylines",
            items=[],
            summary="No storylines"
        ),
        risk_signals=BriefSection(
            title="Risk Signals",
            items=[],
            summary="No risk signals"
        ),
        metadata={
            'generated_at': datetime.utcnow(),
            'platforms': ['instagram']
        }
    )


class TestBriefSection:
    """Tests for BriefSection dataclass."""
    
    def test_brief_section_creation(self):
        """Test creating a BriefSection."""
        section = BriefSection(
            title="Test Section",
            items=[{'key': 'value'}],
            summary="Test summary"
        )
        
        assert section.title == "Test Section"
        assert len(section.items) == 1
        assert section.summary == "Test summary"
    
    def test_brief_section_defaults(self):
        """Test BriefSection with defaults."""
        section = BriefSection(title="Test")
        
        assert section.title == "Test"
        assert section.items == []
        assert section.summary is None


class TestIntelligenceBriefData:
    """Tests for IntelligenceBriefData."""
    
    def test_brief_data_creation(self, sample_brief_data):
        """Test creating IntelligenceBriefData."""
        assert sample_brief_data.topline_summary['total_comments'] == 1000
        assert len(sample_brief_data.top_entities.items) == 2
        assert len(sample_brief_data.velocity_alerts.items) == 1
    
    def test_brief_data_to_dict(self, sample_brief_data):
        """Test converting brief data to dictionary."""
        data_dict = sample_brief_data.to_dict()
        
        assert 'timeframe' in data_dict
        assert 'topline_summary' in data_dict
        assert 'top_entities' in data_dict
        assert 'velocity_alerts' in data_dict
        assert data_dict['topline_summary']['total_comments'] == 1000


class TestBriefBuilder:
    """Tests for BriefBuilder."""
    
    def test_brief_builder_creation(self, db_session):
        """Test creating a BriefBuilder."""
        analytics = AnalyticsService(db_session)
        builder = BriefBuilder(analytics)
        
        assert builder.analytics == analytics
    
    def test_build_brief_empty_database(self, db_session):
        """Test building brief with empty database."""
        analytics = AnalyticsService(db_session)
        builder = BriefBuilder(analytics)
        
        start = datetime.utcnow() - timedelta(days=7)
        end = datetime.utcnow()
        
        brief = builder.build(start, end)
        
        assert brief.topline_summary['total_comments'] == 0
        assert brief.topline_summary['total_entities'] == 0
        assert len(brief.top_entities.items) == 0
    
    def test_build_brief_with_data(self, db_session, sample_entity, enriched_comment):
        """Test building brief with actual data."""
        analytics = AnalyticsService(db_session)
        builder = BriefBuilder(analytics)
        
        # Set comment date to recent
        enriched_comment.comment.created_at = datetime.utcnow() - timedelta(days=1)
        db_session.commit()
        
        start = datetime.utcnow() - timedelta(days=7)
        end = datetime.utcnow()
        
        brief = builder.build(start, end)
        
        assert brief.topline_summary['total_comments'] >= 1
        assert 'start' in brief.timeframe and 'end' in brief.timeframe
        assert brief.metadata['generated_at'] is not None
    
    def test_summarize_top_entities_empty(self, db_session, monkeypatch):
        """Test summarizing empty entity list."""
        from et_intel_core import db
        monkeypatch.setattr(db, 'get_session', lambda: db_session)
        analytics = AnalyticsService(db_session)
        builder = BriefBuilder(analytics)
        
        import pandas as pd
        empty_df = pd.DataFrame()
        
        summary = builder._summarize_top_entities(empty_df)
        assert "No significant entity activity" in summary
    
    def test_summarize_top_entities_with_data(self, db_session):
        """Test summarizing entities with data."""
        analytics = AnalyticsService(db_session)
        builder = BriefBuilder(analytics)
        
        import pandas as pd
        df = pd.DataFrame([
            {'entity_name': 'Test Entity', 'mention_count': 100, 'avg_sentiment': 0.5}
        ])
        
        summary = builder._summarize_top_entities(df)
        assert 'Test Entity' in summary
        assert '100' in summary or 'positive' in summary


class TestPDFRenderer:
    """Tests for PDFRenderer."""
    
    @pytest.fixture
    def temp_output_dir(self):
        """Create temporary directory for PDF output."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    def test_pdf_renderer_creation(self, temp_output_dir):
        """Test creating a PDFRenderer."""
        renderer = PDFRenderer(temp_output_dir)
        
        assert renderer.output_dir == temp_output_dir
        assert temp_output_dir.exists()
    
    def test_render_pdf(self, temp_output_dir, sample_brief_data):
        """Test rendering a PDF from brief data."""
        renderer = PDFRenderer(temp_output_dir)
        
        pdf_path = renderer.render(sample_brief_data, filename="test_brief.pdf")
        
        assert pdf_path.exists()
        assert pdf_path.suffix == '.pdf'
        assert pdf_path.name == "test_brief.pdf"
    
    def test_render_pdf_auto_filename(self, temp_output_dir, sample_brief_data):
        """Test rendering PDF with auto-generated filename."""
        renderer = PDFRenderer(temp_output_dir)
        
        pdf_path = renderer.render(sample_brief_data)
        
        assert pdf_path.exists()
        assert pdf_path.suffix == '.pdf'
        assert 'ET_Intelligence_Brief_' in pdf_path.name
    
    def test_render_pdf_adds_extension(self, temp_output_dir, sample_brief_data):
        """Test that PDF extension is added if missing."""
        renderer = PDFRenderer(temp_output_dir)
        
        pdf_path = renderer.render(sample_brief_data, filename="test_brief")
        
        assert pdf_path.suffix == '.pdf'
        assert pdf_path.name == "test_brief.pdf"
    
    def test_create_title_page(self, temp_output_dir, sample_brief_data):
        """Test title page creation."""
        renderer = PDFRenderer(temp_output_dir)
        
        elements = renderer._create_title_page(sample_brief_data)
        
        assert len(elements) > 0
        # Should have title, timeframe, etc.
    
    def test_create_executive_summary(self, temp_output_dir, sample_brief_data):
        """Test executive summary creation."""
        renderer = PDFRenderer(temp_output_dir)
        
        elements = renderer._create_executive_summary(sample_brief_data)
        
        assert len(elements) > 0
    
    def test_create_top_entities_section(self, temp_output_dir, sample_brief_data):
        """Test top entities section creation."""
        renderer = PDFRenderer(temp_output_dir)
        
        elements = renderer._create_top_entities_section(sample_brief_data.top_entities)
        
        assert len(elements) > 0
    
    def test_create_velocity_alerts_section(self, temp_output_dir, sample_brief_data):
        """Test velocity alerts section creation."""
        renderer = PDFRenderer(temp_output_dir)
        
        elements = renderer._create_velocity_alerts_section(sample_brief_data.velocity_alerts)
        
        assert len(elements) > 0
    
    def test_create_top_entities_empty(self, temp_output_dir):
        """Test top entities section with no data."""
        renderer = PDFRenderer(temp_output_dir)
        
        empty_section = BriefSection(
            title="Top Entities",
            items=[],
            summary="No data"
        )
        
        elements = renderer._create_top_entities_section(empty_section)
        
        assert len(elements) > 0
        # Should have message about no data
    
    def test_create_velocity_alerts_empty(self, temp_output_dir):
        """Test velocity alerts section with no data."""
        renderer = PDFRenderer(temp_output_dir)
        
        empty_section = BriefSection(
            title="Velocity Alerts",
            items=[],
            summary="No alerts"
        )
        
        elements = renderer._create_velocity_alerts_section(empty_section)
        
        assert len(elements) > 0

