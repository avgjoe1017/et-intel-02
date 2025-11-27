"""
Entity extraction using spaCy + custom catalog matching.
"""

import uuid
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict, Set
from collections import defaultdict
import re
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
        self.name_to_entity: Dict[str, MonitoredEntity] = {}
        self.entity_metadata: Dict[str, dict] = {}
        first_name_map: Dict[str, List[MonitoredEntity]] = defaultdict(list)
        last_name_map: Dict[str, List[MonitoredEntity]] = defaultdict(list)
        
        for entity in self.catalog:
            canonical = entity.name.strip()
            canonical_lower = canonical.lower()
            aliases = [alias.strip().lower() for alias in (entity.aliases or []) if alias]
            tokens = canonical_lower.split()
            first_name = tokens[0] if tokens else None
            last_name = tokens[-1] if len(tokens) > 1 else None
            
            self.entity_metadata[str(entity.id)] = {
                "entity": entity,
                "canonical": canonical_lower,
                "aliases": aliases,
                "first": first_name,
                "last": last_name,
            }
            
            if canonical_lower:
                self.name_to_entity[canonical_lower] = entity
            for alias in aliases:
                self.name_to_entity[alias] = entity
            
            if first_name:
                first_name_map[first_name].append(entity)
            if last_name:
                last_name_map[last_name].append(entity)
        
        self.unique_first_names: Set[str] = {
            name for name, ents in first_name_map.items() if len(ents) == 1
        }
        self.unique_last_names: Set[str] = {
            name for name, ents in last_name_map.items() if len(ents) == 1
        }
    
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
        catalog_mentions: List[EntityMention] = []
        discovered_mentions = []
        
        # Use caption for context but only extract entities from comment text
        comment_text_lower = text.lower()
        caption_lower = post_caption.lower() if post_caption else ""
        context_entities = self._get_context_entities(caption_lower)
        
        # Combine for spaCy analysis (for pronoun resolution) but don't use for entity matching
        full_text = text
        if post_caption:
            full_text = f"{post_caption} {text}"
        
        # 1. Check catalog (fast exact/alias matching) - ONLY in comment text
        for name_lower, entity in self.name_to_entity.items():
            if name_lower in comment_text_lower:  # Only check comment text, not caption
                # Check if already found (avoid duplicates from aliases)
                if not any(m.entity_id == entity.id for m in catalog_mentions):
                    catalog_mentions.append(EntityMention(
                        entity_id=entity.id,
                        mention_text=name_lower,
                        confidence=1.0 if name_lower == entity.name.lower() else 0.9
                    ))
        
        catalog_mentions = self._match_partial_names(
            comment_text_lower,  # Only match in comment text
            catalog_mentions,
            context_entities  # But use caption for context
        )
        
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
    
    def _get_context_entities(self, caption_lower: str) -> Set[str]:
        """Return entity IDs referenced in the caption."""
        context_ids: Set[str] = set()
        if not caption_lower:
            return context_ids
        
        for entity_id, meta in self.entity_metadata.items():
            names_to_check = [meta["canonical"], *(meta["aliases"] or [])]
            for name in names_to_check:
                if name and name in caption_lower:
                    context_ids.add(entity_id)
                    break
        return context_ids
    
    def _match_partial_names(
        self,
        text_lower: str,
        catalog_mentions: List[EntityMention],
        context_entities: Set[str]
    ) -> List[EntityMention]:
        """Match first/last names and pronouns using context heuristics."""
        matched_ids = {str(m.entity_id) for m in catalog_mentions}
        tokens = set(re.findall(r"\b[a-zA-Z']+\b", text_lower))
        pronouns = {"she", "her", "hers", "he", "him", "his"}
        
        for entity_id, meta in self.entity_metadata.items():
            if entity_id in matched_ids:
                continue
            
            entity = meta["entity"]
            first = meta["first"]
            last = meta["last"]
            added = False
            
            def add_mention(confidence: float, mention_text: str):
                catalog_mentions.append(EntityMention(
                    entity_id=entity.id,
                    mention_text=mention_text,
                    confidence=confidence
                ))
                matched_ids.add(entity_id)
            
            if first and first in tokens:
                if first in self.unique_first_names or entity_id in context_entities:
                    add_mention(0.75 if entity_id in context_entities else 0.65, first)
                    added = True
            
            if not added and last and last in tokens:
                if last in self.unique_last_names or entity_id in context_entities:
                    add_mention(0.7 if entity_id in context_entities else 0.6, last)
                    added = True
            
            if not added and entity_id in context_entities:
                if tokens & pronouns:
                    add_mention(0.45, "pronoun")
                    added = True
        
        return catalog_mentions

