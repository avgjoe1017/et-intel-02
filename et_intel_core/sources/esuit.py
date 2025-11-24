"""
ESUIT CSV format adapter.
"""

from pathlib import Path
from typing import Iterator
import pandas as pd

from et_intel_core.schemas import RawComment


class ESUITSource:
    """
    Adapter for ESUIT CSV exports.
    
    Expected columns:
    - Post URL
    - Caption
    - Subject
    - Username
    - Comment
    - Timestamp
    - Likes
    """
    
    def __init__(self, csv_path: Path):
        """
        Initialize ESUIT source adapter.
        
        Args:
            csv_path: Path to ESUIT CSV file
        """
        self.csv_path = csv_path
    
    def iter_records(self) -> Iterator[RawComment]:
        """
        Yield normalized comments from ESUIT CSV.
        
        Simple, synchronous CSV reading - no async needed for local files.
        """
        df = pd.read_csv(self.csv_path)
        
        for _, row in df.iterrows():
            # Extract post ID from URL
            # Example: https://instagram.com/p/ABC123/ -> ABC123
            post_url = row['Post URL']
            external_post_id = post_url.rstrip('/').split('/')[-1]
            if external_post_id == 'p':
                # Handle case: /p/ABC123/
                external_post_id = post_url.rstrip('/').split('/')[-2]
            
            yield RawComment(
                platform="instagram",
                external_post_id=external_post_id,
                post_url=post_url,
                post_caption=row.get('Caption', ''),
                post_subject=row.get('Subject', ''),
                comment_author=row['Username'],
                comment_text=row['Comment'],
                comment_timestamp=pd.to_datetime(row['Timestamp']),
                like_count=int(row.get('Likes', 0)),
                raw=row.to_dict()
            )

