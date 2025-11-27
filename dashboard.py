"""
ET Social Intelligence Dashboard

Interactive Streamlit dashboard for exploring social intelligence data.
Uses direct library imports (no HTTP overhead).
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
from typing import Optional, List

from et_intel_core.db import get_session
from et_intel_core.analytics import AnalyticsService
from et_intel_core.models import MonitoredEntity

# Page config
st.set_page_config(
    page_title="ET Social Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 1rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    .alert-box {
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    .alert-critical {
        background-color: #fee;
        border-left: 4px solid #d32f2f;
    }
    .alert-warning {
        background-color: #fff3cd;
        border-left: 4px solid #ff9800;
    }
    .alert-success {
        background-color: #d4edda;
        border-left: 4px solid #28a745;
    }
    </style>
""", unsafe_allow_html=True)


def get_sentiment_color(sentiment: float) -> str:
    """Get color for sentiment score."""
    if sentiment > 0.3:
        return "#28a745"  # Green
    elif sentiment < -0.3:
        return "#dc3545"  # Red
    else:
        return "#6c757d"  # Gray


def get_sentiment_label(sentiment: float) -> str:
    """Get human-readable sentiment label."""
    if sentiment > 0.7:
        return "Strongly Positive"
    elif sentiment > 0.3:
        return "Positive"
    elif sentiment > -0.3:
        return "Neutral"
    elif sentiment > -0.7:
        return "Negative"
    else:
        return "Strongly Negative"


def format_sentiment(sentiment: float) -> str:
    """Format sentiment with label and color."""
    label = get_sentiment_label(sentiment)
    color = get_sentiment_color(sentiment)
    return f'<span style="color: {color}; font-weight: bold;">{sentiment:+.2f} ({label})</span>'


# Initialize session state for database connection
@st.cache_resource
def get_analytics_service():
    """Get cached analytics service."""
    session = get_session()
    return AnalyticsService(session), session


# Get analytics service
analytics, session = get_analytics_service()

# Header
st.markdown('<div class="main-header">📊 ET Social Intelligence Dashboard</div>', unsafe_allow_html=True)
st.markdown("---")

# Sidebar filters
st.sidebar.header("🔍 Filters")

# Date range filter
st.sidebar.subheader("Time Range")
days_back = st.sidebar.slider(
    "Days to analyze",
    min_value=1,
    max_value=90,
    value=30,
    step=1,
    help="Number of days to look back from today"
)

end_date = datetime.utcnow()
start_date = end_date - timedelta(days=days_back)

st.sidebar.info(f"**Period**: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")

# Platforms filter
st.sidebar.subheader("Platforms")
platforms = st.sidebar.multiselect(
    "Select platforms",
    options=["instagram", "youtube", "tiktok"],
    default=["instagram"],
    help="Filter by social media platform"
)

# Entity type filter (for top entities)
st.sidebar.subheader("Entity Filters")
entity_types = st.sidebar.multiselect(
    "Entity types",
    options=["person", "show", "couple", "brand"],
    default=[],
    help="Filter by entity type (leave empty for all)"
)

# Refresh button
if st.sidebar.button("🔄 Refresh Data", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

# Main content tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "📈 Overview",
    "🎯 Top Entities",
    "🔍 Entity Deep Dive",
    "🆕 Discovered Entities"
])

