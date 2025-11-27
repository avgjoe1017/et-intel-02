"""
Chart Generator - Creates visualizations for PDF reports.

Uses Matplotlib to generate charts that can be embedded in PDFs.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import tempfile
import io

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.figure import Figure
import pandas as pd

# Nielsen-inspired color palette (locked for consistency)
CHART_COLORS = {
    'positive': '#27ae60',  # Green
    'neutral': '#95a5a6',  # Gray
    'negative': '#e74c3c',  # Red
    'instagram': '#E4405F',  # Instagram pink
    'youtube': '#FF0000',  # YouTube red
    'tiktok': '#000000',  # TikTok black
}


class ChartGenerator:
    """Generates charts for intelligence briefs."""
    
    def __init__(self, output_dir: Optional[Path] = None):
        """
        Initialize chart generator.
        
        Args:
            output_dir: Directory for temporary chart files (uses temp if None)
        """
        self.output_dir = output_dir or Path(tempfile.gettempdir())
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Set style (fallback if seaborn not available)
        try:
            plt.style.use('seaborn-v0_8-darkgrid')
        except:
            try:
                plt.style.use('seaborn-darkgrid')
            except:
                plt.style.use('default')
        matplotlib.rcParams['figure.figsize'] = (8, 5)
        matplotlib.rcParams['font.size'] = 10
    
    def generate_sentiment_trend(
        self,
        entity_data: List[Dict[str, Any]],
        entity_name: str,
        width: float = 8,
        height: float = 4
    ) -> Path:
        """
        Generate sentiment trend line chart for an entity.
        
        Args:
            entity_data: List of dicts with 'date' and 'avg_sentiment' keys
            entity_name: Name of entity for title
            width: Chart width in inches
            height: Chart height in inches
            
        Returns:
            Path to saved chart image
        """
        fig, ax = plt.subplots(figsize=(width, height))
        
        # Prepare data
        df = pd.DataFrame(entity_data)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')
        
        # Plot line
        ax.plot(df['date'], df['avg_sentiment'], 
                marker='o', linewidth=2, markersize=6,
                color='#3498db', label='Sentiment')
        
        # Add zero line
        ax.axhline(y=0, color='#95a5a6', linestyle='--', linewidth=1, alpha=0.5)
        
        # Add reference marks at ±0.3 for scale clarity (Nielsen-style)
        ax.axhline(y=0.3, color=CHART_COLORS['positive'], linestyle=':', linewidth=1, alpha=0.6, label='Positive threshold (+0.3)')
        ax.axhline(y=-0.3, color=CHART_COLORS['negative'], linestyle=':', linewidth=1, alpha=0.6, label='Negative threshold (-0.3)')
        
        # Fill positive/negative areas
        ax.fill_between(df['date'], 0, df['avg_sentiment'],
                        where=(df['avg_sentiment'] >= 0),
                        color=CHART_COLORS['positive'], alpha=0.2, label='Positive')
        ax.fill_between(df['date'], 0, df['avg_sentiment'],
                        where=(df['avg_sentiment'] < 0),
                        color=CHART_COLORS['negative'], alpha=0.2, label='Negative')
        
        # Formatting with scale reference
        ax.set_title(f'Sentiment Trend: {entity_name}', fontsize=14, fontweight='bold', pad=15)
        ax.set_xlabel('Date', fontsize=11)
        ax.set_ylabel('Average Sentiment (-1.0 to +1.0)', fontsize=11)
        ax.set_ylim(-1, 1)
        
        # Add scale reference lines
        ax.axhline(y=0.7, color='green', linestyle=':', linewidth=1, alpha=0.5, label='Strongly Positive (0.7)')
        ax.axhline(y=0.3, color='lightgreen', linestyle=':', linewidth=1, alpha=0.5, label='Positive (0.3)')
        ax.axhline(y=-0.3, color='lightcoral', linestyle=':', linewidth=1, alpha=0.5, label='Negative (-0.3)')
        ax.axhline(y=-0.7, color='red', linestyle=':', linewidth=1, alpha=0.5, label='Strongly Negative (-0.7)')
        
        ax.grid(True, alpha=0.3)
        ax.legend(loc='best', fontsize=8)
        
        # Format x-axis dates
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(df) // 5)))
        plt.xticks(rotation=45, ha='right')
        
        plt.tight_layout()
        
        # Save to temp file
        chart_path = self.output_dir / f"sentiment_trend_{entity_name.replace(' ', '_')}.png"
        fig.savefig(chart_path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        
        return chart_path
    
    def generate_entity_comparison_trend(
        self,
        entities_data: Dict[str, List[Dict[str, Any]]],
        width: float = 8,
        height: float = 5
    ) -> Path:
        """
        Generate comparison trend chart for multiple entities.
        
        Args:
            entities_data: Dict mapping entity names to their trend data
            width: Chart width in inches
            height: Chart height in inches
            
        Returns:
            Path to saved chart image
        """
        fig, ax = plt.subplots(figsize=(width, height))
        
        # Locked entity colors (consistent across all charts)
        entity_colors = {
            # Use consistent palette - assign colors by index for consistency
            'default': ['#3498db', '#e74c3c', '#f39c12', '#9b59b6', '#1abc9c', '#e67e22', '#16a085']
        }
        
        # Use consistent colors for known entities
        entity_color_map = {
            'Blake Lively': '#e74c3c',  # Red (often negative in demo)
            'Taylor Swift': '#3498db',  # Blue (positive)
            'Justin Baldoni': '#e67e22',  # Orange
            'Ryan Reynolds': '#16a085',  # Teal
            'Travis Kelce': '#f39c12',  # Yellow
        }
        
        for idx, (entity_name, data) in enumerate(entities_data.items()):
            df = pd.DataFrame(data)
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
            
            # Use locked color if available, otherwise use default palette
            color = entity_color_map.get(entity_name, entity_colors['default'][idx % len(entity_colors['default'])])
            ax.plot(df['date'], df['avg_sentiment'],
                   marker='o', linewidth=2, markersize=5,
                   color=color, label=entity_name, alpha=0.8)
        
        # Add zero line
        ax.axhline(y=0, color=CHART_COLORS['neutral'], linestyle='--', linewidth=1, alpha=0.5)
        
        # Add reference marks at ±0.3 for scale clarity (Nielsen-style)
        ax.axhline(y=0.3, color=CHART_COLORS['positive'], linestyle=':', linewidth=1.5, alpha=0.7, label='Positive threshold (+0.3)')
        ax.axhline(y=-0.3, color=CHART_COLORS['negative'], linestyle=':', linewidth=1.5, alpha=0.7, label='Negative threshold (-0.3)')
        
        # Formatting with scale reference
        ax.set_title('Entity Sentiment Comparison', fontsize=14, fontweight='bold', pad=15)
        ax.set_xlabel('Date', fontsize=11)
        ax.set_ylabel('Average Sentiment (-1.0 to +1.0)', fontsize=11)
        ax.set_ylim(-1, 1)
        
        # Add additional scale reference lines
        ax.axhline(y=0.7, color=CHART_COLORS['positive'], linestyle=':', linewidth=1, alpha=0.4)
        ax.axhline(y=-0.7, color=CHART_COLORS['negative'], linestyle=':', linewidth=1, alpha=0.4)
        
        ax.grid(True, alpha=0.3)
        ax.legend(loc='best', fontsize=9)
        
        # Format x-axis
        if entities_data:
            first_entity_data = list(entities_data.values())[0]
            df = pd.DataFrame(first_entity_data)
            df['date'] = pd.to_datetime(df['date'])
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(df) // 5)))
        
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        
        # Save
        chart_path = self.output_dir / "entity_comparison_trend.png"
        fig.savefig(chart_path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        
        return chart_path
    
    def generate_sentiment_distribution(
        self,
        distribution: Dict[str, Any],
        width: float = 6,
        height: float = 5
    ) -> Path:
        """
        Generate sentiment distribution pie/bar chart.
        
        Args:
            distribution: Dict with 'positive', 'negative', 'neutral' counts
            width: Chart width in inches
            height: Chart height in inches
            
        Returns:
            Path to saved chart image
        """
        fig, ax = plt.subplots(figsize=(width, height))
        
        labels = ['Positive', 'Neutral', 'Negative']
        sizes = [
            distribution.get('positive', 0),
            distribution.get('neutral', 0),
            distribution.get('negative', 0)
        ]
        colors = [CHART_COLORS['positive'], CHART_COLORS['neutral'], CHART_COLORS['negative']]
        explode = (0.05, 0, 0.05)  # Slight separation
        
        # Create pie chart
        wedges, texts, autotexts = ax.pie(
            sizes, labels=labels, colors=colors, autopct='%1.1f%%',
            startangle=90, explode=explode, shadow=True
        )
        
        # Enhance text
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')
        
        ax.set_title('Sentiment Distribution', fontsize=14, fontweight='bold', pad=15)
        
        plt.tight_layout()
        
        # Save
        chart_path = self.output_dir / "sentiment_distribution.png"
        fig.savefig(chart_path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        
        return chart_path
    
    def generate_platform_comparison(
        self,
        platform_data: List[Dict[str, Any]],
        width: float = 8,
        height: float = 5
    ) -> Path:
        """
        Generate platform comparison chart.
        
        Args:
            platform_data: List of dicts with platform metrics
            width: Chart width in inches
            height: Chart height in inches
            
        Returns:
            Path to saved chart image
        """
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(width, height))
        
        df = pd.DataFrame(platform_data)
        
        # Chart 1: Comment volume
        platforms = df['platform'].str.title()
        volumes = df['comment_count']
        # Locked platform colors (consistent across all charts)
        platform_color_map = {
            'Instagram': CHART_COLORS['instagram'],
            'Youtube': CHART_COLORS['youtube'],
            'Tiktok': CHART_COLORS['tiktok'],
        }
        
        # Use locked colors for platforms
        bar_colors = [platform_color_map.get(p, CHART_COLORS['neutral']) for p in platforms]
        bars1 = ax1.bar(platforms, volumes, color=bar_colors, alpha=0.8)
        ax1.set_title('Comment Volume by Platform', fontsize=12, fontweight='bold')
        ax1.set_ylabel('Number of Comments', fontsize=10)
        ax1.tick_params(axis='x', rotation=45)
        
        # Add value labels on bars
        for bar in bars1:
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height,
                    f'{int(height):,}',
                    ha='center', va='bottom', fontsize=9)
        
        # Chart 2: Sentiment comparison (use locked sentiment colors)
        sentiments = df['avg_sentiment']
        colors_sent = [
            CHART_COLORS['positive'] if s > 0.3 
            else CHART_COLORS['negative'] if s < -0.3 
            else CHART_COLORS['neutral'] 
            for s in sentiments
        ]
        
        bars2 = ax2.bar(platforms, sentiments, color=colors_sent, alpha=0.8)
        ax2.axhline(y=0, color='black', linestyle='-', linewidth=0.8)
        ax2.set_title('Average Sentiment by Platform', fontsize=12, fontweight='bold')
        ax2.set_ylabel('Average Sentiment', fontsize=10)
        ax2.set_ylim(-1, 1)
        ax2.tick_params(axis='x', rotation=45)
        
        # Add value labels
        for bar in bars2:
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:+.2f}',
                    ha='center', va='bottom' if height > 0 else 'top', fontsize=9)
        
        plt.tight_layout()
        
        # Save
        chart_path = self.output_dir / "platform_comparison.png"
        fig.savefig(chart_path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        
        return chart_path
    
    def generate_risk_radar(
        self,
        entity_data: List[Dict[str, Any]],
        width: float = 6,
        height: float = 6
    ) -> Path:
        """
        Generate risk radar chart (volume vs sentiment quadrant).
        
        Args:
            entity_data: List of dicts with entity metrics
            width: Chart width in inches
            height: Chart height in inches
            
        Returns:
            Path to saved chart image
        """
        fig, ax = plt.subplots(figsize=(width, height))
        
        df = pd.DataFrame(entity_data)
        
        # Create scatter plot
        scatter = ax.scatter(
            df['avg_sentiment'],
            df['mention_count'],
            s=df['total_likes'] / 10,  # Size by likes
            alpha=0.6,
            c=df['avg_sentiment'],
            cmap='RdYlGn',
            edgecolors='black',
            linewidths=1
        )
        
        # Add quadrant lines
        ax.axvline(x=0, color='gray', linestyle='--', linewidth=1, alpha=0.5)
        ax.axhline(y=df['mention_count'].median(), color='gray', linestyle='--', linewidth=1, alpha=0.5)
        
        # Add quadrant labels
        ax.text(0.5, 0.95, 'High Volume\nPositive', transform=ax.transAxes,
               ha='center', va='top', fontsize=10, fontweight='bold',
               bbox=dict(boxstyle='round', facecolor='#d5f4e6', alpha=0.5))
        ax.text(0.5, 0.05, 'High Volume\nNegative', transform=ax.transAxes,
               ha='center', va='bottom', fontsize=10, fontweight='bold',
               bbox=dict(boxstyle='round', facecolor='#ffe5e5', alpha=0.5))
        
        # Add entity labels for top entities
        for idx, row in df.head(5).iterrows():
            ax.annotate(
                row['entity_name'],
                (row['avg_sentiment'], row['mention_count']),
                fontsize=8,
                alpha=0.8
            )
        
        # Formatting with scale reference
        ax.set_title('Risk Radar: Volume vs Sentiment', fontsize=14, fontweight='bold', pad=15)
        ax.set_xlabel('Average Sentiment (-1.0 to +1.0)', fontsize=11)
        ax.set_ylabel('Mention Count', fontsize=11)
        ax.set_xlim(-1, 1)
        
        # Add scale reference lines
        ax.axvline(x=0.7, color='green', linestyle=':', linewidth=1, alpha=0.5)
        ax.axvline(x=0.3, color='lightgreen', linestyle=':', linewidth=1, alpha=0.5)
        ax.axvline(x=-0.3, color='lightcoral', linestyle=':', linewidth=1, alpha=0.5)
        ax.axvline(x=-0.7, color='red', linestyle=':', linewidth=1, alpha=0.5)
        
        ax.grid(True, alpha=0.3)
        
        # Add colorbar
        cbar = plt.colorbar(scatter, ax=ax)
        cbar.set_label('Sentiment Score', fontsize=9)
        
        plt.tight_layout()
        
        # Save
        chart_path = self.output_dir / "risk_radar.png"
        fig.savefig(chart_path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        
        return chart_path

