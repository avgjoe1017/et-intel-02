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
    ReviewQueue,
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
            # Extract entities first (needed for enhanced analysis)
            catalog_mentions, discovered = self.extractor.extract(
                comment.text,
                post_caption=comment.post.caption or comment.post.subject_line or ""
            )
            
            # Track discovered entities from spaCy
            for disc in discovered:
                self._track_discovered_entity(disc.name, disc.entity_type, comment.text)
                stats["entities_discovered"] += 1
            
            # Get post caption for context
            post_caption = comment.post.caption or comment.post.subject_line or ""
            
            # Get ALL monitored entities as context (not just ones found in comment)
            # Let GPT determine which ones are actually relevant
            all_monitored_entities = self.session.query(MonitoredEntity).filter_by(is_active=True).all()
            monitored_entity_list = []
            for entity in all_monitored_entities:
                # Add disambiguation for common confusions
                entity_info = entity.name
                if "Justin" in entity.name and "Baldoni" in entity.name:
                    entity_info += " (the director, not Justin Bieber)"
                elif "Blake" in entity.name and "Lively" in entity.name:
                    entity_info += " (the actress, not Blake Shelton)"
                elif entity.aliases:
                    aliases_str = ", ".join(entity.aliases[:3])
                    entity_info += f" (aliases: {aliases_str})"
                monitored_entity_list.append(entity_info)
            
            # Calculate like-weighted score
            weight_score = 1.0 + (comment.likes / 100.0)
            
            # Use enhanced OpenAI provider if available, otherwise fallback
            if hasattr(self.sentiment_provider, 'analyze_comment'):
                # Enhanced multi-signal extraction
                # Pass monitored entities as context, not targets
                # GPT will determine which ones are actually mentioned
                analysis = self.sentiment_provider.analyze_comment(
                    comment_text=comment.text,
                    post_caption=post_caption,
                    comment_likes=comment.likes or 0,
                    monitored_entities=monitored_entity_list if monitored_entity_list else None
                )
                
                # Get confidence scores
                entity_confidence = analysis.get("entity_confidence", {})
                
                # Create entity-targeted sentiment signals (only if confidence >= 0.7)
                for entity_name_raw, score in analysis.get("entity_scores", {}).items():
                    # Strip disambiguation hints from entity name
                    entity_name = entity_name_raw.split(" (")[0].strip()
                    
                    # FIX 2: Validate entity name before processing
                    if not self._is_valid_entity_name(entity_name):
                        continue
                    
                    # Check confidence
                    confidence = entity_confidence.get(entity_name, 0.8)  # Default 0.8 if not provided
                    
                    if confidence < 0.7:
                        # Low confidence - queue for human review instead of creating signal
                        self._queue_for_review(
                            comment=comment,
                            entity_mention=entity_name,
                            confidence=confidence,
                            possible_entities=[entity_name],
                            reason=f"Low confidence ({confidence:.2f}) for entity assignment"
                        )
                        stats["queued_for_review"] = stats.get("queued_for_review", 0) + 1
                        continue
                    
                    # High confidence - create signal
                    entity = self._resolve_entity_by_name(entity_name)
                    if entity:
                        self._create_signal(
                            comment_id=comment.id,
                            entity_id=entity.id,
                            signal_type=SignalType.SENTIMENT,
                            value=self._sentiment_label(score),
                            numeric_value=float(score),
                            source_model=getattr(self.sentiment_provider, 'model', 'gpt-4o-mini'),
                            confidence=confidence,
                            weight_score=weight_score
                        )
                        stats["signals_created"] += 1
                
                # If no entity scores but we have catalog mentions, use general sentiment
                if not analysis.get("entity_scores") and catalog_mentions:
                    # Calculate average sentiment from entity scores or use stance
                    general_sentiment = 0.0
                    if analysis.get("stance") == "oppose":
                        general_sentiment = -0.5
                    elif analysis.get("stance") == "support":
                        general_sentiment = 0.5
                    
                    for entity_mention in catalog_mentions:
                        self._create_signal(
                            comment_id=comment.id,
                            entity_id=entity_mention.entity_id,
                            signal_type=SignalType.SENTIMENT,
                            value=self._sentiment_label(general_sentiment),
                            numeric_value=general_sentiment,
                            source_model=getattr(self.sentiment_provider, 'model', 'gpt-4o-mini'),
                            confidence=0.7,
                            weight_score=weight_score
                        )
                        stats["signals_created"] += 1
                
                # FIX 6: Emotion signals - per entity for entity-specific emotions
                # This allows queries like "what emotions are people expressing about Blake?"
                if analysis.get("emotion") and catalog_mentions:
                    for entity_mention in catalog_mentions:
                        self._create_signal(
                            comment_id=comment.id,
                            entity_id=entity_mention.entity_id,  # Link to entity!
                            signal_type=SignalType.EMOTION,
                            value=analysis["emotion"],
                            numeric_value=None,
                            source_model=getattr(self.sentiment_provider, 'model', 'gpt-4o-mini'),
                            confidence=0.8,
                            weight_score=weight_score
                        )
                        stats["signals_created"] += 1
                elif analysis.get("emotion"):
                    # Comment-level emotion if no specific entity mentioned
                    self._create_signal(
                        comment_id=comment.id,
                        entity_id=None,
                        signal_type=SignalType.EMOTION,
                        value=analysis["emotion"],
                        numeric_value=None,
                        source_model=getattr(self.sentiment_provider, 'model', 'gpt-4o-mini'),
                        confidence=0.8,
                        weight_score=weight_score
                    )
                    stats["signals_created"] += 1
                
                # FIX 7: Stance signals - DISABLED until GPT returns per-entity stances
                # Current issue: if comment mentions Blake and Ryan with different stances,
                # both get the same stance value. Need to update GPT prompt to return
                # entity_stances: {"Blake Lively": "oppose", "Ryan Reynolds": "support"}
                # For now, disable to prevent incorrect data
                # TODO: Implement entity_stances in GPT prompt and uncomment this
                # if analysis.get("entity_stances"):
                #     for entity_name, stance in analysis["entity_stances"].items():
                #         entity = self._resolve_entity_by_name(entity_name)
                #         if entity:
                #             self._create_signal(
                #                 comment_id=comment.id,
                #                 entity_id=entity.id,
                #                 signal_type=SignalType.STANCE,
                #                 value=stance,
                #                 numeric_value=None,
                #                 source_model=getattr(self.sentiment_provider, 'model', 'gpt-4o-mini'),
                #                 confidence=0.8,
                #                 weight_score=weight_score
                #             )
                #             stats["signals_created"] += 1
                
                # Topic signals
                for topic in analysis.get("topics", []):
                    self._create_signal(
                        comment_id=comment.id,
                        entity_id=None,
                        signal_type=SignalType.TOPIC,
                        value=topic,
                        numeric_value=None,
                        source_model=getattr(self.sentiment_provider, 'model', 'gpt-4o-mini'),
                        confidence=0.7,
                        weight_score=weight_score
                    )
                    stats["signals_created"] += 1
                
                # Toxicity signal
                if analysis.get("toxicity") is not None:
                    toxicity_score = float(analysis["toxicity"])
                    # Categorize toxicity level for value field
                    if toxicity_score >= 0.7:
                        toxicity_label = "high"
                    elif toxicity_score >= 0.4:
                        toxicity_label = "medium"
                    else:
                        toxicity_label = "low"
                    
                    self._create_signal(
                        comment_id=comment.id,
                        entity_id=None,
                        signal_type=SignalType.TOXICITY,
                        value=toxicity_label,
                        numeric_value=toxicity_score,
                        source_model=getattr(self.sentiment_provider, 'model', 'gpt-4o-mini'),
                        confidence=0.8,
                        weight_score=weight_score
                    )
                    stats["signals_created"] += 1
                
                # Sarcasm signal
                if analysis.get("sarcasm"):
                    self._create_signal(
                        comment_id=comment.id,
                        entity_id=None,
                        signal_type=SignalType.SARCASM,
                        value="sarcasm",
                        numeric_value=1.0,
                        source_model=getattr(self.sentiment_provider, 'model', 'gpt-4o-mini'),
                        confidence=0.7,
                        weight_score=weight_score
                    )
                    stats["signals_created"] += 1
                
                # Handle ambiguous mentions - queue for human review
                for ambiguous in analysis.get("ambiguous_mentions", []):
                    self._queue_for_review(
                        comment=comment,
                        entity_mention=ambiguous.get("name", ""),
                        confidence=ambiguous.get("confidence", 0.5),
                        possible_entities=ambiguous.get("possible_entities", []),
                        reason=ambiguous.get("reason", "Ambiguous entity mention")
                    )
                    stats["queued_for_review"] = stats.get("queued_for_review", 0) + 1
                
                # FIX 8: Track discovered entities, preventing double-counting
                # An entity can appear in both other_entities and entity_scores
                tracked_this_comment = set()
                
                # Track discovered entities from GPT "other_entities"
                for discovered_name in analysis.get("other_entities", []):
                    name_lower = discovered_name.lower().strip()
                    if name_lower not in tracked_this_comment:
                        self._track_discovered_entity(discovered_name, "PERSON", comment.text)
                        tracked_this_comment.add(name_lower)
                        stats["entities_discovered"] += 1
                
                # Also check entity_scores for entities not in our catalog (like Colleen Hoover)
                # These should be tracked as discovered entities
                for entity_name_raw in analysis.get("entity_scores", {}).keys():
                    # Strip disambiguation hints
                    entity_name = entity_name_raw.split(" (")[0].strip()
                    name_lower = entity_name.lower().strip()
                    
                    # Skip if already tracked in this comment
                    if name_lower not in tracked_this_comment:
                        # Check if this entity is in our catalog
                        entity = self._resolve_entity_by_name(entity_name)
                        if not entity:
                            # Not in catalog - track as discovered
                            self._track_discovered_entity(entity_name, "PERSON", comment.text)
                            tracked_this_comment.add(name_lower)
                            stats["entities_discovered"] += 1
                    
            else:
                # Fallback to legacy sentiment scoring
                sentiment_result = self.sentiment_provider.score(comment.text)
                
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
            ExtractedSignal.source_model == kwargs.get('source_model', 'unknown')
        ).first()
        
        if existing:
            # Update existing
            if 'value' in kwargs:
                existing.value = kwargs['value']
            if 'numeric_value' in kwargs:
                existing.numeric_value = kwargs['numeric_value']
            if 'confidence' in kwargs:
                existing.confidence = kwargs['confidence']
            if 'weight_score' in kwargs:
                existing.weight_score = kwargs['weight_score']
            existing.created_at = datetime.utcnow()  # Update timestamp
        else:
            # Create new
            signal = ExtractedSignal(**kwargs, created_at=datetime.utcnow())
            self.session.add(signal)
    
    def _resolve_entity_by_name(self, entity_name: str) -> Optional[MonitoredEntity]:
        """
        FIX 9: Resolve entity name to MonitoredEntity, checking aliases.
        
        This allows GPT to return "JLo" and have it match "Jennifer Lopez".
        Uses a cached lookup for performance with many entities.
        """
        # Build alias cache on first use
        if not hasattr(self, '_alias_cache') or self._alias_cache is None:
            self._build_alias_cache()
        
        # Lookup in cache (includes name, canonical_name, and all aliases)
        return self._alias_cache.get(entity_name.lower().strip())
    
    def _build_alias_cache(self):
        """Build lookup dict: alias -> entity for fast resolution."""
        self._alias_cache = {}
        for entity in self.session.query(MonitoredEntity).filter_by(is_active=True).all():
            # Add primary name
            self._alias_cache[entity.name.lower()] = entity
            
            # Add canonical name if present
            if entity.canonical_name:
                self._alias_cache[entity.canonical_name.lower()] = entity
            
            # Add all aliases
            for alias in (entity.aliases or []):
                self._alias_cache[alias.lower()] = entity
    
    def _get_entity_name(self, entity_id: uuid.UUID) -> Optional[str]:
        """Get entity name from ID."""
        entity = self.session.query(MonitoredEntity).filter_by(id=entity_id).first()
        return entity.name if entity else None
    
    def _sentiment_label(self, score: float) -> str:
        """
        Convert numeric sentiment to human-readable label.
        
        Args:
            score: Sentiment score from -1.0 to 1.0
            
        Returns:
            Human-readable sentiment label matching the 5-level scale
        """
        if score >= 0.7:
            return "Strongly Positive"
        elif score >= 0.3:
            return "Positive"
        elif score > -0.3:  # FIX 4: Use > not >= to ensure -0.3 is "Negative"
            return "Neutral"
        elif score > -0.7:
            return "Negative"
        else:
            return "Strongly Negative"
    
    def _track_discovered_entity(self, name: str, entity_type: str, context: str):
        """
        Track an entity that spaCy found but isn't in MonitoredEntity.
        
        Args:
            name: Entity name
            entity_type: Entity type from spaCy (PERSON, ORG, etc.)
            context: Comment text where entity was found
        """
        # Filter out invalid entities
        if not self._is_valid_discovered_entity(name, entity_type):
            return
        
        # Flush pending changes to ensure we see recently added entities
        self.session.flush()
        
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
            # Flush immediately to make it visible for subsequent queries in this batch
            self.session.flush()
    
    def _is_valid_entity_name(self, name: str) -> bool:
        """
        Validate entity name from GPT response before creating signals.
        Filters out rendering artifacts, emojis, and common non-entities.
        
        Args:
            name: Entity name to validate
            
        Returns:
            True if entity name is valid, False otherwise
        """
        import re
        
        if not name or len(name) < 2:
            return False
        
        # Filter rendering artifacts
        if '■' in name or '□' in name or '▪' in name:
            return False
        
        # Filter emoji-only strings
        emoji_pattern = re.compile(
            "["
            "\U0001F300-\U0001F9FF"  # Miscellaneous Symbols and Pictographs
            "\U00002600-\U000026FF"  # Miscellaneous Symbols
            "\U00002700-\U000027BF"  # Dingbats
            "\U0001F600-\U0001F64F"  # Emoticons
            "\U0001F680-\U0001F6FF"  # Transport and Map Symbols
            "\U0001F1E0-\U0001F1FF"  # Flags
            "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
            "]+"
        )
        if emoji_pattern.fullmatch(name.strip()):
            return False
        
        # Filter common non-entities
        garbage = {
            'omg', 'lol', 'wtf', 'idk', 'tbh', 'imo', 'imho', 'fyi', 'btw',
            'mexico', 'america', 'usa', 'uk', 'canada',  # Countries without context
            'today', 'tomorrow', 'yesterday', 'here', 'there',
            'love', 'hate', 'best', 'worst', 'amazing', 'beautiful',
            'photo', 'video', 'image', 'picture', 'story', 'stories'
        }
        if name.lower() in garbage:
            return False
        
        # Must be primarily alphabetic (at least 50% letters)
        alpha_chars = sum(1 for c in name if c.isalpha())
        if alpha_chars < len(name) * 0.5:
            return False
        
        return True
    
    def _is_valid_discovered_entity(self, name: str, entity_type: str) -> bool:
        """
        Filter out invalid discovered entities (emojis, single characters, etc.).
        
        Args:
            name: Entity name to validate
            entity_type: Entity type from spaCy
            
        Returns:
            True if entity should be tracked, False otherwise
        """
        import re
        
        # Filter out emojis and emoji-only strings
        # Emojis are typically in the range U+1F300-U+1F9FF, U+2600-U+26FF, U+2700-U+27BF
        emoji_pattern = re.compile(
            "["
            "\U0001F300-\U0001F9FF"  # Miscellaneous Symbols and Pictographs
            "\U00002600-\U000026FF"  # Miscellaneous Symbols
            "\U00002700-\U000027BF"  # Dingbats
            "\U0001F600-\U0001F64F"  # Emoticons
            "\U0001F680-\U0001F6FF"  # Transport and Map Symbols
            "\U0001F1E0-\U0001F1FF"  # Flags
            "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
            "]+"
        )
        
        # Check if name is only emojis
        if emoji_pattern.fullmatch(name.strip()):
            return False
        
        # Filter out single characters or very short names (unless they're acronyms)
        name_clean = name.strip()
        if len(name_clean) < 2:
            return False
        
        # Filter out names that are only punctuation or numbers
        if not re.search(r'[a-zA-Z]', name_clean):
            return False
        
        # Filter out common non-entity words (if they're being picked up)
        common_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be',
            'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
            'would', 'could', 'should', 'may', 'might', 'must', 'can'
        }
        if name_clean.lower() in common_words:
            return False
        
        # Comprehensive blocklist for discovered entities
        # From user requirements: filter caption boilerplate, magazine names, etc.
        DISCOVERED_ENTITY_BLOCKLIST = {
            # Caption boilerplate
            'getty images', 'getty', 'swipe', 'universe', 'tap', 'link', 'bio',
            'comment', 'comments', 'like', 'share', 'follow', 'click',
            
            # Partial magazine names (should be full name or nothing)
            'harper', 'bazaar', 'vogue', 'elle', 'glamour', 'cosmopolitan',
            
            # Common false positives
            'photo', 'video', 'image', 'picture', 'story', 'stories',
            'instagram', 'facebook', 'twitter', 'tiktok', 'youtube',
            
            # Generic words often misclassified
            'today', 'tomorrow', 'yesterday', 'week', 'month', 'year',
            'love', 'hate', 'best', 'worst', 'amazing', 'beautiful',
            
            # Additional caption boilerplate
            'images', 'see more', 'link in bio', 'linkinbio', 'link in description',
            'double tap', 'follow me', 'dm', 'dm me', 'highlight', 'highlights',
            'reels', 'reel', 'post', 'posts', 'feed', 'grid', 'save', 'bookmark',
            'tag', 'tags', 'hashtag', 'hashtags', 'ad', 'sponsored', 'paid',
            'collaboration', 'collab', 'partnership', 'partner', 'credit', 'credits',
            'photographer', 'caption', 'insta', 'ig', 'more', 'magazine', 'mag'
        }
        
        if name_clean.lower() in DISCOVERED_ENTITY_BLOCKLIST:
            return False
        
        # Filter out common caption phrases that contain spaces
        if ' ' in name_clean:
            caption_phrases = [
                'getty images', 'swipe to see', 'link in bio', 'see more',
                'double tap', 'follow me', 'dm me', 'link in description',
                'harper\'s bazaar', 'vanity fair', 'link in story', 'check story',
                'people magazine'
            ]
            if name_clean.lower() in caption_phrases:
                return False
        
        # Filter out emojis more thoroughly
        import re
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "]+"
        )
        if emoji_pattern.search(name):
            return False
        
        # Filter out rendering artifacts (■■ characters)
        if '■' in name or '□' in name:
            return False
        
        # Note: We don't filter common first names (like "Kate", "Harry") because:
        # - They might be valid (e.g., "Harry" = Prince Harry)
        # - Full names like "Kate Middleton" would be two words anyway
        # - mention_count will help surface the important ones
        
        return True
    
    def _queue_for_review(
        self,
        comment: Comment,
        entity_mention: str,
        confidence: float,
        possible_entities: List[str],
        reason: str
    ):
        """
        Queue an ambiguous entity mention for human review.
        
        Args:
            comment: The comment containing the ambiguous mention
            entity_mention: The ambiguous entity name (e.g., "Justin")
            confidence: GPT's confidence score (0.0-1.0)
            possible_entities: List of possible entity matches
            reason: Why it's ambiguous
        """
        # Check if already queued for this comment + mention
        existing = self.session.query(ReviewQueue).filter(
            ReviewQueue.comment_id == comment.id,
            ReviewQueue.entity_mention == entity_mention,
            ReviewQueue.reviewed == False
        ).first()
        
        if existing:
            # Update existing queue item
            existing.confidence = confidence
            existing.possible_entities = possible_entities
            existing.reason = reason
        else:
            # Create new queue item
            queue_item = ReviewQueue(
                comment_id=comment.id,
                entity_mention=entity_mention,
                context=comment.text,
                post_caption=comment.post.caption or comment.post.subject_line,
                confidence=confidence,
                possible_entities=possible_entities,
                reason=reason
            )
            self.session.add(queue_item)
        
        self.session.flush()

