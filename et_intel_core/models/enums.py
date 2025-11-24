"""
Enums for ET Intelligence models.
"""

from enum import Enum as PyEnum


class PlatformType(str, PyEnum):
    """Social media platforms."""
    INSTAGRAM = "instagram"
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"


class SignalType(str, PyEnum):
    """Types of intelligence signals extracted from comments."""
    SENTIMENT = "sentiment"       # -1.0 to 1.0
    EMOTION = "emotion"           # "anger", "joy", "excitement"
    STORYLINE = "storyline"       # "lawsuit", "divorce", "comeback"
    RISK_FLAG = "risk_flag"       # "threat", "doxxing", "harassment"


class ContextType(str, PyEnum):
    """Comment threading context."""
    DIRECT = "direct"             # Top-level comment
    REPLY = "reply"               # Direct reply
    THREAD = "thread"             # Deep nested (context drift risk)


class EntityType(str, PyEnum):
    """Types of monitored entities."""
    PERSON = "person"
    SHOW = "show"
    COUPLE = "couple"
    BRAND = "brand"

