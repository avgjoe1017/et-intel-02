"""
NLP components for entity extraction and sentiment analysis.
"""

from et_intel_core.nlp.entity_extractor import EntityExtractor, EntityMention
from et_intel_core.nlp.sentiment import (
    SentimentProvider,
    SentimentResult,
    RuleBasedSentimentProvider,
    OpenAISentimentProvider,
    HybridSentimentProvider,
    get_sentiment_provider
)

__all__ = [
    "EntityExtractor",
    "EntityMention",
    "SentimentProvider",
    "SentimentResult",
    "RuleBasedSentimentProvider",
    "OpenAISentimentProvider",
    "HybridSentimentProvider",
    "get_sentiment_provider",
]

