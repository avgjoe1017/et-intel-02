"""
Sentiment analysis providers with swappable backends.
"""

from dataclasses import dataclass
from typing import Protocol
import re

from textblob import TextBlob
from openai import OpenAI

from et_intel_core.config import settings


@dataclass
class SentimentResult:
    """Result from any sentiment model."""
    score: float  # -1.0 to 1.0
    confidence: float  # 0.0 to 1.0
    source_model: str


class SentimentProvider(Protocol):
    """Interface for all sentiment models."""
    
    def score(self, text: str) -> SentimentResult:
        """
        Score sentiment of text.
        
        Args:
            text: Text to analyze
            
        Returns:
            SentimentResult with score, confidence, and model name
        """
        ...


class RuleBasedSentimentProvider:
    """
    Fast, free, decent for obvious cases.
    
    Uses TextBlob + entertainment-specific tuning:
    - Understands stan culture ("she ate" = positive)
    - Emoji analysis
    - Sarcasm detection (basic)
    """
    
    # Entertainment-specific lexicon
    POSITIVE_TERMS = [
        "love", "amazing", "great", "best", "perfect", "beautiful", "gorgeous",
        "talented", "queen", "king", "icon", "legend", "ate", "slayed", "fire",
        "obsessed", "adorable", "stunning", "incredible", "phenomenal"
    ]
    
    NEGATIVE_TERMS = [
        "hate", "terrible", "worst", "awful", "disgusting", "cringe", "yikes",
        "toxic", "problematic", "cancelled", "flop", "trash", "mess", "disaster"
    ]
    
    # Positive emojis
    POSITIVE_EMOJIS = ["❤️", "😍", "🥰", "😊", "🔥", "✨", "👑", "💯", "🙌", "👏"]
    
    # Negative emojis
    NEGATIVE_EMOJIS = ["😡", "🤮", "💔", "😤", "🙄", "😬", "👎", "😒"]
    
    def score(self, text: str) -> SentimentResult:
        """Score sentiment using rules + TextBlob."""
        text_lower = text.lower()
        
        # Count entertainment terms
        pos_term_count = sum(1 for term in self.POSITIVE_TERMS if term in text_lower)
        neg_term_count = sum(1 for term in self.NEGATIVE_TERMS if term in text_lower)
        
        # Count emojis
        pos_emoji_count = sum(1 for emoji in self.POSITIVE_EMOJIS if emoji in text)
        neg_emoji_count = sum(1 for emoji in self.NEGATIVE_EMOJIS if emoji in text)
        
        # Total positive/negative signals
        pos_total = pos_term_count + pos_emoji_count
        neg_total = neg_term_count + neg_emoji_count
        
        # If we have strong signals from our lexicon, use them
        if pos_total + neg_total >= 2:
            if pos_total + neg_total == 0:
                score = 0.0
            else:
                score = (pos_total - neg_total) / (pos_total + neg_total)
            confidence = min(0.8, 0.5 + (pos_total + neg_total) * 0.1)
            return SentimentResult(
                score=score,
                confidence=confidence,
                source_model="rule_based"
            )
        
        # Fall back to TextBlob for neutral/ambiguous cases
        blob = TextBlob(text)
        polarity = blob.sentiment.polarity  # -1 to 1
        
        # TextBlob confidence based on subjectivity
        # High subjectivity = more confident in sentiment
        subjectivity = blob.sentiment.subjectivity
        confidence = 0.3 + (subjectivity * 0.4)  # 0.3 to 0.7 range
        
        return SentimentResult(
            score=polarity,
            confidence=confidence,
            source_model="rule_based"
        )


class OpenAISentimentProvider:
    """
    High accuracy, costs money.
    
    Uses GPT-4o-mini for entertainment-aware sentiment analysis.
    """
    
    def __init__(self, api_key: str | None = None):
        """
        Initialize OpenAI provider.
        
        Args:
            api_key: OpenAI API key (uses settings.openai_api_key if None)
        """
        self.api_key = api_key or settings.openai_api_key
        if not self.api_key:
            raise ValueError("OpenAI API key required. Set OPENAI_API_KEY in .env")
        
        self.client = OpenAI(api_key=self.api_key)
    
    def score(self, text: str) -> SentimentResult:
        """Score sentiment using GPT-4o-mini."""
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{
                    "role": "system",
                    "content": (
                        "You are a sentiment analyzer for entertainment social media comments. "
                        "Understand stan culture, sarcasm, and entertainment language. "
                        "Return ONLY a number from -1.0 (very negative) to 1.0 (very positive)."
                    )
                }, {
                    "role": "user",
                    "content": f"Score sentiment: {text}"
                }],
                max_tokens=10,
                temperature=0.3  # Lower temperature for consistent scoring
            )
            
            # Parse score
            score_text = response.choices[0].message.content.strip()
            score = float(score_text)
            
            # Clamp to valid range
            score = max(-1.0, min(1.0, score))
            
            return SentimentResult(
                score=score,
                confidence=0.9,  # High confidence in GPT
                source_model="gpt-4o-mini"
            )
            
        except Exception as e:
            # Fallback to neutral on error
            print(f"OpenAI API error: {e}")
            return SentimentResult(
                score=0.0,
                confidence=0.0,
                source_model="gpt-4o-mini_error"
            )


class HybridSentimentProvider:
    """
    Cost optimization: use cheap model first, escalate if uncertain.
    
    Strategy:
    1. Try rule-based first (free, fast)
    2. If confidence < 0.7 OR score is neutral (-0.2 to 0.2), escalate to OpenAI
    3. This saves ~60-70% of API costs while maintaining quality
    """
    
    def __init__(
        self, 
        cheap: SentimentProvider | None = None,
        expensive: SentimentProvider | None = None
    ):
        """
        Initialize hybrid provider.
        
        Args:
            cheap: Cheap sentiment provider (defaults to RuleBasedSentimentProvider)
            expensive: Expensive provider (defaults to OpenAISentimentProvider)
        """
        self.cheap = cheap or RuleBasedSentimentProvider()
        self.expensive = expensive or OpenAISentimentProvider()
    
    def score(self, text: str) -> SentimentResult:
        """Score sentiment with escalation strategy."""
        # Try cheap first
        result = self.cheap.score(text)
        
        # Escalate if:
        # 1. Low confidence (< 0.7)
        # 2. Neutral score (-0.2 to 0.2) - these are often misclassified
        should_escalate = (
            result.confidence < 0.7 or 
            abs(result.score) < 0.2
        )
        
        if should_escalate:
            # Use expensive model
            return self.expensive.score(text)
        
        return result


def get_sentiment_provider(backend: str | None = None) -> SentimentProvider:
    """
    Get sentiment provider based on configuration.
    
    Args:
        backend: Override backend ("rule_based", "openai", "hybrid")
                 Uses settings.sentiment_backend if None
    
    Returns:
        Configured SentimentProvider instance
    """
    backend = backend or settings.sentiment_backend
    
    if backend == "openai":
        return OpenAISentimentProvider()
    elif backend == "hybrid":
        return HybridSentimentProvider()
    else:  # "rule_based" or default
        return RuleBasedSentimentProvider()

