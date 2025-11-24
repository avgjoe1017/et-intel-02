"""
Tests for NLP components (entity extraction and sentiment analysis).
"""

import pytest
from et_intel_core.models import MonitoredEntity, EntityType
from et_intel_core.nlp import (
    EntityExtractor,
    RuleBasedSentimentProvider,
    OpenAISentimentProvider,
    HybridSentimentProvider,
    get_sentiment_provider
)


def test_entity_extractor_catalog_matching(db_session):
    """Test entity extraction from catalog."""
    # Create test entities
    taylor = MonitoredEntity(
        name="Taylor Swift",
        canonical_name="Taylor Swift",
        entity_type=EntityType.PERSON,
        aliases=["Taylor", "T-Swift"]
    )
    ryan = MonitoredEntity(
        name="Ryan Reynolds",
        canonical_name="Ryan Reynolds",
        entity_type=EntityType.PERSON,
        aliases=["Ryan"]
    )
    
    db_session.add_all([taylor, ryan])
    db_session.commit()
    
    # Create extractor
    catalog = [taylor, ryan]
    extractor = EntityExtractor(catalog)
    
    # Test exact match
    catalog_mentions, discovered = extractor.extract("I love Taylor Swift!")
    assert len(catalog_mentions) == 1
    assert catalog_mentions[0].mention_text == "taylor swift"
    assert catalog_mentions[0].confidence == 1.0
    
    # Test alias match
    catalog_mentions, discovered = extractor.extract("T-Swift is amazing")
    assert len(catalog_mentions) == 1
    assert catalog_mentions[0].confidence == 0.9  # Alias has lower confidence
    
    # Test multiple entities
    catalog_mentions, discovered = extractor.extract("Taylor and Ryan are great")
    assert len(catalog_mentions) == 2


def test_entity_extractor_discovery(db_session):
    """Test entity discovery with spaCy."""
    # Empty catalog
    extractor = EntityExtractor([])
    
    # Should discover entities via spaCy
    catalog_mentions, discovered = extractor.extract("Blake Lively is talented")
    
    assert len(catalog_mentions) == 0  # Not in catalog
    assert len(discovered) >= 1  # spaCy should find "Blake Lively"
    
    # Check discovered entity
    blake = next((d for d in discovered if "Blake" in d.name or "Lively" in d.name), None)
    assert blake is not None
    assert blake.entity_type in ["PERSON", "ORG"]


def test_rule_based_sentiment_positive():
    """Test rule-based sentiment on positive text."""
    provider = RuleBasedSentimentProvider()
    
    # Strong positive
    result = provider.score("I love this! Amazing! 😍")
    assert result.score > 0.5
    assert result.source_model == "rule_based"
    
    # Entertainment slang
    result = provider.score("She ate! Queen behavior 👑")
    assert result.score > 0.5


def test_rule_based_sentiment_negative():
    """Test rule-based sentiment on negative text."""
    provider = RuleBasedSentimentProvider()
    
    # Strong negative
    result = provider.score("I hate this. Terrible and awful 😡")
    assert result.score < -0.5
    
    # Entertainment slang
    result = provider.score("This is cringe. Total flop 👎")
    assert result.score < -0.5


def test_rule_based_sentiment_neutral():
    """Test rule-based sentiment on neutral text."""
    provider = RuleBasedSentimentProvider()
    
    result = provider.score("The movie comes out next week.")
    assert -0.3 <= result.score <= 0.3


def test_openai_sentiment_provider():
    """Test OpenAI sentiment provider (if API key available)."""
    try:
        provider = OpenAISentimentProvider()
        
        # Test positive
        result = provider.score("This is absolutely wonderful!")
        assert result.score > 0
        assert result.source_model == "gpt-4o-mini"
        assert result.confidence == 0.9
        
        # Test negative
        result = provider.score("This is terrible and disappointing.")
        assert result.score < 0
        
    except ValueError as e:
        # Skip if no API key
        pytest.skip(f"OpenAI API key not available: {e}")


def test_hybrid_sentiment_escalation():
    """Test hybrid provider escalation logic."""
    # Mock providers for testing
    class MockCheap:
        def score(self, text):
            from et_intel_core.nlp.sentiment import SentimentResult
            # Return low confidence to trigger escalation
            return SentimentResult(score=0.1, confidence=0.5, source_model="mock_cheap")
    
    class MockExpensive:
        def score(self, text):
            from et_intel_core.nlp.sentiment import SentimentResult
            return SentimentResult(score=0.8, confidence=0.9, source_model="mock_expensive")
    
    provider = HybridSentimentProvider(cheap=MockCheap(), expensive=MockExpensive())
    
    # Should escalate due to low confidence
    result = provider.score("Some text")
    assert result.source_model == "mock_expensive"
    assert result.score == 0.8


def test_get_sentiment_provider():
    """Test sentiment provider factory."""
    # Rule-based
    provider = get_sentiment_provider("rule_based")
    assert isinstance(provider, RuleBasedSentimentProvider)
    
    # Hybrid
    provider = get_sentiment_provider("hybrid")
    assert isinstance(provider, HybridSentimentProvider)
    
    # OpenAI (if available)
    try:
        provider = get_sentiment_provider("openai")
        assert isinstance(provider, OpenAISentimentProvider)
    except ValueError:
        # Skip if no API key
        pass


def test_sentiment_score_range():
    """Test that sentiment scores are in valid range."""
    provider = RuleBasedSentimentProvider()
    
    texts = [
        "I love this so much!",
        "This is okay I guess",
        "I hate everything about this"
    ]
    
    for text in texts:
        result = provider.score(text)
        assert -1.0 <= result.score <= 1.0
        assert 0.0 <= result.confidence <= 1.0

