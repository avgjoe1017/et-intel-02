"""
Narrative Generator - Uses LLM to generate contextual insights.

Takes analytics data and generates human-readable narrative summaries.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import os

from openai import OpenAI
from et_intel_core.config import settings


class NarrativeGenerator:
    """Generates narrative summaries using LLM."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize narrative generator.
        
        Args:
            api_key: OpenAI API key (uses settings if not provided)
        """
        api_key = api_key or settings.openai_api_key
        if not api_key or api_key == "your-openai-api-key-here":
            self.client = None
            self.enabled = False
        else:
            self.client = OpenAI(api_key=api_key)
            self.enabled = True
    
    def generate_velocity_narrative(
        self,
        velocity_data: Dict[str, Any],
        entity_name: str
    ) -> str:
        """
        Generate narrative explaining why sentiment changed.
        
        Args:
            velocity_data: Velocity alert data
            entity_name: Name of entity
            
        Returns:
            Narrative text explaining the change
        """
        if not self.enabled:
            return (
                f"{entity_name} experienced a {velocity_data.get('percent_change', 0):+.1f}% "
                f"sentiment shift from {velocity_data.get('previous_sentiment', 0):.2f} to "
                f"{velocity_data.get('recent_sentiment', 0):.2f}."
            )
        
        change_pct = velocity_data.get('percent_change', 0)
        previous = velocity_data.get('previous_sentiment', 0)
        recent = velocity_data.get('recent_sentiment', 0)
        
        # Determine clear direction language
        if change_pct > 0:
            if previous < -0.3 and recent > -0.3:
                direction_desc = "recovering from negative territory"
            elif recent > 0.3:
                direction_desc = "sentiment strongly positive"
            else:
                direction_desc = "sentiment improving"
        else:
            if previous > -0.3 and recent < -0.3:
                direction_desc = "turned negative"
            elif recent < -0.7:
                direction_desc = "sentiment crisis"
            else:
                direction_desc = "sentiment declining"
        
        prompt = f"""Analyze this sentiment velocity alert and provide a brief, professional explanation (2-3 sentences) of why this change likely occurred.

Entity: {entity_name}
Change: {change_pct:+.1f}% ({direction_desc})
Previous Sentiment: {previous:.2f}
Recent Sentiment: {recent:.2f}
Sample Size: {velocity_data.get('recent_sample_size', 0)} recent comments

Provide a data-driven explanation that would be useful for entertainment industry executives. Focus on likely causes (news events, social media discourse, content releases, etc.). Be concise and professional.

Use clear language: say "sentiment improving" not "negativity improving". Describe the direction of change clearly."""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an entertainment industry intelligence analyst. Provide concise, data-driven insights."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0.7
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            # Fallback to simple narrative
            return (
                f"{entity_name} experienced a {velocity_data.get('percent_change', 0):+.1f}% "
                f"sentiment shift from {velocity_data.get('previous_sentiment', 0):.2f} to "
                f"{velocity_data.get('recent_sentiment', 0):.2f}."
            )
    
    def generate_brief_summary(
        self,
        top_entities: List[Dict[str, Any]],
        velocity_alerts: List[Dict[str, Any]],
        platform_breakdown: List[Dict[str, Any]],
        timeframe: Dict[str, datetime]
    ) -> str:
        """
        Generate executive summary narrative for the entire brief.
        
        Args:
            top_entities: Top entities data
            velocity_alerts: Velocity alerts
            platform_breakdown: Platform metrics
            timeframe: Time window
            
        Returns:
            Executive summary narrative (3-4 sentences)
        """
        if not self.enabled:
            return self._generate_fallback_summary(top_entities, velocity_alerts)
        
        # Build context
        top_entity = top_entities[0] if top_entities else None
        critical_alert = next((a for a in velocity_alerts if abs(a.get('percent_change', 0)) > 50), None)
        
        prompt = f"""Generate a 3-4 sentence executive summary for an entertainment industry intelligence brief.

Time Period: {timeframe['start'].strftime('%B %d')} to {timeframe['end'].strftime('%B %d, %Y')}

Key Data:
- Top Entity: {top_entity['entity_name'] if top_entity else 'N/A'} ({top_entity['mention_count'] if top_entity else 0} mentions, {top_entity['avg_sentiment'] if top_entity else 0:+.2f} sentiment)
- Critical Alert: {critical_alert['entity_name'] if critical_alert else 'None'} ({critical_alert['percent_change'] if critical_alert else 0:+.1f}% change)
- Platform Performance: {', '.join([f"{p['platform']}: {p['avg_sentiment']:+.2f}" for p in platform_breakdown[:2]])}

STRICT RULES:
1. ONLY reference entities and statistics provided above
2. NEVER invent events, tours, albums, or news not mentioned in the data
3. NEVER speculate about causes unless directly evidenced by comment themes
4. Focus on WHAT the data shows, not WHY it might be happening

Write a professional, concise summary that highlights the most important insights. Focus on what executives need to know. Do NOT mention anything not directly supported by the data above."""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an entertainment industry intelligence analyst. Write executive summaries that are concise, data-driven, and actionable."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=250,
                temperature=0.7
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return self._generate_fallback_summary(top_entities, velocity_alerts)
    
    def _generate_fallback_summary(
        self,
        top_entities: List[Dict[str, Any]],
        velocity_alerts: List[Dict[str, Any]]
    ) -> str:
        """Generate fallback summary without LLM."""
        if not top_entities:
            return "No significant entity activity in this period."
        
        top = top_entities[0]
        narratives = [
            f"{top['entity_name']} dominated conversations with {top['mention_count']:,} mentions "
            f"and {'positive' if top['avg_sentiment'] > 0.3 else 'negative' if top['avg_sentiment'] < -0.3 else 'neutral'} sentiment."
        ]
        
        if velocity_alerts:
            alert = velocity_alerts[0]
            narratives.append(
                f"{alert.get('entity_name', 'An entity')} shows a critical sentiment shift "
                f"({alert.get('percent_change', 0):+.1f}%), indicating significant change in public perception."
            )
        
        return " ".join(narratives)

