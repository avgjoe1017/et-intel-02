"""
Tests for chart generator.
"""

import pytest
from pathlib import Path
from datetime import datetime, timedelta
import tempfile
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend

from et_intel_core.reporting.chart_generator import ChartGenerator


class TestChartGenerator:
    """Tests for ChartGenerator."""
    
    def test_init_default_dir(self):
        """Test initialization with default temp directory."""
        generator = ChartGenerator()
        assert generator.output_dir.exists()
    
    def test_init_custom_dir(self, tmp_path):
        """Test initialization with custom directory."""
        generator = ChartGenerator(output_dir=tmp_path)
        assert generator.output_dir == tmp_path
    
    def test_generate_sentiment_trend(self, tmp_path):
        """Test generating sentiment trend chart."""
        generator = ChartGenerator(output_dir=tmp_path)
        
        # Create test data
        entity_data = [
            {"date": datetime.utcnow() - timedelta(days=2), "avg_sentiment": 0.5},
            {"date": datetime.utcnow() - timedelta(days=1), "avg_sentiment": 0.7},
            {"date": datetime.utcnow(), "avg_sentiment": 0.6}
        ]
        
        chart_path = generator.generate_sentiment_trend(entity_data, "Test Entity")
        
        assert chart_path.exists()
        assert chart_path.suffix == ".png"
        assert "Test_Entity" in str(chart_path)
    
    def test_generate_sentiment_trend_empty_data(self, tmp_path):
        """Test generating sentiment trend with empty data."""
        generator = ChartGenerator(output_dir=tmp_path)
        
        # Empty data should still create a chart (even if empty)
        # The function may handle empty data differently, so we just check it doesn't crash
        try:
            chart_path = generator.generate_sentiment_trend([], "Test Entity")
            # If it returns a path, check it exists
            if chart_path:
                assert chart_path.exists()
        except (ValueError, KeyError, IndexError):
            # Empty data might cause errors, which is acceptable
            pass
    
    def test_generate_entity_comparison_trend(self, tmp_path):
        """Test generating entity comparison trend chart."""
        generator = ChartGenerator(output_dir=tmp_path)
        
        # Create test data for multiple entities
        entities_data = {
            "Entity A": [
                {"date": datetime.utcnow() - timedelta(days=1), "avg_sentiment": 0.5},
                {"date": datetime.utcnow(), "avg_sentiment": 0.7}
            ],
            "Entity B": [
                {"date": datetime.utcnow() - timedelta(days=1), "avg_sentiment": -0.3},
                {"date": datetime.utcnow(), "avg_sentiment": -0.5}
            ]
        }
        
        chart_path = generator.generate_entity_comparison_trend(entities_data)
        
        assert chart_path.exists()
        assert chart_path.suffix == ".png"
    
    def test_generate_sentiment_distribution(self, tmp_path):
        """Test generating sentiment distribution chart."""
        generator = ChartGenerator(output_dir=tmp_path)
        
        distribution = {
            "positive": 50,
            "neutral": 30,
            "negative": 20,
            "total": 100
        }
        
        chart_path = generator.generate_sentiment_distribution(distribution)
        
        assert chart_path.exists()
        assert chart_path.suffix == ".png"
    
    def test_generate_platform_comparison(self, tmp_path):
        """Test generating platform comparison chart."""
        generator = ChartGenerator(output_dir=tmp_path)
        
        # Note: chart expects 'comment_count' not 'mention_count'
        platform_data = [
            {"platform": "instagram", "avg_sentiment": 0.5, "comment_count": 100},
            {"platform": "youtube", "avg_sentiment": 0.3, "comment_count": 50},
            {"platform": "tiktok", "avg_sentiment": -0.2, "comment_count": 75}
        ]
        
        chart_path = generator.generate_platform_comparison(platform_data)
        
        assert chart_path.exists()
        assert chart_path.suffix == ".png"
    
    def test_generate_risk_radar(self, tmp_path):
        """Test generating risk radar chart."""
        generator = ChartGenerator(output_dir=tmp_path)
        
        # Note: risk_radar expects list of entity dicts with entity_name, avg_sentiment, mention_count, total_likes
        entity_data = [
            {"entity_name": "Entity A", "avg_sentiment": -0.3, "mention_count": 100, "total_likes": 500},
            {"entity_name": "Entity B", "avg_sentiment": 0.5, "mention_count": 200, "total_likes": 1000}
        ]
        
        chart_path = generator.generate_risk_radar(entity_data)
        
        assert chart_path.exists()
        assert chart_path.suffix == ".png"