# ============================================
# TAB 1: Overview
# ============================================
with tab1:
    st.header("📈 Overview Dashboard")
    
    # Get top entities for overview
    try:
        top_entities_df = analytics.get_top_entities(
            (start_date, end_date),
            platforms=platforms if platforms else None,
            limit=10
        )
        
        comment_count = analytics.get_comment_count((start_date, end_date))
        
        # Key metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Total Comments",
                f"{comment_count:,}",
                help="Total comments in selected time period"
            )
        
        with col2:
            if len(top_entities_df) > 0:
                top_entity = top_entities_df.iloc[0]
                st.metric(
                    "Top Entity",
                    top_entity['entity_name'],
                    help=f"{top_entity['mention_count']} mentions"
                )
            else:
                st.metric("Top Entity", "N/A")
        
        with col3:
            if len(top_entities_df) > 0:
                avg_sentiment = top_entities_df['avg_sentiment'].mean()
                st.metric(
                    "Avg Sentiment",
                    f"{avg_sentiment:+.2f}",
                    help="Average sentiment across all entities"
                )
            else:
                st.metric("Avg Sentiment", "N/A")
        
        with col4:
            if len(top_entities_df) > 0:
                total_likes = top_entities_df['total_likes'].sum()
                st.metric(
                    "Total Engagement",
                    f"{total_likes:,}",
                    help="Total likes across all comments"
                )
            else:
                st.metric("Total Engagement", "N/A")
        
        st.markdown("---")
        
        # Top 5 entities table
        if len(top_entities_df) > 0:
            st.subheader("Top 5 Entities")
            
            # Format the dataframe for display
            display_df = top_entities_df.head(5).copy()
            display_df['Sentiment'] = display_df['avg_sentiment'].apply(
                lambda x: format_sentiment(x)
            )
            
            # Select columns to display
            st.dataframe(
                display_df[['entity_name', 'entity_type', 'mention_count', 'total_likes']].style.format({
                    'mention_count': '{:,}',
                    'total_likes': '{:,}',
                    'avg_sentiment': '{:+.2f}'
                }),
                use_container_width=True,
                hide_index=True
            )
            
            # Sentiment distribution chart
            st.subheader("Sentiment Distribution")
            
            # Create pie chart
            sentiment_dist = analytics.get_sentiment_distribution((start_date, end_date))
            
            if sentiment_dist:
                fig = px.pie(
                    values=list(sentiment_dist.values()),
                    names=list(sentiment_dist.keys()),
                    title="Sentiment Label Distribution",
                    color_discrete_map={
                        "positive": "#28a745",
                        "negative": "#dc3545",
                        "neutral": "#6c757d"
                    }
                )
                fig.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig, use_container_width=True)
            
            # Entity sentiment scatter
            st.subheader("Entity Sentiment vs Volume")
            
            fig = px.scatter(
                top_entities_df,
                x='mention_count',
                y='avg_sentiment',
                size='total_likes',
                color='avg_sentiment',
                hover_data=['entity_name', 'entity_type'],
                title='Entity Sentiment vs. Mention Volume',
                color_continuous_scale='RdYlGn',
                color_continuous_midpoint=0,
                labels={
                    'mention_count': 'Mention Count',
                    'avg_sentiment': 'Average Sentiment',
                    'total_likes': 'Total Likes'
                }
            )
            fig.add_hline(y=0, line_dash="dash", line_color="gray", annotation_text="Neutral")
            fig.add_hline(y=0.3, line_dash="dot", line_color="green", opacity=0.5, annotation_text="Positive threshold")
            fig.add_hline(y=-0.3, line_dash="dot", line_color="red", opacity=0.5, annotation_text="Negative threshold")
            fig.update_layout(yaxis_range=[-1, 1])
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data found for the selected time period and filters.")
    
    except Exception as e:
        st.error(f"Error loading overview data: {str(e)}")
        if st.checkbox("Show error details"):
            st.exception(e)

