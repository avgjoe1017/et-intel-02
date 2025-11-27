"""
Source adapters for ingesting data from various formats.
"""

from et_intel_core.sources.base import IngestionSource
from et_intel_core.sources.esuit import ESUITSource
from et_intel_core.sources.apify import ApifySource
from et_intel_core.sources.apify_live import ApifyLiveSource
from et_intel_core.sources.apify_posts import ApifyPostSource
from et_intel_core.sources.apify_metadata import ApifyMetadataSource

# Try to import merged source (may not be available)
try:
    from et_intel_core.sources.apify_merged import ApifyMergedAdapter
    __all__ = [
        "IngestionSource",
        "ESUITSource",
        "ApifySource",
        "ApifyLiveSource",
        "ApifyPostSource",
        "ApifyMetadataSource",
        "ApifyMergedAdapter",
    ]
except ImportError:
    __all__ = [
        "IngestionSource",
        "ESUITSource",
        "ApifySource",
        "ApifyLiveSource",
        "ApifyPostSource",
        "ApifyMetadataSource",
    ]

