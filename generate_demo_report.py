"""
Demo script to generate a sample intelligence brief report.
Uses mock data to demonstrate the PDF output.
"""

from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import shutil

from et_intel_core.reporting import BriefBuilder, BriefSection, IntelligenceBriefData, PDFRenderer


def create_demo_brief_data():
    """Create sample brief data for demonstration."""
    
    # Create timeframe (last 7 days)
    end = datetime.utcnow()
    start = end - timedelta(days=7)
    
    # Create top entities section
    top_entities = BriefSection(
        title="Top Entities by Volume",
        items=[
            {
                'entity_name': 'Blake Lively',
                'entity_type': 'person',
                'mention_count': 1234,
                'avg_sentiment': -0.45,
                'total_likes': 45678,
                'weighted_sentiment': -0.52
            },
            {
                'entity_name': 'Taylor Swift',
                'entity_type': 'person',
                'mention_count': 987,
                'avg_sentiment': 0.72,
                'total_likes': 123456,
                'weighted_sentiment': 0.85
            },
            {
                'entity_name': 'Justin Baldoni',
                'entity_type': 'person',
                'mention_count': 756,
                'avg_sentiment': -0.61,
                'total_likes': 23456,
                'weighted_sentiment': -0.68
            },
            {
                'entity_name': 'Ryan Reynolds',
                'entity_type': 'person',
                'mention_count': 654,
                'avg_sentiment': 0.58,
                'total_likes': 34567,
                'weighted_sentiment': 0.64
            },
            {
                'entity_name': 'The Eras Tour',
                'entity_type': 'show',
                'mention_count': 543,
                'avg_sentiment': 0.82,
                'total_likes': 67890,
                'weighted_sentiment': 0.91
            }
        ],
        summary=(
            "Blake Lively dominated conversations with 1,234 mentions and negative sentiment (-0.45). "
            "Taylor Swift followed with 987 mentions and highly positive sentiment (+0.72)."
        )
    )
    
    # Create velocity alerts section (with narratives)
    velocity_alerts = BriefSection(
        title="Sentiment Velocity Alerts",
        items=[
            {
                'entity_name': 'Blake Lively',
                'percent_change': -123.5,
                'recent_sentiment': -0.523,
                'previous_sentiment': -0.234,
                'direction': 'down',
                'recent_sample_size': 234,
                'previous_sample_size': 198,
                'window_hours': 72,
                'narrative': (
                    "Sentiment plummeted 123% largely due to negative discourse surrounding "
                    "the It Ends With Us adaptation release. Recent comments show increased criticism "
                    "of casting decisions and adaptation choices, driving the sharp decline."
                )
            },
            {
                'entity_name': 'Justin Baldoni',
                'percent_change': -87.3,
                'recent_sentiment': -0.61,
                'previous_sentiment': -0.33,
                'direction': 'down',
                'recent_sample_size': 156,
                'previous_sample_size': 142,
                'window_hours': 72,
                'narrative': (
                    "Negative sentiment increased 87% following press cycle coverage of the film. "
                    "Comments reflect growing criticism of the adaptation's handling of sensitive themes, "
                    "with discourse intensifying around release timing and marketing approach."
                )
            }
        ],
        summary="2 entities with significant sentiment shifts (30%+ change in 72hrs)"
    )
    
    # Create brief data
    brief = IntelligenceBriefData(
        timeframe={'start': start, 'end': end},
        topline_summary={
            'total_comments': 5678,
            'total_entities': 15,
            'critical_alerts': 1,
            'velocity_alerts_count': 2
        },
        top_entities=top_entities,
        velocity_alerts=velocity_alerts,
        discovered_entities=BriefSection(
            title="Discovered Entities",
            items=[
                {
                    'name': 'Kelsea Ballerini',
                    'entity_type': 'PERSON',
                    'mention_count': 23,
                    'first_seen_at': '2024-11-15T00:00:00'
                },
                {
                    'name': 'Deadpool 3',
                    'entity_type': 'WORK_OF_ART',
                    'mention_count': 18,
                    'first_seen_at': '2024-11-16T00:00:00'
                }
            ],
            summary="2 new entities discovered by NLP (not yet in monitoring)"
        ),
        platform_breakdown=BriefSection(
            title="Platform Breakdown",
            items=[
                {
                    'platform': 'instagram',
                    'comment_count': 3456,
                    'avg_sentiment': 0.12,
                    'total_likes': 123456
                },
                {
                    'platform': 'youtube',
                    'comment_count': 2222,
                    'avg_sentiment': -0.08,
                    'total_likes': 89012
                }
            ],
            summary="Comment volume and sentiment by platform"
        ),
        sentiment_distribution={
            'positive': 2345,
            'negative': 1234,
            'neutral': 2099,
            'total': 5678,
            'positive_pct': 41.3,
            'negative_pct': 21.7,
            'neutral_pct': 37.0
        },
        contextual_narrative=(
            "Blake Lively dominated conversations with 1,234 mentions but experienced a critical sentiment collapse "
            "(-123.5%) driven by negative discourse around the It Ends With Us adaptation. In contrast, Taylor Swift "
            "maintained strong positive sentiment (+0.72) with 987 mentions, largely fueled by Eras Tour coverage. "
            "Platform analysis reveals Instagram skews positive (+0.12) while YouTube shows negative sentiment (-0.08), "
            "indicating platform-specific discourse patterns that warrant strategic attention."
        ),
        entity_comparison=BriefSection(
            title="Entity Comparison",
            items=[
                {
                    'entity_name': 'Blake Lively',
                    'current_sentiment': -0.45,
                    'mention_count': 1234,
                    'trend': 'falling'
                },
                {
                    'entity_name': 'Taylor Swift',
                    'current_sentiment': 0.72,
                    'mention_count': 987,
                    'trend': 'rising'
                },
                {
                    'entity_name': 'Justin Baldoni',
                    'current_sentiment': -0.61,
                    'mention_count': 756,
                    'trend': 'falling'
                }
            ],
            summary="Top entities ranked by mention volume and sentiment"
        ),
        what_changed=BriefSection(
            title="What Changed This Week",
            items=[
                {'category': 'Top Faller', 'entity': 'Blake Lively', 'metric': '-123.5%', 'detail': 'Sentiment: -0.52'},
                {'category': 'Top Faller', 'entity': 'Justin Baldoni', 'metric': '-87.3%', 'detail': 'Sentiment: -0.61'},
                {'category': 'Top Riser', 'entity': 'Taylor Swift', 'metric': '+18.2%', 'detail': 'Sentiment: +0.72'},
                {'category': 'New Negative', 'entity': 'Ryan Reynolds', 'metric': '-0.15', 'detail': '234 mentions'},
                {'category': 'Surprising Shift', 'entity': 'Blake Lively', 'metric': '-123.5%', 'detail': '1,234 mentions'}
            ],
            summary="2 risers, 2 fallers, 1 new negative trend, 1 surprising shift"
        ),
        key_risks=BriefSection(
            title="Key Risks & Watchouts",
            items=[
                {
                    'risk': 'Blake Lively negativity accelerating; 123.5% sentiment shift in 72hrs',
                    'severity': 'critical',
                    'type': 'velocity'
                },
                {
                    'risk': 'Justin Baldoni sentiment remains fragile (-0.61) with high volume (756 mentions)',
                    'severity': 'warning',
                    'type': 'fragile'
                },
                {
                    'risk': 'YouTube shows negative sentiment (-0.08) across 2,222 comments',
                    'severity': 'warning',
                    'type': 'platform'
                }
            ],
            summary="3 actionable risks identified"
        ),
        entity_micro_insights={
            'Blake Lively': 'Significant negative sentiment (-0.45) across 1,234 mentions • Sentiment declined 123.5% in past 72hrs',
            'Taylor Swift': 'Strong positive sentiment (+0.72) with 987 mentions • High engagement: 89,234 total likes',
            'Justin Baldoni': 'Significant negative sentiment (-0.61) across 756 mentions • Sentiment declined 87.3% in past 72hrs',
            'Ryan Reynolds': 'Neutral sentiment (-0.15) with 234 mentions',
            'Travis Kelce': 'Strong positive sentiment (+0.68) with 189 mentions'
        },
        cross_platform_deltas=BriefSection(
            title="Cross-Platform Deltas",
            items=[
                {
                    'entity': 'Blake Lively',
                    'insight': 'Blake Lively is being discussed more negatively on YouTube (-0.15) than Instagram (-0.10)',
                    'best_platform': 'instagram',
                    'worst_platform': 'youtube',
                    'delta': 0.05
                },
                {
                    'entity': 'Taylor Swift',
                    'insight': 'Taylor Swift shows Instagram-driven positivity (+0.75) while YouTube is more neutral (+0.45)',
                    'best_platform': 'instagram',
                    'worst_platform': 'youtube',
                    'delta': 0.30
                }
            ],
            summary="Platform-specific sentiment analysis for 2 top entities"
        ),
        storylines=BriefSection(
            title="Active Storylines",
            items=[
                {
                    'storyline': 'It Ends With Us',
                    'mention_count': 45,
                    'entities': 'Blake Lively, Justin Baldoni',
                    'type': 'trending'
                },
                {
                    'storyline': 'Eras Tour',
                    'mention_count': 38,
                    'entities': 'Taylor Swift, Travis Kelce',
                    'type': 'trending'
                },
                {
                    'storyline': 'Controversy',
                    'mention_count': 22,
                    'entities': 'Blake Lively',
                    'type': 'trending'
                }
            ],
            summary="3 storylines detected from 200 high-engagement comments"
        ),
        risk_signals=BriefSection(
            title="Risk Signals",
            items=[],
            summary="Risk signal detection not yet implemented"
        ),
        metadata={
            'generated_at': datetime.utcnow(),
            'platforms': ['instagram', 'youtube'],
            'focus_entities': []
        }
    )
    
    return brief