# ============================================
# TAB 2: Top Entities
# ============================================
with tab2:
    st.header("🎯 Top Entities by Volume")
    
    try:
        # Get top entities
        limit = st.slider("Number of entities to show", 10, 50, 20, key="top_entities_limit")
        
        top_entities_df = analytics.get_top_entities(
            (start_date, end_date),
            platforms=platforms if platforms else None,
            limit=limit
        )
        
        if len(top_entities_df) > 0:
            # Filter by entity type if selected
            if entity_types:
                top_entities_df = top_entities_df[top_entities_df['entity_type'].isin(entity_types)]
            
            # Display table with formatting
            st.dataframe(
                top_entities_df.style.format({
                    'avg_sentiment': '{:+.3f}',
                    'weighted_sentiment': '{:+.3f}',
                    'mention_count': '{:,}',
                    'total_likes': '{:,}'
                }).applymap(
                    lambda x: f"color: {get_sentiment_color(x)}" if isinstance(x, float) and -1 <= x <= 1 else "",
                    subset=['avg_sentiment']
                ),
                use_container_width=True,
                height=600
            )
            
            # Download button
            csv = top_entities_df.to_csv(index=False)
            st.download_button(
                label="📥 Download as CSV",
                data=csv,
                file_name=f"top_entities_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
            
            # Bar chart of top entities
            st.subheader("Top Entities by Mention Count")
            
            top_10 = top_entities_df.head(10)
            fig = px.bar(
                top_10,
                x='entity_name',
                y='mention_count',
                color='avg_sentiment',
                color_continuous_scale='RdYlGn',
                color_continuous_midpoint=0,
                labels={
                    'entity_name': 'Entity',
                    'mention_count': 'Mention Count',
                    'avg_sentiment': 'Avg Sentiment'
                },
                title="Top 10 Entities by Mention Volume"
            )
            fig.update_xaxes(tickangle=45)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No entities found for the selected time period and filters.")
    
    except Exception as e:
        st.error(f"Error loading top entities: {str(e)}")
        if st.checkbox("Show error details", key="top_entities_error"):
            st.exception(e)

# ============================================
# TAB 3: Entity Deep Dive
# ============================================
with tab3:
    st.header("🔍 Entity Deep Dive")
    
    try:
        # Get list of entities for selector
        all_entities_df = analytics.get_top_entities(
            (start_date, end_date),
            platforms=platforms if platforms else None,
            limit=100
        )
        
        if len(all_entities_df) == 0:
            st.warning("No entities found. Try adjusting your filters or ingesting more data.")
        else:
            # Entity selector
            entity_names = all_entities_df['entity_name'].tolist()
            selected_entity_name = st.selectbox(
                "Select entity to analyze",
                options=entity_names,
                help="Choose an entity to see detailed analysis"
            )
            
            if selected_entity_name:
                # Get entity ID
                entity = session.query(MonitoredEntity).filter_by(
                    name=selected_entity_name
                ).first()
                
                if entity:
                    entity_id = entity.id
                    
                    # Get entity row data
                    entity_row = all_entities_df[all_entities_df['entity_name'] == selected_entity_name].iloc[0]
                    
                    # Display metrics
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric(
                            "Mentions",
                            f"{int(entity_row['mention_count']):,}",
                            help="Number of comments mentioning this entity"
                        )
                    
                    with col2:
                        sentiment_val = entity_row['avg_sentiment']
                        delta = None
                        delta_color = "off"
                        if abs(sentiment_val) > 0.3:
                            delta_color = "normal" if sentiment_val > 0 else "inverse"
                        
                        st.metric(
                            "Avg Sentiment",
                            f"{sentiment_val:+.2f}",
                            delta=None,
                            delta_color=delta_color,
                            help=get_sentiment_label(sentiment_val)
                        )
                    
                    with col3:
                        st.metric(
                            "Total Likes",
                            f"{int(entity_row['total_likes']):,}",
                            help="Total engagement on comments mentioning this entity"
                        )
                    
                    with col4:
                        weighted = entity_row['weighted_sentiment']
                        st.metric(
                            "Weighted Sentiment",
                            f"{weighted:+.2f}",
                            help="Like-weighted sentiment score"
                        )
                    
                    st.markdown("---")
                    
                    # Velocity check
                    st.subheader("⚡ Velocity Alert")
                    
                    velocity = analytics.compute_velocity(entity_id, window_hours=72)
                    
                    if 'error' not in velocity:
                        if velocity['alert']:
                            st.markdown(
                                f"""
                                <div class="alert-box alert-critical">
                                    <h4>⚠️ Critical Alert: {velocity['percent_change']:+.1f}% Change</h4>
                                    <p><strong>Recent:</strong> {velocity['recent_sentiment']:.3f} 
                                    (<strong>Previous:</strong> {velocity['previous_sentiment']:.3f})</p>
                                    <p>Sentiment {velocity['direction']} by {abs(velocity['percent_change']):.1f}% 
                                    in the last {velocity['window_hours']} hours.</p>
                                    <p><small>Sample sizes: Recent={velocity['recent_sample_size']}, 
                                    Previous={velocity['previous_sample_size']}</small></p>
                                </div>
                                """,
                                unsafe_allow_html=True
                            )
                        else:
                            st.markdown(
                                f"""
                                <div class="alert-box alert-success">
                                    <h4>✓ Stable Sentiment</h4>
                                    <p>Change: {velocity['percent_change']:+.1f}% in last {velocity['window_hours']} hours</p>
                                    <p>Recent: {velocity['recent_sentiment']:.3f} 
                                    (Previous: {velocity['previous_sentiment']:.3f})</p>
                                </div>
                                """,
                                unsafe_allow_html=True
                            )
                    else:
                        st.info(f"Velocity: {velocity['error']}")
                    
                    # Sentiment history chart
                    st.subheader("📈 Sentiment Trend Over Time")
                    
                    history_days = st.slider(
                        "Days of history",
                        min_value=7,
                        max_value=90,
                        value=min(days_back, 30),
                        key="history_days"
                    )
                    
                    history_df = analytics.get_entity_sentiment_history(entity_id, days=history_days)
                    
                    if len(history_df) > 0:
                        # Convert date column if needed
                        if 'date' in history_df.columns:
                            history_df['date'] = pd.to_datetime(history_df['date'])
                        
                        fig = go.Figure()
                        
                        # Sentiment line
                        fig.add_trace(go.Scatter(
                            x=history_df['date'],
                            y=history_df['avg_sentiment'],
                            mode='lines+markers',
                            name='Sentiment',
                            line=dict(color='#1f77b4', width=3),
                            marker=dict(size=6)
                        ))
                        
                        # Reference lines
                        fig.add_hline(y=0, line_dash="dash", line_color="gray", annotation_text="Neutral")
                        fig.add_hline(y=0.3, line_dash="dot", line_color="green", opacity=0.5, annotation_text="Positive")
                        fig.add_hline(y=-0.3, line_dash="dot", line_color="red", opacity=0.5, annotation_text="Negative")
                        
                        fig.update_layout(
                            title=f"Sentiment Over Time: {selected_entity_name}",
                            xaxis_title="Date",
                            yaxis_title="Average Sentiment (-1.0 to +1.0)",
                            yaxis_range=[-1, 1],
                            hovermode='x unified',
                            height=400
                        )
                        
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # Mention volume chart
                        st.subheader("📊 Mention Volume Over Time")
                        
                        fig2 = go.Figure()
                        fig2.add_trace(go.Bar(
                            x=history_df['date'],
                            y=history_df['mention_count'],
                            name='Mentions',
                            marker_color='#17a2b8'
                        ))
                        
                        fig2.update_layout(
                            title=f"Mention Volume: {selected_entity_name}",
                            xaxis_title="Date",
                            yaxis_title="Number of Mentions",
                            height=300
                        )
                        
                        st.plotly_chart(fig2, use_container_width=True)
                    else:
                        st.info("No sentiment history data available for this entity.")
                    
                    # Entity comparison (if multiple entities selected)
                    st.subheader("🔀 Compare with Other Entities")
                    
                    comparison_entities = st.multiselect(
                        "Select entities to compare",
                        options=[e for e in entity_names if e != selected_entity_name],
                        help="Compare sentiment trends with other entities"
                    )
                    
                    if comparison_entities:
                        # Get entity IDs
                        comparison_ids = []
                        for name in comparison_entities:
                            entity_obj = session.query(MonitoredEntity).filter_by(name=name).first()
                            if entity_obj:
                                comparison_ids.append(entity_obj.id)
                        
                        if comparison_ids:
                            comparison_ids.append(entity_id)  # Include selected entity
                            
                            comparison_df = analytics.get_entity_comparison(
                                comparison_ids,
                                (start_date, end_date)
                            )
                            
                            if len(comparison_df) > 0:
                                st.dataframe(
                                    comparison_df.style.format({
                                        'avg_sentiment': '{:+.3f}',
                                        'min_sentiment': '{:+.3f}',
                                        'max_sentiment': '{:+.3f}',
                                        'sentiment_stddev': '{:.3f}',
                                        'mention_count': '{:,}',
                                        'total_likes': '{:,}'
                                    }),
                                    use_container_width=True
                                )
                else:
                    st.error(f"Entity '{selected_entity_name}' not found in database.")
    
    except Exception as e:
        st.error(f"Error loading entity deep dive: {str(e)}")
        if st.checkbox("Show error details", key="deep_dive_error"):
            st.exception(e)

# ============================================
# TAB 4: Discovered Entities
# ============================================
with tab4:
    st.header("🆕 Discovered Entities")
    st.write("Entities found by spaCy that aren't in the monitored list")
    
    try:
        min_mentions = st.slider(
            "Minimum mentions",
            min_value=1,
            max_value=50,
            value=5,
            help="Only show entities with at least this many mentions"
        )
        
        reviewed_filter = st.radio(
            "Show",
            options=["Unreviewed only", "All entities"],
            help="Filter by review status"
        )
        
        reviewed = reviewed_filter == "All entities"
        
        discovered_df = analytics.get_discovered_entities(
            min_mentions=min_mentions,
            reviewed=reviewed,
            limit=50
        )
        
        if len(discovered_df) == 0:
            st.info("No discovered entities found. All entities are being tracked!")
        else:
            st.success(f"Found {len(discovered_df)} discovered entities")
            
            # Display table
            display_cols = ['name', 'entity_type', 'mention_count', 'first_seen_at', 'last_seen_at']
            if 'sample_mentions' in discovered_df.columns:
                display_cols.append('sample_mentions')
            
            st.dataframe(
                discovered_df[display_cols].style.format({
                    'mention_count': '{:,}'
                }),
                use_container_width=True,
                height=500
            )
            
            # Download button
            csv = discovered_df.to_csv(index=False)
            st.download_button(
                label="📥 Download as CSV",
                data=csv,
                file_name=f"discovered_entities_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
            
            # Instructions
            st.info(
                "💡 **To add an entity to monitoring**, use the CLI:\n\n"
                "```bash\n"
                "python cli.py add-entity \"Entity Name\" --type person --aliases \"Alias1\" \"Alias2\"\n"
                "```"
            )
    
    except Exception as e:
        st.error(f"Error loading discovered entities: {str(e)}")
        if st.checkbox("Show error details", key="discovered_error"):
            st.exception(e)

# Footer
st.sidebar.markdown("---")
st.sidebar.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
st.sidebar.caption("ET Social Intelligence V2")

