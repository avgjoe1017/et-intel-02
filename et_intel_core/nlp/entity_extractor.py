"""
Entity extraction using spaCy + custom catalog matching.
"""

import uuid
from dataclasses import dataclass
from typing import List, Tuple, Optional
import spacy
from spacy.language import Language

from et_intel_core.models import MonitoredEntity


@dataclass
class EntityMention:
    """Extracted entity mention with confidence."""
    entity_id: uuid.UUID
    mention_text: str
    confidence: float


@dataclass
class DiscoveredEntityMention:
    """Entity found by spaCy but not in catalog."""
    name: str
    entity_type: str  # PERSON, ORG, etc.
    confidence: float


class EntityExtractor:
    """
    Pure function: takes text, returns entities.
    No database coupling, easily testable.
    
    Strategy:
    1. Check catalog first (fast exact/alias matching)
    2. Use spaCy NER for discovery (people/orgs not in catalog)
    """
    
    def __init__(self, entity_catalog: List[MonitoredEntity], nlp: Optional[Language] = None):
        """
        Initialize entity extractor.
        
        Args:
            entity_catalog: List of monitored entities to match against
            nlp: Optional spaCy language model (loads en_core_web_sm if None)
        """
        self.catalog = entity_catalog
        self.nlp = nlp or spacy.load("en_core_web_sm")
        
        # Build lookup index for fast matching
        self._build_lookup_index()
    
    def _build_lookup_index(self):
        """Build lowercase lookup index for catalog matching."""
        self.name_to_entity = {}
        
        for entity in self.catalog:
            # Add canonical name
            self.name_to_entity[entity.name.lower()] = entity
            
            # Add aliases
            for alias in entity.aliases:
                self.name_to_entity[alias.lower()] = entity
    
    def extract(
        self, 
        text: str, 
        post_caption: Optional[str] = None
    ) -> Tuple[List[EntityMention], List[DiscoveredEntityMention]]:
        """
        Extract entities from comment text.
        
        Args:
            text: Comment text to analyze
            post_caption: Optional post caption for additional context
            
        Returns:
            Tuple of (catalog_mentions, discovered_mentions)
            - catalog_mentions: Entities found in our catalog
            - discovered_mentions: Entities found by spaCy but not in catalog
        """
        catalog_mentions = []
        discovered_mentions = []
        
        # Combine text and caption for analysis
        full_text = text
        if post_caption:
            full_text = f"{post_caption} {text}"
        
        text_lower = full_text.lower()
        
        # 1. Check catalog (fast exact/alias matching)
        for name_lower, entity in self.name_to_entity.items():
            if name_lower in text_lower:
                # Check if already found (avoid duplicates from aliases)
                if not any(m.entity_id == entity.id for m in catalog_mentions):
                    catalog_mentions.append(EntityMention(
                        entity_id=entity.id,
                        mention_text=name_lower,
                        confidence=1.0 if name_lower == entity.name.lower() else 0.9
                    ))
        
        # 2. spaCy NER for discovery (people/orgs not in catalog)
        doc = self.nlp(full_text)
        for ent in doc.ents:
            if ent.label_ in ["PERSON", "ORG"]:
                # Check if already found via catalog
                if not any(m.mention_text.lower() == ent.text.lower() for m in catalog_mentions):
                    # New entity discovered
                    discovered_mentions.append(DiscoveredEntityMention(
                        name=ent.text,
                        entity_type=ent.label_,
                        confidence=0.7  # spaCy confidence
                    ))
        
        return catalog_mentions, discovered_mentions
    
    def extract_catalog_only(self, text: str, post_caption: Optional[str] = None) -> List[EntityMention]:
        """
        Extract only catalog entities (skip discovery).
        Useful when you don't want to track discovered entities.
        
        Args:
            text: Comment text to analyze
            post_caption: Optional post caption for context
            
        Returns:
            List of EntityMention objects from catalog
        """
        catalog_mentions, _ = self.extract(text, post_caption)
        return catalog_mentions

