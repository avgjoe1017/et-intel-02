"""
Sentiment analysis providers with swappable backends.
"""

from dataclasses import dataclass
from typing import Protocol, Optional, List, Dict, Any
import re
import json

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
    Enhanced sentiment provider with multi-signal extraction.
    
    Uses GPT-4o-mini to extract:
    - Entity-targeted sentiment scores
    - Emotion classification
    - Stance (support/oppose/neutral)
    - Topics/storylines
    - Toxicity score
    - Sarcasm detection
    - Discovered entities
    
    All in one API call for maximum ROI.
    """
    
    SYSTEM_PROMPT = """You are an entertainment social media analyst. Extract structured signals from comments.

Understand:
- Stan culture and fandom language
- Sarcasm and irony - CRITICAL patterns:
  * 💐 (flowers) + "you earned it" = sarcasm (funeral flowers, mocking)
  * 🐍🤮💀🙄 combined with seemingly positive words = sarcasm
  * "You chose X" after controversy = sarcastic blame
  * High likes + negative emojis = community agrees it's sarcastic
- Pronoun resolution using post context
- That high like counts mean community agreement
- Questions like "Is X true?" are neutral (0.0) unless clearly rhetorical
- Context matters: "I feel bad for X" = positive sentiment toward X, negative toward situation

Sarcasm Examples:
- "💐 You earned it. You chose Blake" = sarcasm=true, Blake=-0.7 (not +0.5)
- "Great job ruining it 🐍" = sarcasm=true, negative sentiment
- "You did so well 🤮" = sarcasm=true

Question Handling:
- "Is it possible Blake is telling the truth?" = neutral (0.0), not positive
- "Could X be right?" = neutral unless clearly rhetorical

Return ONLY valid JSON with this exact structure:
{
  "entity_scores": {"EntityName": -1.0 to 1.0, ...},
  "entity_confidence": {"EntityName": 0.0 to 1.0, ...},
  "emotion": "anger|disgust|joy|disappointment|sarcasm|neutral",
  "stance": "support|oppose|neutral",
  "topics": ["topic1", "topic2"],
  "other_entities": ["discovered entity names"],
  "sarcasm": true|false,
  "toxicity": 0.0-1.0,
  "ambiguous_mentions": [{"name": "Justin", "possible_entities": ["Justin Bieber", "Justin Baldoni"], "confidence": 0.4, "reason": "First name only, multiple Justins in monitored list"}]
}

