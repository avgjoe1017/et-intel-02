"""
Brief Builder - Composes analytics results into brief structure.

Separates computation from presentation - pure data assembly.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime
import pandas as pd
import uuid
import json

from et_intel_core.analytics import AnalyticsService
from et_intel_core.reporting.narrative_generator import NarrativeGenerator

# Scale limits for report generation
TOP_ENTITIES_DETAILED_NARRATIVE = 3  # Only write detailed context for top 3
TOP_ENTITIES_TABLE = 10              # Show top 10 in main table
TOP_ENTITIES_CHART = 7               # Plot top 7 in trend chart
MAX_VELOCITY_ALERTS = 8              # Show up to 8 alerts (if >30% change)
MAX_DISCOVERED_ENTITIES = 10         # Show top 10 discovered entities


@dataclass
class BriefSection:
    """One section of the intelligence brief."""
    title: str
    items: List[Dict[str, Any]] = field(default_factory=list)
    summary: Optional[str] = None


@dataclass
class IntelligenceBriefData:
    """
    Pure data structure for intelligence briefs.
    
    No presentation logic here - can be rendered as PDF, Slack, email, dashboard.
    """
    timeframe: Dict[str, datetime]
    topline_summary: Dict[str, Any]
    top_entities: BriefSection
    velocity_alerts: BriefSection
    discovered_entities: BriefSection
    platform_breakdown: BriefSection
    sentiment_distribution: Dict[str, Any]
    contextual_narrative: str
    entity_comparison: BriefSection
    what_changed: BriefSection
    key_risks: BriefSection
    entity_micro_insights: Dict[str, str]
    cross_platform_deltas: BriefSection
    storylines: BriefSection
    risk_signals: BriefSection
    metadata: Dict[str, Any]
    emotion_analysis: BriefSection = field(default_factory=lambda: BriefSection(title="Emotion Analysis", items=[]))
    topic_clusters: BriefSection = field(default_factory=lambda: BriefSection(title="Topic Clusters", items=[]))
    toxicity_alerts: BriefSection = field(default_factory=lambda: BriefSection(title="Toxicity Alerts", items=[]))
    stance_summary: BriefSection = field(default_factory=lambda: BriefSection(title="Stance Summary", items=[]))
    post_performance: BriefSection = field(default_factory=lambda: BriefSection(title="Post Performance", items=[]))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert brief data to dictionary for JSON serialization."""
        def serialize_value(value):
            if isinstance(value, datetime):
                return value.isoformat()
            elif isinstance(value, uuid.UUID):
                return str(value)
            elif isinstance(value, dict):
                return {k: serialize_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [serialize_value(item) for item in value]
            else:
                return value
        
        result = {}
        for key, value in self.__dict__.items():
            if isinstance(value, BriefSection):
                result[key] = {
                    'title': value.title,
                    'items': [serialize_value(item) for item in value.items],
                    'summary': value.summary
                }
            elif key == 'sentiment_distribution' and isinstance(value, dict):
                result[key] = serialize_value(value)
            elif key == 'contextual_narrative' and isinstance(value, str):
                result[key] = value
            else:
                result[key] = serialize_value(value)
        return result


class BriefBuilder:
    """
    Composes analytics results into brief structure.
    
    No presentation logic - just data assembly.
    """
    
    def __init__(self, analytics: AnalyticsService, narrative_generator: Optional[NarrativeGenerator] = None):
        self.analytics = analytics
        self.narrative = narrative_generator or NarrativeGenerator()
    
    def build(
        self,
        start: datetime,
        end: datetime,
        platforms: Optional[List[str]] = None,
        focus_entities: Optional[List[uuid.UUID]] = None,
        top_entities_limit: int = 20
    ) -> IntelligenceBriefData:
        """
        Build intelligence brief from analytics.
        
        Args:
            start: Start of time window
            end: End of time window
            platforms: Optional list of platforms to filter
            focus_entities: Optional list of entity IDs to focus on
            top_entities_limit: Maximum number of top entities to include
            
        Returns:
            IntelligenceBriefData with all sections populated
        """
        time_window = (start, end)
        
        # Compute all metrics using dynamic entities (monitored + high-volume discovered)
        # This includes any entity with 10+ mentions, not just pre-monitored ones
        top_entities_df = self.analytics.get_dynamic_entities(
            start_date=start,
            end_date=end,
            min_mentions=10,
            platforms=platforms,
            limit=TOP_ENTITIES_TABLE  # Use scale limit
        )
        
        # Get total comment count
        total_comments = self.analytics.get_comment_count(time_window)
        
        # Velocity checks for top entities
        velocity_alerts = []
        if len(top_entities_df) > 0:
            # Get entity IDs from top entities
            # We need to query the database to get entity IDs from names
            from et_intel_core.models import MonitoredEntity
            from et_intel_core.db import get_session
            
            session = get_session()
            try:
                entity_ids_to_check = []
                entity_name_map = {}  # Map entity_id to name
                
                for _, row in top_entities_df.head(10).iterrows():
                    # Only check velocity for monitored entities (discovered entities don't have entity_id)
                    entity_id = row.get('entity_id')
                    entity_name = row.get('entity_name', 'Unknown')
                    
                    # Skip if entity_id is None (discovered entities)
                    if entity_id and pd.notna(entity_id):
                        entity_ids_to_check.append(uuid.UUID(str(entity_id)))
                        entity_name_map[uuid.UUID(str(entity_id))] = entity_name
                    else:
                        # For discovered entities, try to find if they're now monitored
                        entity = session.query(MonitoredEntity).filter_by(
                            name=entity_name
                        ).first()
                        if entity:
                            entity_ids_to_check.append(entity.id)
                            entity_name_map[entity.id] = entity_name
                
                # Check velocity for each
                for entity_id in entity_ids_to_check:
                    velocity = self.analytics.compute_velocity(entity_id, window_hours=72)
                    if velocity and not velocity.get('error') and velocity.get('alert'):
                        # Add entity name to velocity data
                        velocity['entity_name'] = entity_name_map.get(entity_id, 'Unknown')
                        velocity_alerts.append(velocity)
                
                # Sort by absolute change (biggest swings first) and limit
                velocity_alerts.sort(key=lambda x: abs(x.get('percent_change', 0)), reverse=True)
                velocity_alerts = velocity_alerts[:MAX_VELOCITY_ALERTS]
            finally:
                session.close()
        
        # Count critical alerts (>50% change)
        critical_alerts = len([
            v for v in velocity_alerts 
            if abs(v.get('percent_change', 0)) > 50
        ])
        
        # Get discovered entities (with scale limit)
        discovered_df = self.analytics.get_discovered_entities(
            min_mentions=10,  # Increased threshold for scale
            reviewed=False,
            limit=MAX_DISCOVERED_ENTITIES
        )
        
        # Get platform breakdown
        platform_breakdown = self._get_platform_breakdown(time_window, platforms)
        
        # Get sentiment distribution
        sentiment_dist = self._get_sentiment_distribution(time_window, platforms)
        
        # Generate contextual narrative (with LLM if available) - only top 3 entities
        contextual_narrative = self._generate_contextual_narrative(
            top_entities_df.head(TOP_ENTITIES_DETAILED_NARRATIVE),  # Only top 3 for narrative
            velocity_alerts, 
            platform_breakdown, 
            time_window
        )
        
        # Generate velocity narratives (LLM explanations for each alert)
        velocity_narratives = {}
        for alert in velocity_alerts:
            entity_name = alert.get('entity_name', 'Unknown')
            velocity_narratives[entity_name] = self.narrative.generate_velocity_narrative(
                alert, entity_name
            )
        
        # Get entity comparison (week-over-week changes)
        entity_comparison = self._get_entity_comparison(time_window, top_entities_df)
        
        # Get "What Changed This Week" section
        what_changed = self._get_what_changed(time_window, top_entities_df, velocity_alerts)
        
        # Get cross-platform deltas
        cross_platform_deltas = self._get_cross_platform_deltas(time_window, top_entities_df)
        
        # Generate key risks/watchouts
        key_risks = self._generate_key_risks(velocity_alerts, top_entities_df, platform_breakdown)
        
        # Generate micro-insights per entity
        entity_micro_insights = self._generate_entity_micro_insights(top_entities_df, velocity_alerts)
        
        # Generate new signal type sections
        emotion_analysis = self._get_emotion_analysis(time_window, top_entities_df)
        topic_clusters = self._get_topic_clusters(time_window)
        toxicity_alerts = self._get_toxicity_alerts(time_window)
        stance_summary = self._get_stance_summary(time_window, top_entities_df)
        
        # Generate post performance section
        post_performance = self._get_post_performance(time_window)
        
        # Assemble brief
        return IntelligenceBriefData(
            timeframe={'start': start, 'end': end},
            topline_summary={
                'total_comments': total_comments,
                'total_entities': len(top_entities_df),
                'critical_alerts': critical_alerts,
                'velocity_alerts_count': len(velocity_alerts)
            },
            top_entities=BriefSection(
                title="Top Entities by Volume",
                items=top_entities_df.head(TOP_ENTITIES_TABLE).to_dict('records') if len(top_entities_df) > 0 else [],  # Limit to top 10
                summary=self._summarize_top_entities(top_entities_df)
            ),
            velocity_alerts=BriefSection(
                title="Sentiment Velocity Alerts",
                items=[
                    {
                        **alert,
                        'narrative': velocity_narratives.get(alert.get('entity_name', 'Unknown'), '')
                    }
                    for alert in velocity_alerts
                ],
                summary=f"{len(velocity_alerts)} entities with significant sentiment shifts (30%+ change in 72hrs)"
            ),
            discovered_entities=BriefSection(
                title="Discovered Entities",
                items=discovered_df.to_dict('records') if len(discovered_df) > 0 else [],
                summary=f"{len(discovered_df)} new entities discovered by NLP (not yet in monitoring)"
            ),
            platform_breakdown=BriefSection(
                title="Platform Breakdown",
                items=platform_breakdown,
                summary="Comment volume and sentiment by platform"
            ),
            sentiment_distribution=sentiment_dist,
            contextual_narrative=contextual_narrative,
            entity_comparison=entity_comparison,
            what_changed=what_changed,
            key_risks=key_risks,
            entity_micro_insights=entity_micro_insights,
            cross_platform_deltas=cross_platform_deltas,
            storylines=self._detect_storylines(time_window, top_entities_df),
            risk_signals=BriefSection(
                title="Risk Signals",
                items=[],  # TODO: Implement risk detection in future
                summary="Risk signal detection not yet implemented"
            ),
            emotion_analysis=emotion_analysis,
            topic_clusters=topic_clusters,
            toxicity_alerts=toxicity_alerts,
            stance_summary=stance_summary,
            post_performance=post_performance,
            metadata={
                'generated_at': datetime.utcnow(),
                'platforms': platforms or ['all'],
                'focus_entities': [str(eid) for eid in (focus_entities or [])]
            }
        )
    
    def _summarize_top_entities(self, df: pd.DataFrame) -> str:
        """Generate executive summary text for top entities."""
        if len(df) == 0:
            return "No significant entity activity in this period."
        
        top = df.iloc[0]
        sentiment_desc = "positive" if top['avg_sentiment'] > 0.3 else "negative" if top['avg_sentiment'] < -0.3 else "neutral"
        
        return (
            f"{top['entity_name']} dominated conversations with "
            f"{int(top['mention_count']):,} mentions and {sentiment_desc} sentiment "
            f"({top['avg_sentiment']:+.2f})."
        )
    
    def _get_platform_breakdown(
        self,
        time_window: tuple[datetime, datetime],
        platforms: Optional[List[str]]
    ) -> List[Dict[str, Any]]:
        """Get comment volume and sentiment by platform."""
        from et_intel_core.models import Post, Comment, ExtractedSignal
        from et_intel_core.models.enums import SignalType
        from sqlalchemy import func
        
        session = self.analytics.session
        
        query = session.query(
            Post.platform,
            func.count(func.distinct(Comment.id)).label('comment_count'),
            func.avg(ExtractedSignal.numeric_value).label('avg_sentiment'),
            func.sum(Comment.likes).label('total_likes')
        ).join(
            Comment, Post.id == Comment.post_id
        ).join(
            ExtractedSignal, Comment.id == ExtractedSignal.comment_id
        ).filter(
            Comment.created_at.between(time_window[0], time_window[1]),
            ExtractedSignal.signal_type == SignalType.SENTIMENT,
            ExtractedSignal.numeric_value.isnot(None)
        )
        
        if platforms:
            query = query.filter(Post.platform.in_(platforms))
        
        results = query.group_by(Post.platform).all()
        
        return [
            {
                'platform': row.platform,
                'comment_count': int(row.comment_count),
                'avg_sentiment': float(row.avg_sentiment or 0.0),
                'total_likes': int(row.total_likes or 0)
            }
            for row in results
        ]
    
    def _get_sentiment_distribution(
        self,
        time_window: tuple[datetime, datetime],
        platforms: Optional[List[str]]
    ) -> Dict[str, Any]:
        """Get sentiment distribution (positive/negative/neutral counts)."""
        from et_intel_core.models import Comment, ExtractedSignal, Post
        from et_intel_core.models.enums import SignalType
        from sqlalchemy import func, case
        
        session = self.analytics.session
        
        query = session.query(
            func.count(
                case(
                    (ExtractedSignal.numeric_value > 0.3, 1),
                    else_=None
                )
            ).label('positive'),
            func.count(
                case(
                    (ExtractedSignal.numeric_value < -0.3, 1),
                    else_=None
                )
            ).label('negative'),
            func.count(
                case(
                    ((ExtractedSignal.numeric_value >= -0.3) & 
                     (ExtractedSignal.numeric_value <= 0.3), 1),
                    else_=None
                )
            ).label('neutral')
        ).join(
            Comment, ExtractedSignal.comment_id == Comment.id
        ).join(
            Post, Comment.post_id == Post.id
        ).filter(
            Comment.created_at.between(time_window[0], time_window[1]),
            ExtractedSignal.signal_type == SignalType.SENTIMENT,
            ExtractedSignal.numeric_value.isnot(None)
        )
        
        if platforms:
            query = query.filter(Post.platform.in_(platforms))
        
        result = query.first()
        
        total = (result.positive or 0) + (result.negative or 0) + (result.neutral or 0)
        
        return {
            'positive': int(result.positive or 0),
            'negative': int(result.negative or 0),
            'neutral': int(result.neutral or 0),
            'total': total,
            'positive_pct': round((result.positive or 0) / total * 100, 1) if total > 0 else 0,
            'negative_pct': round((result.negative or 0) / total * 100, 1) if total > 0 else 0,
            'neutral_pct': round((result.neutral or 0) / total * 100, 1) if total > 0 else 0
        }
    
    def _format_comment_sample(self, comment: Dict[str, Any]) -> str:
        """Format comment text for grounding LLM narratives."""
        text = (comment.get("text") or "").strip().replace("\n", " ")
        if not text:
            return ""
        if len(text) > 160:
            text = text[:157] + "..."
        likes = comment.get("likes", 0) or 0
        return f"{likes:,} likes · {text}"
    
    def _generate_contextual_narrative(
        self,
        top_entities_df: pd.DataFrame,
        velocity_alerts: List[Dict[str, Any]],
        platform_breakdown: List[Dict[str, Any]],
        time_window: tuple[datetime, datetime]
    ) -> str:
        """
        Generate contextual narrative using LLM if available.
        
        Only uses top 3 entities for detailed narrative (scale optimization).
        """
        if len(top_entities_df) == 0:
            return "No significant entity activity in this period."
        
        # Build context from top entities (already limited to top 3)
        context = []
        for _, row in top_entities_df.iterrows():
            entity_name = row['entity_name']
            entity_id = row.get('entity_id')
            
            # Get velocity for this entity if available
            velocity = None
            for alert in velocity_alerts:
                if alert.get('entity_name') == entity_name:
                    velocity = alert.get('percent_change', 0)
                    break
            
            sample_comments = []
            if entity_id:
                try:
                    sample_comments = self.analytics.get_top_comments_for_entity(
                        uuid.UUID(str(entity_id)),
                        limit=3
                    )
                except Exception:
                    sample_comments = []
            formatted_samples = [
                self._format_comment_sample(comment)
                for comment in sample_comments
                if comment.get("text")
            ]
            
            context.append({
                "name": entity_name,
                "mentions": int(row['mention_count']),
                "sentiment": float(row['avg_sentiment']),
                "velocity": velocity,
                "platform_split": platform_breakdown,  # Overall platform data
                "sample_comments": formatted_samples
            })
        
        # Use LLM if available
        if self.narrative.enabled and hasattr(self.narrative, 'client') and self.narrative.client:
            # Build prompt for GPT-4o-mini
            context_lines = []
            for entry in context:
                lines = [
                    f"- {entry['name']}: {entry['mentions']} mentions, sentiment {entry['sentiment']:+.2f}"
                ]
                if entry["velocity"]:
                    lines.append(f"  Velocity: {entry['velocity']:+.1f}% change")
                if entry["sample_comments"]:
                    lines.append("  Representative comments:")
                    for comment in entry["sample_comments"]:
                        lines.append(f"    • {comment}")
                context_lines.append("\n".join(lines))
            prompt_context = "\n".join(context_lines)
            
            prompt = f"""Use the following entity summaries and representative comments to write a 3-4 sentence intelligence brief.

Data:
{prompt_context}

STRICT RULES:
1. ONLY reference entities and statistics provided above
2. NEVER invent events, tours, albums, news, or announcements not mentioned in the data
3. NEVER speculate about causes unless directly evidenced by comment themes
4. Keep to 2-3 sentences per major entity
5. Focus on WHAT the data shows, not WHY it might be happening

Do NOT mention anything not directly supported by the data above. Be factual and data-driven."""
            
            try:
                response = self.narrative.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are an entertainment industry intelligence analyst. Write concise, factual summaries."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=300,
                    temperature=0.7
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                # Fallback to existing method
                pass
        
        # Fallback to existing narrative generator
        top_entities_list = top_entities_df.to_dict('records')
        narrative = self.narrative.generate_brief_summary(
            top_entities_list,
            velocity_alerts,
            platform_breakdown,
            {'start': time_window[0], 'end': time_window[1]}
        )
        
        return narrative
    
    def _get_entity_comparison(
        self,
        time_window: tuple[datetime, datetime],
        top_entities_df: pd.DataFrame
    ) -> BriefSection:
        """Get entity comparison showing week-over-week changes."""
        # For now, return a placeholder
        # In a full implementation, we'd compare current week to previous week
        if len(top_entities_df) == 0:
            return BriefSection(
                title="Entity Comparison",
                items=[],
                summary="No comparison data available"
            )
        
        # Simplified: show top 5 entities with their sentiment trends
        comparison_items = []
        for _, row in top_entities_df.head(5).iterrows():
            comparison_items.append({
                'entity_name': row['entity_name'],
                'current_sentiment': row['avg_sentiment'],
                'mention_count': int(row['mention_count']),
                'trend': 'rising' if row['avg_sentiment'] > 0.3 else 'falling' if row['avg_sentiment'] < -0.3 else 'stable'
            })
        
        return BriefSection(
            title="Entity Comparison",
            items=comparison_items,
            summary="Top entities ranked by mention volume and sentiment"
        )
    
    def _get_what_changed(
        self,
        time_window: tuple[datetime, datetime],
        top_entities_df: pd.DataFrame,
        velocity_alerts: List[Dict[str, Any]]
    ) -> BriefSection:
        """Get 'What Changed This Week' section with risers, fallers, trends."""
        if len(top_entities_df) == 0:
            return BriefSection(
                title="What Changed This Week",
                items=[],
                summary="No entity data available"
            )
        
        items = []
        
        # Top risers (positive sentiment change)
        risers = []
        for alert in velocity_alerts:
            if alert.get('percent_change', 0) > 30:  # Significant positive change
                risers.append({
                    'entity': alert.get('entity_name', 'Unknown'),
                    'change': f"+{alert.get('percent_change', 0):.1f}%",
                    'current': alert.get('recent_sentiment', 0.0),
                    'type': 'riser'
                })
        
        # Top fallers (negative sentiment change)
        fallers = []
        for alert in velocity_alerts:
            if alert.get('percent_change', 0) < -30:  # Significant negative change
                fallers.append({
                    'entity': alert.get('entity_name', 'Unknown'),
                    'change': f"{alert.get('percent_change', 0):.1f}%",
                    'current': alert.get('recent_sentiment', 0.0),
                    'type': 'faller'
                })
        
        # New negative trends (entities with negative sentiment but not in alerts)
        # IMPORTANT: Don't mark as "new negative" if sentiment is improving (recovery)
        new_negative = []
        for _, row in top_entities_df.iterrows():
            if row['avg_sentiment'] < -0.3:
                entity_name = row['entity_name']
                
                # Check if entity is already in risers (improving sentiment = recovery, not new negative)
                is_improving = any(r['entity'] == entity_name for r in risers)
                
                # Check if entity is already in fallers (already covered)
                is_falling = any(f['entity'] == entity_name for f in fallers)
                
                # Only mark as "new negative" if:
                # 1. Sentiment is negative (< -0.3)
                # 2. NOT improving (not in risers)
                # 3. NOT already falling (not in fallers - to avoid duplicates)
                if not is_improving and not is_falling:
                    new_negative.append({
                        'entity': entity_name,
                        'sentiment': row['avg_sentiment'],
                        'mentions': int(row['mention_count']),
                        'type': 'new_negative'
                    })
        
        # New positive narratives (entities with strong positive sentiment)
        new_positive = []
        for _, row in top_entities_df.iterrows():
            if row['avg_sentiment'] > 0.5:
                # Check if not already in risers
                if not any(r['entity'] == row['entity_name'] for r in risers):
                    new_positive.append({
                        'entity': row['entity_name'],
                        'sentiment': row['avg_sentiment'],
                        'mentions': int(row['mention_count']),
                        'type': 'new_positive'
                    })
        
        # Surprising shifts (large volume + significant change)
        surprising = []
        for alert in velocity_alerts:
            entity_name = alert.get('entity_name', 'Unknown')
            entity_row = top_entities_df[top_entities_df['entity_name'] == entity_name]
            if len(entity_row) > 0:
                mentions = int(entity_row.iloc[0]['mention_count'])
                if mentions > 500 and abs(alert.get('percent_change', 0)) > 50:
                    surprising.append({
                        'entity': entity_name,
                        'change': f"{alert.get('percent_change', 0):+.1f}%",
                        'mentions': mentions,
                        'type': 'surprising'
                    })
        
        # Combine into single table
        all_changes = []
        
        # Add risers
        for riser in risers[:3]:  # Top 3
            all_changes.append({
                'category': 'Top Riser',
                'entity': riser['entity'],
                'metric': riser['change'],
                'detail': f"Sentiment: {riser['current']:+.2f}"
            })
        
        # Add fallers
        for faller in fallers[:3]:  # Top 3
            all_changes.append({
                'category': 'Top Faller',
                'entity': faller['entity'],
                'metric': faller['change'],
                'detail': f"Sentiment: {faller['current']:+.2f}"
            })
        
        # Add new negative trends (only if NOT already improving)
        for neg in new_negative[:2]:  # Top 2
            # Check if this entity is already in risers (improving sentiment)
            is_improving = any(r['entity'] == neg['entity'] for r in risers)
            if not is_improving:
                all_changes.append({
                    'category': 'New Negative',
                    'entity': neg['entity'],
                    'metric': f"{neg['sentiment']:+.2f}",
                    'detail': f"{neg['mentions']} mentions"
                })
        
        # Add new positive narratives
        for pos in new_positive[:2]:  # Top 2
            all_changes.append({
                'category': 'New Positive',
                'entity': pos['entity'],
                'metric': f"{pos['sentiment']:+.2f}",
                'detail': f"{pos['mentions']} mentions"
            })
        
        # Add surprising shifts
        for surp in surprising[:2]:  # Top 2
            all_changes.append({
                'category': 'Surprising Shift',
                'entity': surp['entity'],
                'metric': surp['change'],
                'detail': f"{surp['mentions']} mentions"
            })
        
        summary = f"{len(risers)} risers, {len(fallers)} fallers, {len(new_negative)} new negative trends, {len(new_positive)} new positive narratives"
        
        return BriefSection(
            title="What Changed This Week",
            items=all_changes,
            summary=summary
        )
    
    def _get_cross_platform_deltas(
        self,
        time_window: tuple[datetime, datetime],
        top_entities_df: pd.DataFrame
    ) -> BriefSection:
        """Get cross-platform deltas showing platform-specific insights."""
        from et_intel_core.models import Post, Comment, ExtractedSignal, MonitoredEntity
        from et_intel_core.models.enums import SignalType
        from sqlalchemy import func
        from et_intel_core.db import get_session
        
        session = get_session()
        try:
            deltas = []
            
            # For each top entity, get platform-specific sentiment
            for _, entity_row in top_entities_df.head(5).iterrows():
                entity_name = entity_row['entity_name']
                entity = session.query(MonitoredEntity).filter_by(name=entity_name).first()
                
                if not entity:
                    continue
                
                # Get sentiment by platform
                platform_sentiment = session.query(
                    Post.platform,
                    func.avg(ExtractedSignal.numeric_value).label('avg_sentiment'),
                    func.count(func.distinct(Comment.id)).label('mention_count')
                ).join(
                    Comment, Post.id == Comment.post_id
                ).join(
                    ExtractedSignal, Comment.id == ExtractedSignal.comment_id
                ).filter(
                    ExtractedSignal.entity_id == entity.id,
                    ExtractedSignal.signal_type == SignalType.SENTIMENT,
                    ExtractedSignal.numeric_value.isnot(None),
                    Comment.created_at.between(time_window[0], time_window[1])
                ).group_by(Post.platform).all()
                
                if len(platform_sentiment) < 2:
                    continue  # Need at least 2 platforms for comparison
                
                # Find best and worst platform
                platform_data = [
                    {'platform': p.platform, 'sentiment': float(p.avg_sentiment), 'mentions': int(p.mention_count)}
                    for p in platform_sentiment
                ]
                best_platform = max(platform_data, key=lambda x: x['sentiment'])
                worst_platform = min(platform_data, key=lambda x: x['sentiment'])
                
                # Generate insight
                if best_platform['sentiment'] - worst_platform['sentiment'] > 0.3:
                    insight = (
                        f"{entity_name} shows {best_platform['platform'].title()}-driven positivity "
                        f"({best_platform['sentiment']:+.2f}) while {worst_platform['platform'].title()} "
                        f"is more negative ({worst_platform['sentiment']:+.2f})"
                    )
                elif worst_platform['sentiment'] - best_platform['sentiment'] < -0.3:
                    insight = (
                        f"{entity_name} is being discussed more negatively on {worst_platform['platform'].title()} "
                        f"({worst_platform['sentiment']:+.2f}) than {best_platform['platform'].title()} "
                        f"({best_platform['sentiment']:+.2f})"
                    )
                else:
                    insight = (
                        f"{entity_name} sentiment is consistent across platforms "
                        f"({best_platform['platform'].title()}: {best_platform['sentiment']:+.2f}, "
                        f"{worst_platform['platform'].title()}: {worst_platform['sentiment']:+.2f})"
                    )
                
                deltas.append({
                    'entity': entity_name,
                    'insight': insight,
                    'best_platform': best_platform['platform'],
                    'worst_platform': worst_platform['platform'],
                    'delta': best_platform['sentiment'] - worst_platform['sentiment']
                })
            
            return BriefSection(
                title="Cross-Platform Deltas",
                items=deltas,
                summary=f"Platform-specific sentiment analysis for {len(deltas)} top entities"
            )
        finally:
            session.close()
    
    def _generate_key_risks(
        self,
        velocity_alerts: List[Dict[str, Any]],
        top_entities_df: pd.DataFrame,
        platform_breakdown: List[Dict[str, Any]]
    ) -> BriefSection:
        """Generate key risks/watchouts - actionable one-sentence alerts."""
        risks = []
        
        # Critical velocity alerts
        for alert in velocity_alerts:
            if abs(alert.get('percent_change', 0)) > 50:
                entity_name = alert.get('entity_name', 'Unknown')
                change = alert.get('percent_change', 0)
                direction = "accelerating" if change < 0 else "improving"
                risks.append({
                    'risk': f"{entity_name} negativity {direction}; {abs(change):.1f}% sentiment shift in 72hrs",
                    'severity': 'critical',
                    'type': 'velocity'
                })
        
        # Fragile entities (negative sentiment but not critical yet)
        for _, row in top_entities_df.iterrows():
            if -0.6 < row['avg_sentiment'] < -0.3 and row['mention_count'] > 200:
                risks.append({
                    'risk': f"{row['entity_name']} sentiment remains fragile ({row['avg_sentiment']:+.2f}) with high volume ({int(row['mention_count']):,} mentions)",
                    'severity': 'warning',
                    'type': 'fragile'
                })
        
        # Platform-specific risks
        if len(platform_breakdown) >= 2:
            worst_platform = min(platform_breakdown, key=lambda x: x.get('avg_sentiment', 0))
            if worst_platform.get('avg_sentiment', 0) < -0.2:
                risks.append({
                    'risk': f"{worst_platform.get('platform', 'Unknown').title()} shows negative sentiment ({worst_platform.get('avg_sentiment', 0):+.2f}) across {worst_platform.get('comment_count', 0):,} comments",
                    'severity': 'warning',
                    'type': 'platform'
                })
        
        # Limit to top 5 risks
        risks = sorted(risks, key=lambda x: 0 if x['severity'] == 'critical' else 1)[:5]
        
        return BriefSection(
            title="Key Risks & Watchouts",
            items=risks,
            summary=f"{len(risks)} actionable risks identified"
        )
    
    def _generate_entity_micro_insights(
        self,
        top_entities_df: pd.DataFrame,
        velocity_alerts: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        """Generate micro-insights (1-2 bullets) per top entity."""
        insights = {}
        
        # Create velocity map
        velocity_map = {a.get('entity_name'): a for a in velocity_alerts}
        
        # Limit to top entities for scale (use table limit)
        for _, row in top_entities_df.head(TOP_ENTITIES_TABLE).iterrows():
            entity_name = row['entity_name']
            bullets = []
            
            # Sentiment insight
            sentiment = row['avg_sentiment']
            if sentiment > 0.5:
                bullets.append(f"Strong positive sentiment ({sentiment:+.2f}) with {int(row['mention_count']):,} mentions")
            elif sentiment < -0.5:
                bullets.append(f"Significant negative sentiment ({sentiment:+.2f}) across {int(row['mention_count']):,} mentions")
            else:
                bullets.append(f"Neutral sentiment ({sentiment:+.2f}) with {int(row['mention_count']):,} mentions")
            
            # Velocity insight
            if entity_name in velocity_map:
                alert = velocity_map[entity_name]
                change = alert.get('percent_change', 0)
                if abs(change) > 30:
                    bullets.append(f"Sentiment {('improved' if change > 0 else 'declined')} {abs(change):.1f}% in past 72hrs")
            
            # Engagement insight
            if row['total_likes'] > 50000:
                bullets.append(f"High engagement: {int(row['total_likes']):,} total likes")
            
            insights[entity_name] = " • ".join(bullets[:2])  # Limit to 2 bullets
        
        return insights
    
    def _detect_storylines(
        self,
        time_window: tuple[datetime, datetime],
        top_entities_df: pd.DataFrame
    ) -> BriefSection:
        """Detect storylines through keyword clustering and repeated phrases."""
        from et_intel_core.models import Comment, ExtractedSignal, Post
        from et_intel_core.models.enums import SignalType
        from et_intel_core.db import get_session
        from collections import Counter
        import re
        
        session = get_session()
        try:
            # Get comments with high engagement (likely to contain storylines)
            high_engagement_comments = session.query(Comment).join(
                Post, Comment.post_id == Post.id
            ).filter(
                Comment.created_at.between(time_window[0], time_window[1]),
                Comment.likes >= 10  # High engagement threshold
            ).order_by(Comment.likes.desc()).limit(200).all()
            
            if len(high_engagement_comments) == 0:
                return BriefSection(
                    title="Active Storylines",
                    items=[],
                    summary="No high-engagement comments found for storyline detection"
                )
            
            # Extract keywords and phrases
            all_text = " ".join([c.text.lower() for c in high_engagement_comments])
            
            # Common entertainment keywords/phrases
            storyline_patterns = [
                r'\bdivorce\b', r'\bpregnancy\b', r'\bbreakup\b', r'\bengagement\b',
                r'\bcontroversy\b', r'\bscandal\b', r'\blawsuit\b', r'\bfeud\b',
                r'\bcollab\b', r'\bcollaboration\b', r'\bcomeback\b', r'\bretirement\b',
                r'\bnew album\b', r'\bnew movie\b', r'\bnew show\b', r'\btour\b',
                r'\baward\b', r'\bnomination\b', r'\bwin\b', r'\bloss\b'
            ]
            
            storyline_counts = {}
            for pattern in storyline_patterns:
                matches = len(re.findall(pattern, all_text))
                if matches >= 3:  # At least 3 mentions
                    storyline_name = pattern.replace(r'\b', '').replace('\\', '').title()
                    storyline_counts[storyline_name] = matches
            
            # Get top entities mentioned with storylines
            storylines = []
            for storyline, count in sorted(storyline_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
                # Find which entities are associated with this storyline
                associated_entities = []
                for _, row in top_entities_df.iterrows():
                    entity_name = row['entity_name'].lower()
                    # Simple check: if entity name appears in comments mentioning this storyline
                    storyline_comments = [c for c in high_engagement_comments 
                                         if storyline.lower() in c.text.lower() 
                                         and entity_name in c.text.lower()]
                    if len(storyline_comments) >= 2:
                        associated_entities.append(row['entity_name'])
                
                storylines.append({
                    'storyline': storyline,
                    'mention_count': count,
                    'entities': ', '.join(associated_entities[:3]) if associated_entities else 'General',
                    'type': 'trending'
                })
            
            # If no storylines detected, create placeholder
            if len(storylines) == 0:
                return BriefSection(
                    title="Active Storylines",
                    items=[],
                    summary="No clear storylines detected in high-engagement comments"
                )
            
            return BriefSection(
                title="Active Storylines",
                items=storylines,
                summary=f"{len(storylines)} storylines detected from {len(high_engagement_comments)} high-engagement comments"
            )
        finally:
            session.close()
    
    def _get_emotion_analysis(
        self,
        time_window: Tuple[datetime, datetime],
        top_entities_df: pd.DataFrame
    ) -> BriefSection:
        """Get emotion distribution for top entities."""
        from datetime import timedelta
        
        days = (time_window[1] - time_window[0]).days or 30
        
        items = []
        for _, row in top_entities_df.head(5).iterrows():
            entity_id = row.get('entity_id')
            if not entity_id:
                continue
            
            emotion_dist = self.analytics.get_emotion_distribution(entity_id, days=days)
            if emotion_dist:
                items.append({
                    'entity_name': row.get('entity_name', 'Unknown'),
                    'emotions': emotion_dist,
                    'total_emotion_signals': sum(emotion_dist.values())
                })
        
        summary = f"Emotion analysis for top {len(items)} entities"
        if not items:
            summary = "No emotion signals found"
        
        return BriefSection(
            title="Emotion Analysis",
            items=items,
            summary=summary
        )
    
    def _get_topic_clusters(
        self,
        time_window: Tuple[datetime, datetime]
    ) -> BriefSection:
        """Get top topics from topic signals."""
        from datetime import timedelta
        
        days = (time_window[1] - time_window[0]).days or 30
        
        topics = self.analytics.get_top_topics(days=days, limit=10)
        
        items = [
            {
                'topic': topic['topic'],
                'mentions': topic['mentions']
            }
            for topic in topics
        ]
        
        summary = f"{len(items)} trending topics identified"
        if not items:
            summary = "No topic signals found"
        
        return BriefSection(
            title="Topic Clusters",
            items=items,
            summary=summary
        )
    
    def _get_toxicity_alerts(
        self,
        time_window: Tuple[datetime, datetime]
    ) -> BriefSection:
        """Get high-toxicity comments."""
        from datetime import timedelta
        
        days = (time_window[1] - time_window[0]).days or 30
        
        alerts = self.analytics.get_toxicity_alerts(threshold=0.7, days=days)
        
        items = alerts[:10]  # Limit to top 10
        
        summary = f"{len(alerts)} high-toxicity comments (threshold: 0.7)"
        if not items:
            summary = "No high-toxicity comments detected"
        
        return BriefSection(
            title="Toxicity Alerts",
            items=items,
            summary=summary
        )
    
    def _get_stance_summary(
        self,
        time_window: Tuple[datetime, datetime],
        top_entities_df: pd.DataFrame
    ) -> BriefSection:
        """Get stance breakdown for top entities."""
        from datetime import timedelta
        
        days = (time_window[1] - time_window[0]).days or 30
        
        items = []
        for _, row in top_entities_df.head(5).iterrows():
            entity_id = row.get('entity_id')
            if not entity_id:
                continue
            
            stance_breakdown = self.analytics.get_stance_breakdown(entity_id, days=days)
            if stance_breakdown and any(stance_breakdown.values()):
                total = sum(stance_breakdown.values())
                items.append({
                    'entity_name': row.get('entity_name', 'Unknown'),
                    'support': stance_breakdown.get('support', 0),
                    'oppose': stance_breakdown.get('oppose', 0),
                    'neutral': stance_breakdown.get('neutral', 0),
                    'total': total
                })
        
        summary = f"Stance breakdown for top {len(items)} entities"
        if not items:
            summary = "No stance signals found"
        
        return BriefSection(
            title="Stance Summary",
            items=items,
            summary=summary
        )
    
    def _get_post_performance(
        self,
        time_window: Tuple[datetime, datetime]
    ) -> BriefSection:
        """Get post-level performance metrics."""
        start_date, end_date = time_window
        
        # Get top posts by engagement
        top_posts = self.analytics.get_top_posts(
            start_date=start_date,
            end_date=end_date,
            limit=10
        )
        
        # Get post sentiment distribution
        distribution = self.analytics.get_post_sentiment_distribution(
            start_date=start_date,
            end_date=end_date
        )
        
        # Format items for the section
        items = []
        for i, post in enumerate(top_posts, 1):
            items.append({
                'rank': i,
                'caption': post['caption'],
                'url': post['url'],
                'platform': post['platform'],
                'comment_count': post['comment_count'],
                'total_likes': post['total_likes'],
                'avg_sentiment': post['avg_sentiment'],
                'top_entity': post.get('top_entity')
            })
        
        # Add distribution summary
        summary = (
            f"Top {len(items)} posts by comment volume. "
            f"Post sentiment distribution: {distribution['positive_posts']} positive, "
            f"{distribution['neutral_posts']} neutral, {distribution['negative_posts']} negative "
            f"(out of {distribution['total_posts']} posts with 5+ comments)."
        )
        
        return BriefSection(
            title="Top Posts This Week",
            items=items,
            summary=summary
        )

