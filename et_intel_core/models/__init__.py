"""
SQLAlchemy models for ET Intelligence V2.

Key Design:
- Posts & Comments: Source of truth (raw data)
- ExtractedSignals: Intelligence layer (multi-perspective)
- MonitoredEntities: Dynamic configuration
- DiscoveredEntities: Tracking unmapped entities
"""

from et_intel_core.models.base import Base
from et_intel_core.models.enums import (
    PlatformType,
    SignalType,
    ContextType,
    EntityType
)
from et_intel_core.models.post import Post
from et_intel_core.models.comment import Comment
from et_intel_core.models.monitored_entity import MonitoredEntity
from et_intel_core.models.extracted_signal import ExtractedSignal
from et_intel_core.models.discovered_entity import DiscoveredEntity
from et_intel_core.models.review_queue import ReviewQueue

__all__ = [
    "Base",
    "PlatformType",
    "SignalType",
    "ContextType",
    "EntityType",
    "Post",
    "Comment",
    "MonitoredEntity",
    "ExtractedSignal",
    "DiscoveredEntity",
    "ReviewQueue",
]