CRITICAL RULES:
- Only include entities in entity_scores if you are CONFIDENT (confidence >= 0.7)
- If confidence < 0.7, include in ambiguous_mentions instead
- Use post caption context to disambiguate (e.g., Hailey Bieber post → "Justin" = Justin Bieber)
- If you cannot confidently determine which entity, put in ambiguous_mentions for human review"""
    
    def __init__(self, api_key: str | None = None, model: str = "gpt-4o-mini"):
        """
        Initialize OpenAI provider.
        
        Args:
            api_key: OpenAI API key (uses settings.openai_api_key if None)
            model: Model to use (default: gpt-4o-mini)
        """
        self.api_key = api_key or settings.openai_api_key
        if not self.api_key:
            raise ValueError("OpenAI API key required. Set OPENAI_API_KEY in .env")
        
        self.client = OpenAI(api_key=self.api_key)
        self.model = model
    
    def score(self, text: str) -> SentimentResult:
        """
        Legacy method: score sentiment only (for backward compatibility).
        
        Use analyze_comment() for enhanced multi-signal extraction.
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
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
                temperature=0.3
            )
            
            score_text = response.choices[0].message.content.strip()
            score = float(score_text)
            score = max(-1.0, min(1.0, score))
            
            return SentimentResult(
                score=score,
                confidence=0.9,
                source_model=self.model
            )
        except Exception as e:
            print(f"OpenAI API error: {e}")
            return SentimentResult(
                score=0.0,
                confidence=0.0,
                source_model=f"{self.model}_error"
            )
    
    def analyze_comment(
        self,
        comment_text: str,
        post_caption: str = "",
        comment_likes: int = 0,
        monitored_entities: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Extract all signals from a comment in one API call.
        
        Args:
            comment_text: The comment text to analyze
            post_caption: Post caption for pronoun/context resolution
            comment_likes: Number of likes (indicates community agreement)
            monitored_entities: List of all monitored entities (for context, not forced scoring)
            
        Returns:
            Dictionary with extracted signals:
            {
                "entity_scores": {"Blake Lively": -0.8, "Justin Baldoni": 0.6},
                "emotion": "disgust",
                "stance": "oppose",
                "topics": ["lawsuit", "casting"],
                "other_entities": ["Colleen Hoover", "Justin Bieber"],
                "sarcasm": False,
                "toxicity": 0.3
            }
        """
        monitored_list = ", ".join(monitored_entities) if monitored_entities else "none"
        
        prompt = f'''Post caption: "{post_caption[:500]}"
Comment: "{comment_text[:1000]}"
Comment likes: {comment_likes}
Monitored entities (for reference): {monitored_list}

Extract signals from this comment. 

CRITICAL INSTRUCTIONS - ENTITY SCORING:
- Score ONLY entities that are ACTUALLY MENTIONED in the comment text
- If the comment says "she" or "he", use post caption context to determine who
- If a monitored entity is NOT mentioned in this specific comment, do NOT include it in entity_scores
- Return empty entity_scores {{}} if no monitored entities are mentioned
- If an entity is mentioned but not in monitored list, include it in other_entities
- DO NOT score entities just because they're in the caption if the comment doesn't reference them

CONFIDENCE GUIDELINES:
- 0.9-1.0: Full name mentioned (e.g., "Justin Baldoni") or clear context
- 0.7-0.9: First name + strong context (e.g., "Justin" on Colleen Hoover post about Justin Baldoni)
- 0.5-0.7: First name + weak context → ambiguous_mentions
- < 0.5: Cannot determine → ambiguous_mentions

SARCASM & SENTIMENT:
- Detect sarcasm: 💐 + "you earned it" = sarcasm, negative sentiment
- Questions like "Is X true?" are neutral (0.0) unless clearly rhetorical
- High like counts indicate community agreement - weight sarcasm detection accordingly
- Context matters: "I feel bad for X" = positive toward X, negative toward situation

DISAMBIGUATION EXAMPLES:
- Comment: "Justin didn't attend" on Hailey Bieber post → "Justin Bieber" (confidence 0.8+)
- Comment: "Justin is wrong" on Colleen Hoover post → "Justin Baldoni" (confidence 0.8+)
- Comment: "Justin" on unrelated post → ambiguous_mentions (confidence < 0.7)

FIX 5: DO NOT hallucinate entity mentions. Only score entities actually discussed in the comment.

Return valid JSON only.'''
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=400,  # Increased from 200 to reduce truncation
                response_format={"type": "json_object"}  # Force JSON output
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # Store raw response for debugging (can be accessed via _last_response)
            self._last_response = response_text
            
            # Try to parse JSON with error recovery
            result = self._parse_json_with_recovery(response_text)
            
            # Validate and normalize result
            normalized = {
                "entity_scores": self._validate_entity_scores(result.get("entity_scores", {}), monitored_entities, comment_text, result.get("stance")),
                "entity_confidence": self._validate_entity_confidence(result.get("entity_confidence", {}), result.get("entity_scores", {})),
                "emotion": self._validate_emotion(result.get("emotion", "neutral")),
                "stance": self._validate_stance(result.get("stance", "neutral")),
                "topics": self._validate_topics(result.get("topics", [])),
                "other_entities": self._validate_other_entities(result.get("other_entities", [])),
                "sarcasm": bool(result.get("sarcasm", False)),
                "toxicity": self._validate_toxicity(result.get("toxicity", 0.0)),
                "ambiguous_mentions": self._validate_ambiguous_mentions(result.get("ambiguous_mentions", []))
            }
            
            # Ensure entity_scores is always a dict (even if empty)
            if not isinstance(normalized["entity_scores"], dict):
                normalized["entity_scores"] = {}
            
            # Don't force entity scores - GPT should only score entities actually mentioned
            # If no entity_scores returned, that's fine - the comment might not mention any monitored entities
            
            return normalized
            
        except Exception as e:
            print(f"OpenAI API error: {e}")
            if 'response' in locals() and hasattr(response, 'choices'):
                print(f"Response preview: {response.choices[0].message.content[:200] if response.choices else 'No response'}")
            # Return safe defaults
            return {
                "entity_scores": {},
                "entity_confidence": {},
                "emotion": "neutral",
                "stance": "neutral",
                "topics": [],
                "other_entities": [],
                "sarcasm": False,
                "toxicity": 0.0,
                "ambiguous_mentions": []
            }
    
    def _parse_json_with_recovery(self, text: str) -> Dict[str, Any]:
        """
        Parse JSON with recovery strategies for common truncation issues.
        
        Strategies:
        1. Try direct parse
        2. Try to fix common truncation issues (unclosed strings, missing brackets)
        3. Extract partial data if possible
        """
        # First, try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            # Try to fix common issues
            fixed_text = self._fix_truncated_json(text, e)
            try:
                return json.loads(fixed_text)
            except json.JSONDecodeError:
                # Last resort: try to extract what we can
                return self._extract_partial_json(text)
    
    def _fix_truncated_json(self, text: str, error: json.JSONDecodeError) -> str:
        """Attempt to fix common JSON truncation issues."""
        # If error is about unterminated string, try to close it
        if "Unterminated string" in str(error):
            # Find the last quote and try to close the string
            last_quote_idx = text.rfind('"')
            if last_quote_idx > 0:
                # Check if it's an opening quote (no closing quote after)
                remaining = text[last_quote_idx + 1:]
                if '"' not in remaining and '}' not in remaining:
                    # Likely truncated string, close it
                    text = text[:last_quote_idx + 1] + '"'
        
        # If error is about missing closing bracket/brace
        if "Expecting" in str(error) and ("}" in str(error) or "]" in str(error)):
            # Count opening vs closing braces/brackets
            open_braces = text.count('{')
            close_braces = text.count('}')
            open_brackets = text.count('[')
            close_brackets = text.count(']')
            
            # Add missing closing characters
            text += '}' * (open_braces - close_braces)
            text += ']' * (open_brackets - close_brackets)
        
        return text
    
    def _extract_partial_json(self, text: str) -> Dict[str, Any]:
        """Extract whatever valid JSON we can from a malformed response."""
        result = {}
        
        # Try to extract entity_scores using regex
        import re
        
        # Extract entity_scores pattern: "entity_scores": {"EntityName": number, ...}
        entity_scores_match = re.search(r'"entity_scores"\s*:\s*\{([^}]*)\}', text)
        if entity_scores_match:
            scores_text = entity_scores_match.group(1)
            # Try to parse individual score pairs
            score_pairs = re.findall(r'"([^"]+)"\s*:\s*(-?\d+\.?\d*)', scores_text)
            result["entity_scores"] = {name: float(score) for name, score in score_pairs}
        else:
            result["entity_scores"] = {}
        
        # Extract emotion
        emotion_match = re.search(r'"emotion"\s*:\s*"([^"]+)"', text)
        if emotion_match:
            result["emotion"] = emotion_match.group(1)
        else:
            result["emotion"] = "neutral"
        
        # Extract stance
        stance_match = re.search(r'"stance"\s*:\s*"([^"]+)"', text)
        if stance_match:
            result["stance"] = stance_match.group(1)
        else:
            result["stance"] = "neutral"
        
        # Extract topics array
        topics_match = re.search(r'"topics"\s*:\s*\[([^\]]*)\]', text)
        if topics_match:
            topics_text = topics_match.group(1)
            topics = re.findall(r'"([^"]+)"', topics_text)
            result["topics"] = topics
        else:
            result["topics"] = []
        
        # Extract toxicity
        toxicity_match = re.search(r'"toxicity"\s*:\s*(\d+\.?\d*)', text)
        if toxicity_match:
            result["toxicity"] = float(toxicity_match.group(1))
        else:
            result["toxicity"] = 0.0
        
        # Extract sarcasm
        sarcasm_match = re.search(r'"sarcasm"\s*:\s*(true|false)', text, re.IGNORECASE)
        if sarcasm_match:
            result["sarcasm"] = sarcasm_match.group(1).lower() == "true"
        else:
            result["sarcasm"] = False
        
        # Extract other_entities
        other_entities_match = re.search(r'"other_entities"\s*:\s*\[([^\]]*)\]', text)
        if other_entities_match:
            entities_text = other_entities_match.group(1)
            entities = re.findall(r'"([^"]+)"', entities_text)
            result["other_entities"] = entities
        else:
            result["other_entities"] = []
        
        return result
    
    def _validate_entity_scores(self, entity_scores: Any, monitored_entities: Optional[List[str]], comment_text: str, inferred_stance: Optional[str]) -> Dict[str, float]:
        """
        Validate entity scores from GPT response.
        
        Note: We no longer force scores for entities that weren't mentioned.
        GPT should only return scores for entities actually discussed in the comment.
        """
        if not isinstance(entity_scores, dict):
            return {}
        
        validated = {}
        for entity_name, score in entity_scores.items():
            try:
                score_float = float(score)
                if -1.0 <= score_float <= 1.0:
                    # Strip disambiguation hints for matching
                    entity_clean = entity_name.split(" (")[0].strip()
                    validated[entity_clean] = score_float
            except (ValueError, TypeError):
                continue
        
        # Don't force scores for entities not mentioned - GPT should only score what's relevant
        return validated
    
    def _validate_entity_confidence(self, confidence_dict: Any, entity_scores: Dict[str, float]) -> Dict[str, float]:
        """Validate entity confidence scores."""
        if not isinstance(confidence_dict, dict):
            # If no confidence provided, assume 0.8 for all entities (moderate confidence)
            return {entity: 0.8 for entity in entity_scores.keys()}
        
        validated = {}
        for entity_name, confidence in confidence_dict.items():
            try:
                conf_float = float(confidence)
                if 0.0 <= conf_float <= 1.0:
                    entity_clean = entity_name.split(" (")[0].strip()
                    validated[entity_clean] = conf_float
            except (ValueError, TypeError):
                continue
        
        # Ensure all entities in entity_scores have confidence scores
        for entity_name in entity_scores.keys():
            entity_clean = entity_name.split(" (")[0].strip()
            if entity_clean not in validated:
                validated[entity_clean] = 0.8  # Default moderate confidence
        
        return validated
    
    def _validate_ambiguous_mentions(self, ambiguous: Any) -> List[Dict[str, Any]]:
        """Validate ambiguous mentions list."""
        if not isinstance(ambiguous, list):
            return []
        
        validated = []
        for item in ambiguous:
            if isinstance(item, dict):
                validated.append({
                    "name": str(item.get("name", "")),
                    "possible_entities": item.get("possible_entities", []),
                    "confidence": float(item.get("confidence", 0.5)),
                    "reason": str(item.get("reason", "Low confidence"))
                })
        
        return validated
    
    def _validate_emotion(self, emotion: Any) -> str:
        """Validate emotion value."""
        valid_emotions = ["anger", "disgust", "joy", "disappointment", "sarcasm", "neutral"]
        emotion_str = str(emotion).lower()
        return emotion_str if emotion_str in valid_emotions else "neutral"
    
    def _validate_stance(self, stance: Any) -> str:
        """Validate stance value."""
        valid_stances = ["support", "oppose", "neutral"]
        stance_str = str(stance).lower()
        return stance_str if stance_str in valid_stances else "neutral"
    
    def _validate_topics(self, topics: Any) -> List[str]:
        """Validate topics list."""
        if not isinstance(topics, list):
            return []
        return [str(topic) for topic in topics if topic]
    
    def _validate_other_entities(self, entities: Any) -> List[str]:
        """Validate other_entities list."""
        if not isinstance(entities, list):
            return []
        return [str(entity) for entity in entities if entity]
    
    def _validate_toxicity(self, toxicity: Any) -> float:
        """Validate and clamp toxicity score."""
        try:
            toxicity_float = float(toxicity)
            return max(0.0, min(1.0, toxicity_float))
        except (ValueError, TypeError):
            return 0.0


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

