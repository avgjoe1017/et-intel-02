"""
Tests for narrative generator.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from et_intel_core.reporting.narrative_generator import NarrativeGenerator


class TestNarrativeGenerator:
    """Tests for NarrativeGenerator."""
    
    @patch('et_intel_core.reporting.narrative_generator.settings')
    def test_init_without_api_key(self, mock_settings):
        """Test initialization without API key."""
        mock_settings.openai_api_key = None
        generator = NarrativeGenerator(api_key=None)
        assert generator.enabled is False
        assert generator.client is None
    
    def test_init_with_invalid_api_key(self):
        """Test initialization with invalid API key."""
        generator = NarrativeGenerator(api_key="your-openai-api-key-here")
        assert generator.enabled is False
        assert generator.client is None
    
    def test_init_with_valid_api_key(self):
        """Test initialization with valid API key."""
        generator = NarrativeGenerator(api_key="sk-test-key")
        assert generator.enabled is True
        assert generator.client is not None
    
    @patch('et_intel_core.reporting.narrative_generator.settings')
    def test_generate_velocity_narrative_disabled(self, mock_settings):
        """Test velocity narrative generation when disabled."""
        mock_settings.openai_api_key = None
        generator = NarrativeGenerator(api_key=None)
        
        velocity_data = {
            "percent_change": 25.5,
            "previous_sentiment": 0.3,
            "recent_sentiment": 0.5
        }
        
        narrative = generator.generate_velocity_narrative(velocity_data, "Test Entity")
        
        assert "Test Entity" in narrative
        assert "25.5" in narrative or "25" in narrative
        assert "0.3" in narrative or "0.30" in narrative
    
    @patch('et_intel_core.reporting.narrative_generator.OpenAI')
    def test_generate_velocity_narrative_enabled(self, mock_openai):
        """Test velocity narrative generation when enabled."""
        # Mock OpenAI client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "This change likely occurred due to recent news events."
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        generator = NarrativeGenerator(api_key="sk-test-key")
        generator.client = mock_client
        
        velocity_data = {
            "percent_change": 25.5,
            "previous_sentiment": 0.3,
            "recent_sentiment": 0.5,
            "recent_sample_size": 100
        }
        
        narrative = generator.generate_velocity_narrative(velocity_data, "Test Entity")
        
        assert "This change likely occurred" in narrative
        mock_client.chat.completions.create.assert_called_once()
    
    @patch('et_intel_core.reporting.narrative_generator.OpenAI')
    def test_generate_velocity_narrative_api_error(self, mock_openai):
        """Test velocity narrative generation with API error."""
        # Mock OpenAI client that raises exception
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        mock_openai.return_value = mock_client
        
        generator = NarrativeGenerator(api_key="sk-test-key")
        generator.client = mock_client
        
        velocity_data = {
            "percent_change": 25.5,
            "previous_sentiment": 0.3,
            "recent_sentiment": 0.5
        }
        
        narrative = generator.generate_velocity_narrative(velocity_data, "Test Entity")
        
        # Should fall back to simple narrative
        assert "Test Entity" in narrative
        assert "25.5" in narrative or "25" in narrative
    
    def test_generate_brief_summary_disabled(self):
        """Test brief summary generation when disabled."""
        generator = NarrativeGenerator(api_key=None)
        
        top_entities = [
            {"entity_name": "Entity A", "mention_count": 100, "avg_sentiment": 0.5}
        ]
        velocity_alerts = [
            {"entity_name": "Entity B", "percent_change": 30.0}
        ]
        platform_breakdown = []
        timeframe = {
            "start": datetime(2024, 1, 1),
            "end": datetime(2024, 1, 7)
        }
        
        summary = generator.generate_brief_summary(
            top_entities, velocity_alerts, platform_breakdown, timeframe
        )
        
        assert "Entity A" in summary
        assert "100" in summary
    
    @patch('et_intel_core.reporting.narrative_generator.settings')
    def test_generate_brief_summary_no_entities(self, mock_settings):
        """Test brief summary with no entities."""
        mock_settings.openai_api_key = None
        generator = NarrativeGenerator(api_key=None)
        
        summary = generator.generate_brief_summary(
            [], [], [], {"start": datetime(2024, 1, 1), "end": datetime(2024, 1, 7)}
        )
        
        assert "No significant entity activity" in summary
    
    @patch('et_intel_core.reporting.narrative_generator.OpenAI')
    def test_generate_brief_summary_enabled(self, mock_openai):
        """Test brief summary generation when enabled."""
        # Mock OpenAI client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Executive summary text here."
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        generator = NarrativeGenerator(api_key="sk-test-key")
        generator.client = mock_client
        
        top_entities = [
            {"entity_name": "Entity A", "mention_count": 100, "avg_sentiment": 0.5}
        ]
        velocity_alerts = []
        platform_breakdown = [
            {"platform": "instagram", "avg_sentiment": 0.4}
        ]
        timeframe = {
            "start": datetime(2024, 1, 1),
            "end": datetime(2024, 1, 7)
        }
        
        summary = generator.generate_brief_summary(
            top_entities, velocity_alerts, platform_breakdown, timeframe
        )
        
        assert "Executive summary text here" in summary
        mock_client.chat.completions.create.assert_called_once()
    
    @patch('et_intel_core.reporting.narrative_generator.OpenAI')
    def test_generate_brief_summary_api_error(self, mock_openai):
        """Test brief summary generation with API error."""
        # Mock OpenAI client that raises exception
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        mock_openai.return_value = mock_client
        
        generator = NarrativeGenerator(api_key="sk-test-key")
        generator.client = mock_client
        
        top_entities = [
            {"entity_name": "Entity A", "mention_count": 100, "avg_sentiment": 0.5}
        ]
        velocity_alerts = []
        platform_breakdown = []
        timeframe = {
            "start": datetime(2024, 1, 1),
            "end": datetime(2024, 1, 7)
        }
        
        summary = generator.generate_brief_summary(
            top_entities, velocity_alerts, platform_breakdown, timeframe
        )
        
        # Should fall back to simple summary
        assert "Entity A" in summary

