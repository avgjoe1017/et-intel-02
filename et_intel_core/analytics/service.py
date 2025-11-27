"""
Analytics service - queries database and computes metrics.
"""

import uuid
from typing import Tuple, Optional, List, Dict, Any
from datetime import datetime, timedelta
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import text, func, and_, or_, select

from et_intel_core.models import (
    Comment,
    ExtractedSignal,
    MonitoredEntity,
    DiscoveredEntity,
    Post,
    SignalType
)


class AnalyticsService:
    """
    Analytics layer: queries database, computes metrics.
    No presentation logic (that's for report generator).
    All queries are timezone-aware (UTC).
    
    Key features:
    - Clean SQL queries using numeric_value column
    - Time-windowed aggregations
    - Velocity detection (sentiment change over time)
    - Entity comparisons
    """
    
    def __init__(self, session: Session):
        """
        Initialize analytics service.
        
        Args:
            session: SQLAlchemy database session
        """
        self.session = session
    
    def get_top_entities(
        self,
        time_window: Tuple[datetime, datetime],
        platforms: Optional[List[str]] = None,
        limit: int = 20
    ) -> pd.DataFrame:
        """
        Get top entities by mention count + average sentiment.
        Uses numeric_value column for clean aggregation.
        
        Args:
            time_window: Tuple of (start_date, end_date)
            platforms: Optional list of platforms to filter by
            limit: Maximum number of entities to return
            
        Returns:
            DataFrame with columns:
            - entity_name: Entity name
            - entity_type: Entity type (person, show, etc.)
            - mention_count: Number of comments mentioning entity
            - avg_sentiment: Average sentiment score
            - total_likes: Sum of likes on comments
            - weighted_sentiment: Like-weighted average sentiment
        """
        query = text("""
        SELECT 
            me.id as entity_id,
            me.name as entity_name,
            me.entity_type,
            COUNT(DISTINCT es.comment_id) as mention_count,
            AVG(es.numeric_value) as avg_sentiment,
            SUM(c.likes) as total_likes,
            CASE 
                WHEN SUM(es.weight_score) > 0 
                THEN SUM(es.numeric_value * es.weight_score) / SUM(es.weight_score)
                ELSE AVG(es.numeric_value)
            END as weighted_sentiment
        FROM extracted_signals es
        JOIN comments c ON es.comment_id = c.id
        JOIN monitored_entities me ON es.entity_id = me.id
        JOIN posts p ON c.post_id = p.id
        WHERE es.signal_type = 'sentiment'
          AND c.created_at BETWEEN :start AND :end
          AND es.numeric_value IS NOT NULL
          AND es.entity_id IS NOT NULL
        """)
        
        params = {"start": time_window[0], "end": time_window[1]}
        
        if platforms:
            # Check if SQLite (doesn't support ANY())
            try:
                is_sqlite = self.session.bind.dialect.name == 'sqlite'
            except (AttributeError, TypeError):
                is_sqlite = False
            
            if is_sqlite:
                # SQLite: use IN clause
                platforms_str = ','.join([f"'{p}'" for p in platforms])
                query = text(str(query) + f" AND p.platform IN ({platforms_str})")
            else:
                query = text(str(query) + " AND p.platform = ANY(:platforms)")
                params["platforms"] = platforms
        
        query = text(str(query) + """
        GROUP BY me.id, me.name, me.entity_type
        ORDER BY mention_count DESC
        LIMIT :limit
        """)
        params["limit"] = limit
        
        result = self.session.execute(query, params)
        df = pd.DataFrame(result.fetchall(), columns=result.keys())
        
        return df
    
    def compute_velocity(
        self,
        entity_id: uuid.UUID,
        window_hours: int = 72,
        min_sample_size: int = 10
    ) -> Dict:
        """
        Calculate sentiment velocity for an entity.
        Returns percent change over window.
        
        Designed for LIVE ALERTS (relative to NOW).
        For briefs, see compute_brief_velocity().
        
        Args:
            entity_id: UUID of entity to analyze
            window_hours: Hours to look back (default 72)
            min_sample_size: Minimum comments required (default 10)
            
        Returns:
            Dictionary with:
            - entity_id: Entity UUID (as string)
            - window_hours: Window size
            - recent_sentiment: Average sentiment in recent window
            - previous_sentiment: Average sentiment in previous window
            - percent_change: Percent change
            - recent_sample_size: Number of comments in recent window
            - previous_sample_size: Number of comments in previous window
            - alert: True if |percent_change| > 30%
            - direction: "up" or "down"
            - calculated_at: Timestamp
            
            Or {"error": "message"} if insufficient data
        """
        now = datetime.utcnow()
        recent_start = now - timedelta(hours=window_hours)
        previous_start = now - timedelta(hours=window_hours * 2)
        
        # Convert UUID to string for SQLite compatibility
        try:
            is_sqlite = self.session.bind.dialect.name == 'sqlite'
        except (AttributeError, TypeError):
            is_sqlite = False
        
        # For SQLite, UUIDs are stored as TEXT, but we need to handle format differences
        # SQLAlchemy might store with or without dashes, so we normalize
        if is_sqlite:
            # Convert UUID to string and remove dashes for consistent comparison
            entity_id_param = str(entity_id).replace('-', '')
            # Use LIKE or = with normalized format
            entity_condition = "REPLACE(es.entity_id, '-', '') = :entity_id"
        else:
            entity_id_param = entity_id
            entity_condition = "es.entity_id = :entity_id"
        
        recent_query = text(f"""
            SELECT 
                AVG(es.numeric_value) as avg_sentiment,
                COUNT(*) as count
            FROM extracted_signals es
            JOIN comments c ON es.comment_id = c.id
            WHERE {entity_condition}
              AND es.signal_type = 'sentiment'
              AND es.numeric_value IS NOT NULL
              AND c.created_at BETWEEN :recent_start AND :now
        """)
        
        recent = self.session.execute(
            recent_query,
            {"entity_id": entity_id_param, "recent_start": recent_start, "now": now}
        ).fetchone()
        
        # Previous sentiment (previous N hours)
        previous_query = text(f"""
            SELECT 
                AVG(es.numeric_value) as avg_sentiment,
                COUNT(*) as count
            FROM extracted_signals es
            JOIN comments c ON es.comment_id = c.id
            WHERE {entity_condition}
              AND es.signal_type = 'sentiment'
              AND es.numeric_value IS NOT NULL
              AND c.created_at BETWEEN :previous_start AND :recent_start
        """)
        
        previous = self.session.execute(
            previous_query,
            {"entity_id": entity_id_param, "previous_start": previous_start, "recent_start": recent_start}
        ).fetchone()
        
        # Validation
        recent_count = recent.count if recent and recent.count else 0
        previous_count = previous.count if previous and previous.count else 0
        
        if recent_count < min_sample_size or previous_count < min_sample_size:
            return {
                "error": "Insufficient data",
                "recent_count": recent_count,
                "previous_count": previous_count,
                "min_required": min_sample_size
            }
        
        # Calculate velocity
        if previous.avg_sentiment == 0:
            percent_change = 0
        else:
            percent_change = (
                (recent.avg_sentiment - previous.avg_sentiment) / abs(previous.avg_sentiment)
            ) * 100
        
        return {
            "entity_id": str(entity_id),
            "window_hours": window_hours,
            "recent_sentiment": round(float(recent.avg_sentiment), 3),
            "previous_sentiment": round(float(previous.avg_sentiment), 3),
            "percent_change": round(percent_change, 1),
            "recent_sample_size": recent.count,
            "previous_sample_size": previous.count,
            "alert": abs(percent_change) > 30,  # Alert threshold
            "direction": "up" if percent_change > 0 else "down",
            "calculated_at": now.isoformat()
        }
    
    def compute_brief_velocity(
        self,
        entity_id: uuid.UUID,
        brief_window: Tuple[datetime, datetime]
    ) -> Dict:
        """
        Calculate velocity WITHIN a brief window.
        Compares first half vs second half of window.
        
        Use this for briefs, not live alerts.
        
        Args:
            entity_id: UUID of entity to analyze
            brief_window: Tuple of (start_date, end_date)
            
        Returns:
            Dictionary with velocity metrics or {"error": "message"}
        """
        start, end = brief_window
        midpoint = start + (end - start) / 2
        
        # Convert UUID to string for SQLite compatibility
        try:
            is_sqlite = self.session.bind.dialect.name == 'sqlite'
        except (AttributeError, TypeError):
            is_sqlite = False
        
        if is_sqlite:
            entity_id_param = str(entity_id).replace('-', '')
            entity_condition = "REPLACE(es.entity_id, '-', '') = :entity_id"
        else:
            entity_id_param = entity_id
            entity_condition = "es.entity_id = :entity_id"
        
        # First half sentiment
        first_half = self.session.execute(text(f"""
            SELECT AVG(es.numeric_value) as avg_sentiment, COUNT(*) as count
            FROM extracted_signals es
            JOIN comments c ON es.comment_id = c.id
            WHERE {entity_condition}
              AND es.signal_type = 'sentiment'
              AND es.numeric_value IS NOT NULL
              AND c.created_at BETWEEN :start AND :midpoint
        """), {"entity_id": entity_id_param, "start": start, "midpoint": midpoint}).fetchone()
        
        # Second half sentiment
        second_half = self.session.execute(text(f"""
            SELECT AVG(es.numeric_value) as avg_sentiment, COUNT(*) as count
            FROM extracted_signals es
            JOIN comments c ON es.comment_id = c.id
            WHERE {entity_condition}
              AND es.signal_type = 'sentiment'
              AND es.numeric_value IS NOT NULL
              AND c.created_at BETWEEN :midpoint AND :end
        """), {"entity_id": entity_id_param, "midpoint": midpoint, "end": end}).fetchone()
        
        if not first_half or not second_half or first_half.count < 5 or second_half.count < 5:
            return {"error": "Insufficient data for brief window"}
        
        percent_change = (
            (second_half.avg_sentiment - first_half.avg_sentiment) / abs(first_half.avg_sentiment)
        ) * 100 if first_half.avg_sentiment != 0 else 0
        
        return {
            "entity_id": str(entity_id),
            "brief_window": f"{start.date()} to {end.date()}",
            "first_half_sentiment": round(float(first_half.avg_sentiment), 3),
            "second_half_sentiment": round(float(second_half.avg_sentiment), 3),
            "percent_change": round(percent_change, 1),
            "trending": "up" if percent_change > 0 else "down"
        }
    
    def get_emotion_distribution(
        self,
        entity_id: uuid.UUID,
        days: int = 7
    ) -> Dict[str, int]:
        """
        Get emotion breakdown for an entity.
        
        Args:
            entity_id: UUID of entity to analyze
            days: Number of days to look back
            
        Returns:
            Dictionary mapping emotion names to counts
            e.g., {"anger": 45, "disgust": 23, "joy": 12}
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        try:
            is_sqlite = self.session.bind.dialect.name == 'sqlite'
        except (AttributeError, TypeError):
            is_sqlite = False
        
        if is_sqlite:
            entity_id_param = str(entity_id).replace('-', '')
            entity_condition = "REPLACE(es.entity_id, '-', '') = :entity_id"
        else:
            entity_id_param = entity_id
            entity_condition = "es.entity_id = :entity_id"
        
        query = text(f"""
            SELECT es.value as emotion, COUNT(*) as count
            FROM extracted_signals es
            JOIN comments c ON es.comment_id = c.id
            WHERE {entity_condition}
              AND es.signal_type = 'emotion'
              AND c.created_at > :cutoff_date
            GROUP BY es.value
            ORDER BY count DESC
        """)
        
        result = self.session.execute(
            query,
            {"entity_id": entity_id_param, "cutoff_date": cutoff_date}
        )
        
        return {row.emotion: row.count for row in result}
    
    def get_top_topics(
        self,
        days: int = 7,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get trending topics from TOPIC signals.
        
        Args:
            days: Number of days to look back
            limit: Maximum number of topics to return
            
        Returns:
            List of dictionaries with topic name and mention count
            e.g., [{"topic": "lawsuit", "mentions": 234}, ...]
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        query = text("""
            SELECT es.value as topic, COUNT(*) as mentions
            FROM extracted_signals es
            JOIN comments c ON es.comment_id = c.id
            WHERE es.signal_type = 'topic'
              AND c.created_at > :cutoff_date
            GROUP BY es.value
            ORDER BY mentions DESC
            LIMIT :limit
        """)
        
        result = self.session.execute(
            query,
            {"cutoff_date": cutoff_date, "limit": limit}
        )
        
        return [
            {"topic": row.topic, "mentions": row.mentions}
            for row in result
        ]
    
    def get_toxicity_alerts(
        self,
        threshold: float = 0.7,
        days: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Get comments with high toxicity scores.
        
        Args:
            threshold: Minimum toxicity score to flag (0.0-1.0)
            days: Number of days to look back
            
        Returns:
            List of dictionaries with comment details and toxicity score
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        query = text("""
            SELECT 
                c.id,
                c.text,
                c.author_name,
                c.likes,
                es.numeric_value as toxicity_score,
                p.url as post_url
            FROM extracted_signals es
            JOIN comments c ON es.comment_id = c.id
            JOIN posts p ON c.post_id = p.id
            WHERE es.signal_type = 'toxicity'
              AND es.numeric_value >= :threshold
              AND c.created_at > :cutoff_date
            ORDER BY es.numeric_value DESC, c.likes DESC
            LIMIT 50
        """)
        
        result = self.session.execute(
            query,
            {"threshold": threshold, "cutoff_date": cutoff_date}
        )
        
        return [
            {
                "comment_id": str(row.id),
                "text": row.text[:200],  # Truncate for display
                "author": row.author_name,
                "likes": row.likes,
                "toxicity": float(row.toxicity_score),
                "post_url": row.post_url
            }
            for row in result
        ]
    
    def get_stance_breakdown(
        self,
        entity_id: uuid.UUID,
        days: int = 7
    ) -> Dict[str, int]:
        """
        Get support/oppose/neutral counts for entity.
        
        Args:
            entity_id: UUID of entity to analyze
            days: Number of days to look back
            
        Returns:
            Dictionary with stance counts
            e.g., {"support": 234, "oppose": 156, "neutral": 45}
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        try:
            is_sqlite = self.session.bind.dialect.name == 'sqlite'
        except (AttributeError, TypeError):
            is_sqlite = False
        
        if is_sqlite:
            entity_id_param = str(entity_id).replace('-', '')
            entity_condition = "REPLACE(es.entity_id, '-', '') = :entity_id"
        else:
            entity_id_param = entity_id
            entity_condition = "es.entity_id = :entity_id"
        
        query = text(f"""
            SELECT es.value as stance, COUNT(*) as count
            FROM extracted_signals es
            JOIN comments c ON es.comment_id = c.id
            WHERE {entity_condition}
              AND es.signal_type = 'stance'
              AND c.created_at > :cutoff_date
            GROUP BY es.value
        """)
        
        result = self.session.execute(
            query,
            {"entity_id": entity_id_param, "cutoff_date": cutoff_date}
        )
        
        breakdown = {row.stance: row.count for row in result}
        
        # Ensure all stances are present
        for stance in ["support", "oppose", "neutral"]:
            if stance not in breakdown:
                breakdown[stance] = 0
        
        return breakdown
    
    def get_top_comments_for_entity(
        self,
        entity_id: uuid.UUID,
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Get top comments mentioning an entity, ordered by likes.
        
        Args:
            entity_id: UUID of entity to find comments for
            limit: Maximum number of comments to return
            
        Returns:
            List of dictionaries with comment details
        """
        try:
            is_sqlite = self.session.bind.dialect.name == 'sqlite'
        except (AttributeError, TypeError):
            is_sqlite = False
        
        if is_sqlite:
            entity_id_param = str(entity_id).replace('-', '')
            entity_condition = "REPLACE(es.entity_id, '-', '') = :entity_id"
        else:
            entity_id_param = entity_id
            entity_condition = "es.entity_id = :entity_id"
        
        query = text(f"""
            SELECT DISTINCT
                c.id,
                c.text,
                c.author_name,
                c.likes,
                p.caption as post_caption
            FROM extracted_signals es
            JOIN comments c ON es.comment_id = c.id
            JOIN posts p ON c.post_id = p.id
            WHERE {entity_condition}
              AND es.signal_type = 'sentiment'
            ORDER BY c.likes DESC
            LIMIT :limit
        """)
        
        result = self.session.execute(
            query,
            {"entity_id": entity_id_param, "limit": limit}
        )
        
        return [
            {
                "id": str(row.id),
                "text": row.text,
                "author": row.author_name,
                "likes": row.likes,
                "post_caption": row.post_caption or ""
            }
            for row in result
        ]
    
    def get_entity_sentiment_history(
        self,
        entity_id: uuid.UUID,
        days: int = 30
    ) -> pd.DataFrame:
        """
        Time series of sentiment for charts.
        
        Args:
            entity_id: UUID of entity to analyze
            days: Number of days to look back
            
        Returns:
            DataFrame with columns:
            - date: Date (day granularity)
            - avg_sentiment: Average sentiment for that day
            - mention_count: Number of mentions that day
            - total_likes: Sum of likes that day
        """
        # Check if SQLite
        try:
            is_sqlite = self.session.bind.dialect.name == 'sqlite'
        except (AttributeError, TypeError):
            is_sqlite = False
        
        if is_sqlite:
            # SQLite-compatible query
            entity_id_param = str(entity_id).replace('-', '')
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            query = text("""
            SELECT 
                DATE(c.created_at) as date,
                AVG(es.numeric_value) as avg_sentiment,
                COUNT(DISTINCT es.comment_id) as mention_count,
                SUM(c.likes) as total_likes
            FROM extracted_signals es
            JOIN comments c ON es.comment_id = c.id
            WHERE REPLACE(es.entity_id, '-', '') = :entity_id
              AND es.signal_type = 'sentiment'
              AND es.numeric_value IS NOT NULL
              AND c.created_at > :cutoff_date
            GROUP BY date
            ORDER BY date
            """)
            result = self.session.execute(
                query,
                {"entity_id": entity_id_param, "cutoff_date": cutoff_date}
            )
        else:
            # PostgreSQL query
            query = text("""
            SELECT 
                DATE_TRUNC('day', c.created_at) as date,
                AVG(es.numeric_value) as avg_sentiment,
                COUNT(DISTINCT es.comment_id) as mention_count,
                SUM(c.likes) as total_likes
            FROM extracted_signals es
            JOIN comments c ON es.comment_id = c.id
            WHERE es.entity_id = :entity_id
              AND es.signal_type = 'sentiment'
              AND es.numeric_value IS NOT NULL
              AND c.created_at > NOW() - INTERVAL ':days days'
            GROUP BY date
            ORDER BY date
            """)
            result = self.session.execute(
                query,
                {"entity_id": entity_id, "days": days}
            )
        
        df = pd.DataFrame(result.fetchall(), columns=result.keys())
        
        return df
    
    def get_comment_count(self, time_window: Tuple[datetime, datetime]) -> int:
        """
        Simple count of comments in window.
        
        Args:
            time_window: Tuple of (start_date, end_date)
            
        Returns:
            Number of comments
        """
        result = self.session.execute(text("""
            SELECT COUNT(*)
            FROM comments
            WHERE created_at BETWEEN :start AND :end
        """), {"start": time_window[0], "end": time_window[1]})
        
        return result.scalar()
    
    def get_top_comments_for_entity(
        self,
        entity_id: uuid.UUID,
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Return top comments (by likes) that mention a given entity.
        """
        query = text("""
        SELECT 
            c.text,
            c.likes,
            c.created_at
        FROM comments c
        JOIN extracted_signals es ON es.comment_id = c.id
        WHERE es.entity_id = :entity_id
          AND es.signal_type = 'sentiment'
          AND es.numeric_value IS NOT NULL
        ORDER BY c.likes DESC NULLS LAST, c.created_at DESC
        LIMIT :limit
        """)
        
        result = self.session.execute(
            query,
            {"entity_id": str(entity_id), "limit": limit}
        )
        comments = []
        for row in result:
            comments.append({
                "text": row.text or "",
                "likes": row.likes or 0,
                "created_at": row.created_at
            })
        return comments
    
    def get_discovered_entities(
        self,
        min_mentions: int = 5,
        reviewed: bool = False,
        limit: int = 50
    ) -> pd.DataFrame:
        """
        Get list of entities discovered by spaCy but not in MonitoredEntity.
        For periodic review: "Who should we add to tracking?"
        
        Args:
            min_mentions: Minimum mention count to include
            reviewed: Include only reviewed (True) or unreviewed (False)
            limit: Maximum number to return
            
        Returns:
            DataFrame with discovered entity information
        """
        query = text("""
        SELECT 
            name,
            entity_type,
            mention_count,
            first_seen_at,
            last_seen_at,
            sample_mentions
        FROM discovered_entities
        WHERE mention_count >= :min_mentions
          AND reviewed = :reviewed
        ORDER BY mention_count DESC
        LIMIT :limit
        """)
        
        result = self.session.execute(
            query,
            {
                "min_mentions": min_mentions,
                "reviewed": reviewed,
                "limit": limit
            }
        )
        
        df = pd.DataFrame(result.fetchall(), columns=result.keys())
        
        return df
    
    def get_entity_comparison(
        self,
        entity_ids: List[uuid.UUID],
        time_window: Tuple[datetime, datetime]
    ) -> pd.DataFrame:
        """
        Compare multiple entities side-by-side.
        
        Args:
            entity_ids: List of entity UUIDs to compare
            time_window: Tuple of (start_date, end_date)
            
        Returns:
            DataFrame with comparison metrics for each entity
        """
        query = text("""
        SELECT 
            me.name as entity_name,
            COUNT(DISTINCT es.comment_id) as mention_count,
            AVG(es.numeric_value) as avg_sentiment,
            MIN(es.numeric_value) as min_sentiment,
            MAX(es.numeric_value) as max_sentiment,
            STDDEV(es.numeric_value) as sentiment_stddev,
            SUM(c.likes) as total_likes
        FROM extracted_signals es
        JOIN comments c ON es.comment_id = c.id
        JOIN monitored_entities me ON es.entity_id = me.id
        WHERE es.entity_id = ANY(:entity_ids)
          AND es.signal_type = 'sentiment'
          AND es.numeric_value IS NOT NULL
          AND c.created_at BETWEEN :start AND :end
        GROUP BY me.name
        ORDER BY mention_count DESC
        """)
        
        # Convert UUIDs to strings for SQLite compatibility
        try:
            is_sqlite = self.session.bind.dialect.name == 'sqlite'
        except (AttributeError, TypeError):
            is_sqlite = False
        
        if is_sqlite:
            # SQLite doesn't support ANY() or STDDEV, use IN with parameterized query
            entity_ids_param = [str(eid).replace('-', '') for eid in entity_ids]
            # Build IN clause with placeholders
            entity_ids_str = ','.join([f"'{eid}'" for eid in entity_ids_param])
            # SQLite-compatible query without STDDEV (calculate manually if needed)
            query_str = f"""
            SELECT 
                me.name as entity_name,
                COUNT(DISTINCT es.comment_id) as mention_count,
                AVG(es.numeric_value) as avg_sentiment,
                MIN(es.numeric_value) as min_sentiment,
                MAX(es.numeric_value) as max_sentiment,
                0.0 as sentiment_stddev,
                SUM(c.likes) as total_likes
            FROM extracted_signals es
            JOIN comments c ON es.comment_id = c.id
            JOIN monitored_entities me ON es.entity_id = me.id
            WHERE REPLACE(es.entity_id, '-', '') IN ({entity_ids_str})
              AND es.signal_type = 'sentiment'
              AND es.numeric_value IS NOT NULL
              AND c.created_at BETWEEN :start AND :end
            GROUP BY me.name
            ORDER BY mention_count DESC
            """
            query = text(query_str)
            params = {
                "start": time_window[0],
                "end": time_window[1]
            }
            result = self.session.execute(query, params)
        else:
            entity_ids_param = [str(eid) for eid in entity_ids]
            result = self.session.execute(
                query,
                {
                    "entity_ids": entity_ids_param,
                    "start": time_window[0],
                    "end": time_window[1]
                }
            )
        
        df = pd.DataFrame(result.fetchall(), columns=result.keys())
        
        return df
    
    def get_sentiment_distribution(
        self,
        time_window: Tuple[datetime, datetime],
        entity_id: Optional[uuid.UUID] = None
    ) -> Dict[str, int]:
        """
        Get distribution of sentiment labels (positive/negative/neutral).
        
        Args:
            time_window: Tuple of (start_date, end_date)
            entity_id: Optional entity to filter by
            
        Returns:
            Dictionary with counts: {"positive": 100, "negative": 50, "neutral": 25}
        """
        query_str = """
        SELECT 
            es.value as sentiment_label,
            COUNT(*) as count
        FROM extracted_signals es
        JOIN comments c ON es.comment_id = c.id
        WHERE es.signal_type = 'sentiment'
          AND c.created_at BETWEEN :start AND :end
        """
        
        params = {"start": time_window[0], "end": time_window[1]}
        
        if entity_id:
            # Convert UUID to string for SQLite compatibility
            try:
                is_sqlite = self.session.bind.dialect.name == 'sqlite'
            except (AttributeError, TypeError):
                is_sqlite = False
            
            if is_sqlite:
                entity_id_param = str(entity_id).replace('-', '')
                query_str += " AND REPLACE(es.entity_id, '-', '') = :entity_id"
            else:
                entity_id_param = entity_id
                query_str += " AND es.entity_id = :entity_id"
            params["entity_id"] = entity_id_param
        
        query_str += " GROUP BY es.value"
        
        result = self.session.execute(text(query_str), params)
        
        distribution = {row.sentiment_label: row.count for row in result}
        
        return distribution
    
    def get_top_posts(
        self,
        start_date: datetime,
        end_date: datetime,
        limit: int = 10,
        platform: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get top posts by comment volume with sentiment analysis.
        
        Returns list of dicts with post performance metrics.
        """
        query = (
            self.session.query(
                Post.id,
                Post.platform,
                Post.url,
                Post.caption,
                func.count(Comment.id).label('comment_count'),
                func.sum(Comment.likes).label('total_likes'),
            )
            .join(Comment, Comment.post_id == Post.id)
            .filter(Comment.created_at.between(start_date, end_date))
            .group_by(Post.id, Post.platform, Post.url, Post.caption)
            .order_by(func.count(Comment.id).desc())
            .limit(limit)
        )
        
        if platform:
            query = query.filter(Post.platform == platform)
        
        # Get all monitored entities once for caption matching
        monitored_entities = self.session.query(MonitoredEntity).filter_by(is_active=True).all()
        
        results = []
        for row in query.all():
            # Get average sentiment for this post's comments
            sentiment_query = (
                self.session.query(func.avg(ExtractedSignal.numeric_value))
                .join(Comment, ExtractedSignal.comment_id == Comment.id)
                .filter(
                    Comment.post_id == row.id,
                    ExtractedSignal.signal_type == SignalType.SENTIMENT,
                    Comment.created_at.between(start_date, end_date)
                )
            )
            avg_sentiment = sentiment_query.scalar() or 0.0
            
            # FIX 1: Get top entity from POST CAPTION first (not from comment signals)
            # This ensures a post about "Meghan Markle" shows Meghan as top entity
            top_entity = None
            caption_lower = (row.caption or '').lower()
            
            # Check if any monitored entity appears in the post caption
            for entity in monitored_entities:
                names_to_check = [entity.name.lower()]
                if entity.aliases:
                    names_to_check.extend([alias.lower() for alias in entity.aliases])
                
                for name in names_to_check:
                    if name in caption_lower:
                        top_entity = entity.name
                        break
                if top_entity:
                    break
            
            # If no entity found in caption, fall back to most-mentioned in comments
            if not top_entity:
                top_entity_query = (
                    self.session.query(
                        MonitoredEntity.name,
                        func.count(ExtractedSignal.id).label('mention_count')
                    )
                    .join(ExtractedSignal, ExtractedSignal.entity_id == MonitoredEntity.id)
                    .join(Comment, ExtractedSignal.comment_id == Comment.id)
                    .filter(
                        Comment.post_id == row.id,
                        ExtractedSignal.signal_type == SignalType.SENTIMENT,
                        ExtractedSignal.entity_id.isnot(None),
                        Comment.created_at.between(start_date, end_date)
                    )
                    .group_by(MonitoredEntity.name)
                    .order_by(func.count(ExtractedSignal.id).desc())
                    .first()
                )
                top_entity = top_entity_query[0] if top_entity_query else None
            
            caption = row.caption
            if caption and len(caption) > 100:
                caption = caption[:100] + '...'
            
            results.append({
                'post_id': str(row.id),
                'platform': row.platform,
                'url': row.url,
                'caption': caption or '',
                'comment_count': row.comment_count,
                'total_likes': row.total_likes or 0,
                'avg_sentiment': round(float(avg_sentiment), 2),
                'top_entity': top_entity,
            })
        
        return results
    
    def get_post_sentiment_distribution(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Categorize posts by their average comment sentiment.
        
        Returns dict with counts and extreme examples.
        """
        # Get all posts with their average sentiment
        post_sentiments = (
            self.session.query(
                Post.id,
                Post.url,
                Post.caption,
                func.avg(ExtractedSignal.numeric_value).label('avg_sentiment'),
                func.count(Comment.id).label('comment_count')
            )
            .join(Comment, Comment.post_id == Post.id)
            .join(ExtractedSignal, ExtractedSignal.comment_id == Comment.id)
            .filter(
                Comment.created_at.between(start_date, end_date),
                ExtractedSignal.signal_type == SignalType.SENTIMENT
            )
            .group_by(Post.id, Post.url, Post.caption)
            .having(func.count(Comment.id) >= 5)  # Minimum 5 comments for validity
            .all()
        )
        
        positive = 0
        neutral = 0
        negative = 0
        most_positive = None
        most_negative = None
        
        for post in post_sentiments:
            sentiment = float(post.avg_sentiment) if post.avg_sentiment else 0.0
            
            if sentiment > 0.3:
                positive += 1
            elif sentiment < -0.3:
                negative += 1
            else:
                neutral += 1
            
            if most_positive is None or sentiment > float(most_positive['avg_sentiment']):
                caption = post.caption[:100] if post.caption else None
                most_positive = {
                    'post_id': str(post.id),
                    'url': post.url,
                    'caption': caption,
                    'avg_sentiment': round(sentiment, 2),
                    'comment_count': post.comment_count
                }
            
            if most_negative is None or sentiment < float(most_negative['avg_sentiment']):
                caption = post.caption[:100] if post.caption else None
                most_negative = {
                    'post_id': str(post.id),
                    'url': post.url,
                    'caption': caption,
                    'avg_sentiment': round(sentiment, 2),
                    'comment_count': post.comment_count
                }
        
        return {
            'positive_posts': positive,
            'neutral_posts': neutral,
            'negative_posts': negative,
            'total_posts': len(post_sentiments),
            'most_positive_post': most_positive,
            'most_negative_post': most_negative
        }
    
    def get_dynamic_entities(
        self,
        start_date: datetime,
        end_date: datetime,
        min_mentions: int = 10,
        platforms: Optional[List[str]] = None,
        limit: int = 50
    ) -> pd.DataFrame:
        """
        Get all entities (monitored + high-volume discovered) with min_mentions threshold.
        
        This provides a unified view for the current reporting period,
        treating high-volume discovered entities the same as monitored ones.
        
        Args:
            start_date: Start of time window
            end_date: End of time window
            min_mentions: Minimum mentions to include discovered entities
            platforms: Optional list of platforms to filter by
            limit: Maximum number of entities to return
            
        Returns:
            DataFrame with same structure as get_top_entities, including:
            - entity_id: UUID (None for discovered entities)
            - entity_name: Entity name
            - entity_type: Entity type
            - mention_count: Number of mentions in time window
            - avg_sentiment: Average sentiment score
            - total_likes: Sum of likes
            - weighted_sentiment: Like-weighted sentiment
            - is_monitored: Boolean flag (True for monitored, False for discovered)
        """
        time_window = (start_date, end_date)
        
        # Get monitored entities
        monitored_df = self.get_top_entities(
            time_window=time_window,
            platforms=platforms,
            limit=limit * 2  # Get more to merge with discovered
        )
        
        if len(monitored_df) > 0:
            monitored_df['is_monitored'] = True
        
        # Get discovered entities with enough mentions in the time period
        # For discovered entities, we need to count mentions by searching comment text
        # since they don't have entity_id links in ExtractedSignal
        all_discovered = self.session.query(DiscoveredEntity).filter(
            DiscoveredEntity.mention_count >= min_mentions
        ).limit(limit * 3).all()
        
        # FIX 3B: Filter garbage entities at query time
        # Blocklist matching enrichment.py and cleanup script
        BLOCKLIST = {
            'getty images', 'getty', 'swipe', 'universe', 'tap', 'link', 'bio',
            'comment', 'comments', 'like', 'share', 'follow', 'click',
            'harper', 'bazaar', 'vogue', 'elle', 'glamour', 'cosmopolitan',
            'photo', 'video', 'image', 'picture', 'story', 'stories',
            'instagram', 'facebook', 'twitter', 'tiktok', 'youtube',
            'today', 'tomorrow', 'yesterday', 'week', 'month', 'year',
            'love', 'hate', 'best', 'worst', 'amazing', 'beautiful',
            'images', 'see more', 'link in bio', 'linkinbio', 'more', 'magazine', 'mag',
            'omg', 'lol', 'wtf', 'idk', 'tbh', 'imo', 'imho', 'fyi', 'btw',
            'mexico', 'america', 'usa', 'uk', 'canada',
        }
        
        # Filter out garbage entities
        all_discovered = [
            d for d in all_discovered
            if d.name.lower().strip() not in BLOCKLIST
            and '■' not in d.name
            and '□' not in d.name
            and len(d.name) >= 2
            and any(c.isalpha() for c in d.name)
        ]
        
        discovered_results = []
        for discovered in all_discovered:
            entity_name = discovered.name
            
            # Count mentions in time period by searching comment text
            mention_query = (
                self.session.query(
                    func.count(Comment.id).label('mention_count'),
                    func.sum(Comment.likes).label('total_likes')
                )
                .join(Post, Comment.post_id == Post.id)
                .filter(
                    Comment.created_at.between(start_date, end_date),
                    Comment.text.ilike(f"%{entity_name}%")
                )
            )
            
            if platforms:
                mention_query = mention_query.filter(Post.platform.in_(platforms))
            
            mention_result = mention_query.first()
            if mention_result and mention_result.mention_count and mention_result.mention_count >= min_mentions:
                discovered_results.append({
                    'name': entity_name,
                    'entity_type': discovered.entity_type or 'unknown',
                    'mention_count': mention_result.mention_count,
                    'total_likes': mention_result.total_likes or 0
                })
        
        # Calculate sentiment for discovered entities
        discovered_entities = []
        monitored_names = set(monitored_df['entity_name'].str.lower()) if len(monitored_df) > 0 else set()
        
        for row in discovered_results:
            if isinstance(row, dict):
                entity_name = row['name']
                mention_count = row['mention_count']
                total_likes = row['total_likes']
                entity_type = row['entity_type']
            else:
                # Fallback for tuple/object format
                entity_name = row.name if hasattr(row, 'name') else row[0]
                mention_count = row.mention_count if hasattr(row, 'mention_count') else row[1]
                total_likes = row.total_likes if hasattr(row, 'total_likes') else row[2]
                entity_type = row.entity_type if hasattr(row, 'entity_type') else row[3]
            
            # Skip if already in monitored (monitored takes precedence)
            if entity_name.lower() in monitored_names:
                continue
            
            # Get sentiment for comments mentioning this discovered entity
            # Find comments where entity name appears in comment text
            # Then get average sentiment from those comments' sentiment signals
            mention_comment_ids = (
                self.session.query(Comment.id)
                .join(Post, Comment.post_id == Post.id)
                .filter(
                    Comment.created_at.between(start_date, end_date),
                    Comment.text.ilike(f"%{entity_name}%")
                )
            )
            
            if platforms:
                mention_comment_ids = mention_comment_ids.filter(Post.platform.in_(platforms))
            
            comment_id_list = [c.id for c in mention_comment_ids.all()]
            
            if not comment_id_list:
                avg_sentiment = 0.0
                weighted_sentiment = 0.0
            else:
                sentiment_result = (
                    self.session.query(
                        func.avg(ExtractedSignal.numeric_value).label('avg_sentiment'),
                        func.sum(ExtractedSignal.numeric_value * ExtractedSignal.weight_score).label('weighted_sum'),
                        func.sum(ExtractedSignal.weight_score).label('weight_sum')
                    )
                    .filter(
                        ExtractedSignal.comment_id.in_(comment_id_list),
                        ExtractedSignal.signal_type == SignalType.SENTIMENT,
                        ExtractedSignal.numeric_value.isnot(None)
                    )
                ).first()
            
            avg_sentiment = 0.0
            weighted_sentiment = 0.0
            
            if sentiment_result and sentiment_result.avg_sentiment:
                avg_sentiment = float(sentiment_result.avg_sentiment)
                if sentiment_result.weight_sum and sentiment_result.weight_sum > 0:
                    weighted_sentiment = float(sentiment_result.weighted_sum) / float(sentiment_result.weight_sum)
                else:
                    weighted_sentiment = avg_sentiment
            
            discovered_entities.append({
                'entity_id': None,  # No entity_id for discovered entities
                'entity_name': entity_name,
                'entity_type': entity_type or 'unknown',
                'mention_count': mention_count,
                'avg_sentiment': round(avg_sentiment, 3),
                'total_likes': total_likes or 0,
                'weighted_sentiment': round(weighted_sentiment, 3),
                'is_monitored': False
            })
            
            # Skip rest of loop if we've processed this entity
            continue
        
        # Combine monitored and discovered
        if len(monitored_df) > 0:
            all_entities = monitored_df.to_dict('records')
        else:
            all_entities = []
        
        all_entities.extend(discovered_entities)
        
        # Convert to DataFrame and sort by mention count
        if all_entities:
            result_df = pd.DataFrame(all_entities)
            result_df = result_df.sort_values('mention_count', ascending=False).head(limit)
            return result_df
        else:
            # Return empty DataFrame with correct columns
            return pd.DataFrame(columns=[
                'entity_id', 'entity_name', 'entity_type', 'mention_count',
                'avg_sentiment', 'total_likes', 'weighted_sentiment', 'is_monitored'
            ])

