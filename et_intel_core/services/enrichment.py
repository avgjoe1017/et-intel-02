"""
Enrichment service - extracts entities and scores sentiment.
"""

import uuid
from datetime import datetime
from typing import List, Optional, Dict
from sqlalchemy.orm import Session
from sqlalchemy import exists

from et_intel_core.models import (
    Comment,
    ExtractedSignal,
    DiscoveredEntity,
    MonitoredEntity,
    SignalType
)
from et_intel_core.nlp import EntityExtractor, SentimentProvider


class EnrichmentService:
    """
    Takes raw comments, produces signals.
    Separate from ingestion - can be run as batch job.
    
    Key features:
    - Idempotent: can re-run on same comments (updates existing signals)
    - Batch processing: commits every 50 comments
    - Entity discovery: tracks unknown entities
    - Like-weighted scoring: high-engagement comments matter more
    """
    
    def __init__(
        self,
        session: Session,
        extractor: EntityExtractor,
        sentiment_provider: SentimentProvider
    ):
        """
        Initialize enrichment service.
        
        Args:
            session: SQLAlchemy database session
            extractor: Entity extractor instance
            sentiment_provider: Sentiment scoring provider
        """
        self.session = session
        self.extractor = extractor
        self.sentiment_provider = sentiment_provider
    
    def enrich_comments(
        self,
        comment_ids: Optional[List[uuid.UUID]] = None,
        since: Optional[datetime] = None
    ) -> Dict[str, int]:
        """
        Enrich comments with entities + sentiment.
        Idempotent: can be re-run to update signals.
        
        Args:
            comment_ids: Specific comments to enrich (or None for all unprocessed)
            since: Only enrich comments created after this date
            
        Returns:
            Dictionary with enrichment statistics:
            - comments_processed: Number of comments enriched
            - signals_created: Number of new signals created
            - entities_discovered: Number of new entities discovered
        """
        stats = {
            "comments_processed": 0,
            "signals_created": 0,
            "entities_discovered": 0
        }
        
        # Query comments to process
        query = self.session.query(Comment)
        
        if comment_ids:
            query = query.filter(Comment.id.in_(comment_ids))
        elif since:
            query = query.filter(Comment.created_at >= since)
        else:
            # Default: only unprocessed comments (no signals yet)
            query = query.filter(
                ~exists().where(
                    ExtractedSignal.comment_id == Comment.id
                )
            )
        
        comments = query.all()
        
        for comment in comments:
            # Extract entities
            catalog_mentions, discovered = self.extractor.extract(
                comment.text,
                post_caption=comment.post.subject_line
            )
            
            # Track discovered entities
            for disc in discovered:
                self._track_discovered_entity(disc.name, disc.entity_type, comment.text)
                stats["entities_discovered"] += 1
            
            # Score sentiment
            sentiment_result = self.sentiment_provider.score(comment.text)
            
            # Calculate like-weighted score
            # Formula: 1.0 + (likes / 100)
            # Examples: 0 likes = 1.0, 100 likes = 2.0, 500 likes = 6.0
            weight_score = 1.0 + (comment.likes / 100.0)
            
            # Create general comment sentiment signal (no entity)
            self._create_signal(
                comment_id=comment.id,
                entity_id=None,
                signal_type=SignalType.SENTIMENT,
                value=self._sentiment_label(sentiment_result.score),
                numeric_value=sentiment_result.score,
                source_model=sentiment_result.source_model,
                confidence=sentiment_result.confidence,
                weight_score=weight_score
            )
            stats["signals_created"] += 1
            
            # Create entity-specific signals
            for entity_mention in catalog_mentions:
                # For MVP, use the general sentiment with entity association
                # In future: could do entity-targeted sentiment analysis
                self._create_signal(
                    comment_id=comment.id,
                    entity_id=entity_mention.entity_id,
                    signal_type=SignalType.SENTIMENT,
                    value=self._sentiment_label(sentiment_result.score),
                    numeric_value=sentiment_result.score,
                    source_model=sentiment_result.source_model,
                    confidence=entity_mention.confidence * sentiment_result.confidence,
                    weight_score=weight_score
                )
                stats["signals_created"] += 1
            
            stats["comments_processed"] += 1
            
            # Commit in batches
            if stats["comments_processed"] % 50 == 0:
                self.session.commit()
        
        # Final commit
        self.session.commit()
        return stats
    
    def _create_signal(self, **kwargs):
        """
        Create or update signal (idempotent).
        
        Checks for existing signal with same:
        - comment_id
        - entity_id
        - signal_type
        - source_model
        
        If exists, updates. If not, creates new.
        """
        # Check for existing signal
        existing = self.session.query(ExtractedSignal).filter(
            ExtractedSignal.comment_id == kwargs['comment_id'],
            ExtractedSignal.entity_id == kwargs.get('entity_id'),
            ExtractedSignal.signal_type == kwargs['signal_type'],
            ExtractedSignal.source_model == kwargs['source_model']
        ).first()
        
        if existing:
            # Update existing
            existing.value = kwargs['value']
            existing.numeric_value = kwargs.get('numeric_value')
            existing.confidence = kwargs['confidence']
            existing.weight_score = kwargs['weight_score']
            existing.created_at = datetime.utcnow()  # Update timestamp
        else:
            # Create new
            signal = ExtractedSignal(**kwargs, created_at=datetime.utcnow())
            self.session.add(signal)
    
    def _sentiment_label(self, score: float) -> str:
        """
        Convert numeric sentiment to human-readable label.
        
        Args:
            score: Sentiment score from -1.0 to 1.0
            
        Returns:
            "positive", "negative", or "neutral"
        """
        if score > 0.3:
            return "positive"
        elif score < -0.3:
            return "negative"
        else:
            return "neutral"
    
    def _track_discovered_entity(self, name: str, entity_type: str, context: str):
        """
        Track an entity that spaCy found but isn't in MonitoredEntity.
        
        Args:
            name: Entity name
            entity_type: Entity type from spaCy (PERSON, ORG, etc.)
            context: Comment text where entity was found
        """
        discovered = self.session.query(DiscoveredEntity).filter(
            DiscoveredEntity.name == name
        ).first()
        
        now = datetime.utcnow()
        
        if discovered:
            # Update existing
            discovered.last_seen_at = now
            discovered.mention_count += 1
            # Keep up to 10 sample mentions
            if len(discovered.sample_mentions) < 10:
                discovered.sample_mentions = discovered.sample_mentions + [context[:200]]
        else:
            # Create new
            discovered = DiscoveredEntity(
                name=name,
                entity_type=entity_type,
                first_seen_at=now,
                last_seen_at=now,
                mention_count=1,
                sample_mentions=[context[:200]]
            )
            self.session.add(discovered)

