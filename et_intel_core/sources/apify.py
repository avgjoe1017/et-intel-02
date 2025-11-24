"""
Apify CSV format adapter.
"""

from pathlib import Path
from typing import Iterator
import pandas as pd

from et_intel_core.schemas import RawComment


class ApifySource:
    """
    Adapter for Apify CSV exports.
    
    Expected columns:
    - shortCode (post ID)
    - url
    - caption
    - ownerUsername
    - text (comment text)
    - timestamp
    - likesCount
    """
    
    def __init__(self, csv_path: Path):
        """
        Initialize Apify source adapter.
        
        Args:
            csv_path: Path to Apify CSV file
        """
        self.csv_path = csv_path
    
    def iter_records(self) -> Iterator[RawComment]:
        """
        Yield normalized comments from Apify CSV.
        
        Apify has different column names than ESUIT,
        but we normalize to the same RawComment structure.
        """
        df = pd.read_csv(self.csv_path)
        
        for _, row in df.iterrows():
            yield RawComment(
                platform="instagram",
                external_post_id=row['shortCode'],
                post_url=row['url'],
                post_caption=row.get('caption', ''),
                post_subject=None,  # Apify doesn't track editorial subjects
                comment_author=row['ownerUsername'],
                comment_text=row['text'],
                comment_timestamp=pd.to_datetime(row['timestamp']),
                like_count=int(row.get('likesCount', 0)),
                raw=row.to_dict()
            )