def main():
    """Generate demo report."""
    print("Generating demo intelligence brief...")
    
    # Create reports directory if it doesn't exist
    reports_dir = Path('reports')
    reports_dir.mkdir(exist_ok=True)
    
    # Create demo brief data
    brief = create_demo_brief_data()
    
    # Render PDF
    renderer = PDFRenderer(reports_dir)
    
    print("Rendering PDF...")
    pdf_path = renderer.render(brief, filename="demo_intelligence_brief.pdf")
    
    print(f"\n[SUCCESS] Demo brief generated: {pdf_path}")
    print(f"\nBrief Summary:")
    print(f"   Total Comments: {brief.topline_summary['total_comments']:,}")
    print(f"   Entities Tracked: {brief.topline_summary['total_entities']}")
    print(f"   Velocity Alerts: {brief.topline_summary['velocity_alerts_count']}")
    print(f"   Critical Alerts: {brief.topline_summary['critical_alerts']}")
    print(f"\nOpen PDF: {pdf_path.absolute()}")
    
    # Also save JSON
    import json
    json_path = pdf_path.with_suffix('.json')
    with open(json_path, 'w') as f:
        json.dump(brief.to_dict(), f, indent=2, default=str)
    print(f"[SUCCESS] Data saved: {json_path}")


if __name__ == '__main__':
    main()

