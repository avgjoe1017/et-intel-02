"""
Base protocol for ingestion sources.
"""

from typing import Protocol, Iterator
from et_intel_core.schemas import RawComment


class IngestionSource(Protocol):
    """
    Protocol that every CSV/API adapter must implement.
    
    This allows source-agnostic ingestion - the IngestionService
    doesn't care if data comes from ESUIT, Apify, or Instagram API.
    """
    
    def iter_records(self) -> Iterator[RawComment]:
        """
        Yield normalized comments one at a time.
        
        Synchronous by design - CSV files are local, no need for async.
        Add async version only when fetching from APIs with rate limits.
        
        Yields:
            RawComment: Validated, normalized comment data
        """
        ...

