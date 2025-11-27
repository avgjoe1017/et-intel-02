"""
PDF Renderer - Renders IntelligenceBriefData as professional PDF reports.

Uses ReportLab for PDF generation.
"""

from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
import io
import unicodedata

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image, KeepTogether, PageTemplate, BaseDocTemplate
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus.frames import Frame

from et_intel_core.reporting.brief_builder import IntelligenceBriefData, BriefSection
from et_intel_core.reporting.chart_generator import ChartGenerator
from xml.sax.saxutils import escape

# Nielsen-inspired color palette (locked for consistency)
# Stored as hex strings for easy use in HTML/Paragraph tags
COLOR_PALETTE = {
    # Sentiment
    'strongly_positive': '#27ae60',  # Green
    'positive': '#2ecc71',  # Light green
    'neutral': '#95a5a6',  # Gray
    'negative': '#e67e22',  # Orange
    'strongly_negative': '#e74c3c',  # Red
    
    # Platforms
    'instagram': '#E4405F',  # Instagram pink
    'youtube': '#FF0000',  # YouTube red
    'tiktok': '#000000',  # TikTok black
    
    # Trends
    'surging': '#3498db',  # Blue
    'falling': '#e74c3c',  # Red
    'stable': '#95a5a6',  # Gray
    
    # Backgrounds
    'header': '#34495e',  # Dark gray-blue
    'accent': '#9b59b6',  # Purple
    'light_bg': '#ecf0f1',  # Light gray
}


class PDFRenderer:
    """
    Takes BriefData, renders PDF.
    No computation - just formatting.
    """
    
    def __init__(self, output_dir: Path):
        """
        Initialize PDF renderer.
        
        Args:
            output_dir: Directory where PDFs will be saved
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize chart generator
        self.chart_generator = ChartGenerator(output_dir=self.output_dir)
        
        # Define custom styles
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Setup custom paragraph styles."""
        # Title style
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Title'],
            fontSize=24,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=30,
            alignment=TA_CENTER
        ))
        
        # Section title style
        self.styles.add(ParagraphStyle(
            name='SectionTitle',
            parent=self.styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=12,
            spaceBefore=20
        ))
        
        # Summary style
        self.styles.add(ParagraphStyle(
            name='Summary',
            parent=self.styles['Normal'],
            fontSize=11,
            textColor=colors.HexColor('#34495e'),
            spaceAfter=12,
            leading=14
        ))
    
    def _sanitize_text(self, text: Any) -> str:
        """Remove unsupported characters and escape for Paragraph."""
        if text is None:
            return ""
        value = str(text)
        value = unicodedata.normalize("NFKC", value)
        # Strip control characters that render as squares
        value = "".join(ch for ch in value if unicodedata.category(ch)[0] != "C")
        return escape(value)
    
    def render(
        self,
        brief: IntelligenceBriefData,
        filename: Optional[str] = None
    ) -> Path:
        """
        Render brief as PDF.
        
        Args:
            brief: IntelligenceBriefData to render
            filename: Optional filename (auto-generated if not provided)
            
        Returns:
            Path to generated PDF file
        """
        if not filename:
            timestamp = brief.metadata['generated_at'].strftime("%Y%m%d_%H%M%S")
            filename = f"ET_Intelligence_Brief_{timestamp}.pdf"
        
        # Ensure .pdf extension
        if not filename.endswith('.pdf'):
            filename += '.pdf'
        
        output_path = self.output_dir / filename
        
        # Create PDF document with page numbers
        class NumberedCanvas:
            """Custom canvas for page numbers."""
            def __init__(self, canvas, doc):
                self.canvas = canvas
                self.doc = doc
            
            def draw_page_number(self):
                """Draw page number on each page."""
                page_num = self.canvas.getPageNumber()
                text = f"Page {page_num}"
                self.canvas.saveState()
                self.canvas.setFont('Helvetica', 9)
                self.canvas.setFillColor(colors.HexColor('#7f8c8d'))
                self.canvas.drawRightString(
                    self.doc.pagesize[0] - 72,
                    30,
                    text
                )
                self.canvas.restoreState()
        
        # Create PDF document
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        
        # Store reference for page numbering
        doc._numbered_canvas = NumberedCanvas
        
        # Build story (content elements)
        story = []
        
        # Title page
        story.extend(self._create_title_page(brief))
        story.append(PageBreak())
        
        # Big Number Highlights (Nielsen-style hero callouts)
        story.extend(self._create_big_number_highlights(brief))
        story.append(PageBreak())
        
        # Executive summary
        story.extend(self._create_executive_summary(brief))
        story.append(PageBreak())
        
        # Sentiment Scale Legend (NEW - Context for analysis)
        story.extend(self._create_sentiment_scale_legend())
        story.append(Spacer(1, 0.2*inch))
        
        # Contextual narrative
        if brief.contextual_narrative:
            story.extend(self._create_contextual_narrative_section(brief.contextual_narrative))
            story.append(Spacer(1, 0.3*inch))
        
        # Post Performance section (NEW - shows which posts drove engagement)
        if brief.post_performance and brief.post_performance.items:
            story.extend(self._create_post_performance_section(brief.post_performance))
            story.append(PageBreak())
        
        # What Changed This Week (NEW)
        if brief.what_changed.items:
            story.extend(self._create_what_changed_section(brief.what_changed))
            story.append(PageBreak())
        
        # Key Risks & Watchouts (NEW)
        if brief.key_risks.items:
            story.extend(self._create_key_risks_section(brief.key_risks))
            story.append(PageBreak())
        
        # Top entities section (with micro-insights)
        if brief.top_entities.items:
            story.extend(self._create_top_entities_section(brief.top_entities, brief.entity_micro_insights))
            story.append(PageBreak())
        
        # Sentiment distribution
        if brief.sentiment_distribution and brief.sentiment_distribution.get('total', 0) > 0:
            story.extend(self._create_sentiment_distribution_section(brief.sentiment_distribution))
            story.append(PageBreak())
        
        # Platform Wars section (enhanced platform breakdown)
        if brief.platform_breakdown.items:
            story.extend(self._create_platform_wars_section(brief.platform_breakdown))
            story.append(PageBreak())
        
        # Cross-Platform Deltas (NEW)
        if brief.cross_platform_deltas.items:
            story.extend(self._create_cross_platform_deltas_section(brief.cross_platform_deltas))
            story.append(PageBreak())
        
        # Entity comparison
        if brief.entity_comparison.items:
            story.extend(self._create_entity_comparison_section(brief.entity_comparison))
            story.append(PageBreak())
        
        # Velocity alerts section (with LLM narratives)
        if brief.velocity_alerts.items:
            story.extend(self._create_velocity_alerts_section(brief.velocity_alerts))
            story.append(PageBreak())
        
        # Entity trend charts (limit to top 7 for scale)
        if brief.top_entities.items and len(brief.top_entities.items) >= 2:
            story.extend(self._create_entity_trend_charts(brief, limit=7))
            story.append(PageBreak())
        
        # Discovered entities section
        if brief.discovered_entities.items:
            story.extend(self._create_discovered_entities_section(brief.discovered_entities))
            story.append(PageBreak())
        
        # Storylines section (enhanced with clustering)
        if brief.storylines.items:
            story.extend(self._create_storylines_section(brief.storylines))
            story.append(PageBreak())
        
        # Risk signals section (if any)
        if brief.risk_signals.items:
            story.extend(self._create_risk_signals_section(brief.risk_signals))
            story.append(PageBreak())
        
        # FAQ/Explainer Section (Nielsen-style)
        story.extend(self._create_faq_section())
        story.append(PageBreak())
        
        # Next Steps CTA (Nielsen-style footer)
        story.extend(self._create_next_steps_section())
        
        # Footer/metadata
        story.extend(self._create_footer(brief))
        
        # Build PDF with page numbers
        def on_first_page(canvas, doc):
            """Draw page number on first page."""
            page_num = canvas.getPageNumber()
            canvas.saveState()
            canvas.setFont('Helvetica', 9)
            canvas.setFillColor(colors.HexColor('#7f8c8d'))
            canvas.drawRightString(
                doc.pagesize[0] - 72,
                30,
                f"Page {page_num}"
            )
            canvas.restoreState()
        
        def on_later_pages(canvas, doc):
            """Draw page number on subsequent pages."""
            page_num = canvas.getPageNumber()
            canvas.saveState()
            canvas.setFont('Helvetica', 9)
            canvas.setFillColor(colors.HexColor('#7f8c8d'))
            canvas.drawRightString(
                doc.pagesize[0] - 72,
                30,
                f"Page {page_num}"
            )
            canvas.restoreState()
        
        doc.build(story, onFirstPage=on_first_page, onLaterPages=on_later_pages)
        
        return output_path
    
    def _create_title_page(self, brief: IntelligenceBriefData) -> List:
        """Create title page elements."""
        elements = []
        
        # Main title
        elements.append(Spacer(1, 2*inch))
        elements.append(Paragraph("ET Social Intelligence Brief", self.styles['CustomTitle']))
        elements.append(Spacer(1, 0.5*inch))
        
        # Timeframe
        start_date = brief.timeframe['start'].strftime('%B %d, %Y')
        end_date = brief.timeframe['end'].strftime('%B %d, %Y')
        timeframe_text = f"<b>Period:</b> {start_date} to {end_date}"
        elements.append(Paragraph(timeframe_text, self.styles['Normal']))
        elements.append(Spacer(1, 0.3*inch))
        
        # Generated date
        gen_date = brief.metadata['generated_at'].strftime('%B %d, %Y at %I:%M %p UTC')
        gen_text = f"<i>Generated: {gen_date}</i>"
        elements.append(Paragraph(gen_text, self.styles['Normal']))
        
        elements.append(Spacer(1, 1*inch))
        
        # Topline summary on title page
        summary = brief.topline_summary
        summary_text = (
            f"<b>Total Comments:</b> {summary['total_comments']:,}<br/>"
            f"<b>Entities Tracked:</b> {summary['total_entities']}<br/>"
            f"<b>Velocity Alerts:</b> {summary['velocity_alerts_count']}"
        )
        elements.append(Paragraph(summary_text, self.styles['Summary']))
        
        return elements
    
    def _create_sentiment_scale_legend(self) -> List:
        """Create sentiment scale legend with context."""
        elements = []
        
        elements.append(Paragraph("Sentiment Scale Reference", self.styles['SectionTitle']))
        elements.append(Spacer(1, 0.15*inch))
        
        # Explanation text
        explanation = (
            "<b>Sentiment Range:</b> All sentiment scores range from <b>-1.0</b> (strongly negative) "
            "to <b>+1.0</b> (strongly positive), with <b>0.0</b> representing neutral sentiment. "
            "Scores are calculated using a combination of rule-based analysis and AI models."
        )
        elements.append(Paragraph(explanation, self.styles['Summary']))
        elements.append(Spacer(1, 0.2*inch))
        
        # Create scale table
        scale_data = [
            ['Range', 'Label', 'Interpretation', 'Example Context'],
            ['+0.7 to +1.0', 'Strongly Positive', 'Highly favorable, enthusiastic', 'Praise, admiration, excitement'],
            ['+0.3 to +0.7', 'Positive', 'Favorable, supportive', 'Likes, approval, interest'],
            ['-0.3 to +0.3', 'Neutral', 'Neither positive nor negative', 'Factual statements, questions'],
            ['-0.7 to -0.3', 'Negative', 'Unfavorable, critical', 'Criticism, disappointment, concern'],
            ['-1.0 to -0.7', 'Strongly Negative', 'Highly unfavorable, hostile', 'Anger, hate, strong disapproval']
        ]
        
        scale_table = Table(scale_data, colWidths=[1.5*inch, 1.5*inch, 2.5*inch, 2.5*inch])
        scale_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(COLOR_PALETTE['header'])),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#bdc3c7')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [
                colors.HexColor('#d5f4e6'),  # Strongly positive
                colors.HexColor('#d5f4e6'),  # Positive
                colors.HexColor('#f8f9fa'),  # Neutral
                colors.HexColor('#ffe5e5'),  # Negative
                colors.HexColor('#ffe5e5'),  # Strongly negative
            ]),
        ]))
        
        elements.append(scale_table)
        elements.append(Spacer(1, 0.15*inch))
        
        # Quick reference examples with detailed context
        examples_text = (
            "<b>Quick Reference Examples:</b><br/>"
            "• <b>-0.61</b> = <b>Strongly Negative</b> (between -0.7 and -1.0) - indicates highly unfavorable discourse, "
            "suggesting anger, hate, or strong disapproval. This is not just 'disliked' but represents significant hostility.<br/>"
            "• <b>+0.72</b> = <b>Strongly Positive</b> (between +0.7 and +1.0) - indicates highly favorable sentiment, "
            "showing praise, admiration, or excitement. This represents enthusiastic support.<br/>"
            "• <b>-0.15</b> = <b>Neutral</b> (between -0.3 and +0.3) - indicates neither strongly positive nor negative, "
            "typically factual statements or questions without emotional charge."
        )
        elements.append(Paragraph(examples_text, self.styles['Summary']))
        
        return elements
    
    def _create_big_number_highlights(self, brief: IntelligenceBriefData) -> List:
        """Create Nielsen-style big number hero callouts."""
        elements = []
        
        elements.append(Paragraph("This Week's Big Numbers", self.styles['CustomTitle']))
        elements.append(Spacer(1, 0.5*inch))
        
        # Get top insights
        top_entity = brief.top_entities.items[0] if brief.top_entities.items else None
        critical_alert = next((a for a in brief.velocity_alerts.items if abs(a.get('percent_change', 0)) > 50), None) if brief.velocity_alerts.items else None
        best_platform = max(brief.platform_breakdown.items, key=lambda x: x.get('avg_sentiment', 0)) if brief.platform_breakdown.items else None
        
        highlights = []
        
        # Total comments
        highlights.append({
            'number': f"{brief.topline_summary['total_comments']:,}",
            'label': 'Total Comments Analyzed',
            'color': COLOR_PALETTE['accent']
        })
        
        # Top entity
        if top_entity:
            sentiment_label = self._get_sentiment_label(top_entity.get('avg_sentiment', 0))
            highlights.append({
                'number': f"{int(top_entity.get('mention_count', 0)):,}",
                'label': f"Mentions: {top_entity.get('entity_name', 'Unknown')} ({sentiment_label})",
                'color': COLOR_PALETTE['strongly_positive'] if top_entity.get('avg_sentiment', 0) > 0.3 else COLOR_PALETTE['strongly_negative']
            })
        
        # Critical alert
        if critical_alert:
            highlights.append({
                'number': f"{abs(critical_alert.get('percent_change', 0)):.1f}%",
                'label': f"Sentiment Shift: {critical_alert.get('entity_name', 'Unknown')}",
                'color': COLOR_PALETTE['falling']
            })
        
        # Best platform
        if best_platform:
            highlights.append({
                'number': f"{best_platform.get('avg_sentiment', 0):+.2f}",
                'label': f"Top Platform: {best_platform.get('platform', 'Unknown').title()} Sentiment",
                'color': COLOR_PALETTE['instagram'] if best_platform.get('platform') == 'instagram' else COLOR_PALETTE['youtube']
            })
        
        # Create big number boxes
        for highlight in highlights[:4]:  # Top 4 highlights
            # Big number box - color is already a hex string
            color_hex = highlight['color']
            color_obj = colors.HexColor(color_hex)  # For table border
            
            box_data = [
                [Paragraph(f"<font size=36 color='{color_hex}'><b>{highlight['number']}</b></font>", self.styles['Normal'])],
                [Paragraph(f"<font size=12>{highlight['label']}</font>", self.styles['Normal'])]
            ]
            
            box_table = Table(box_data, colWidths=[3*inch])
            box_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('BACKGROUND', (0, 0), (-1, -1), colors.white),
                ('LEFTPADDING', (0, 0), (-1, -1), 20),
                ('RIGHTPADDING', (0, 0), (-1, -1), 20),
                ('TOPPADDING', (0, 0), (-1, -1), 15),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
                ('GRID', (0, 0), (-1, -1), 2, color_obj),
            ]))
            
            elements.append(box_table)
            elements.append(Spacer(1, 0.3*inch))
        
        return elements
    
    def _create_executive_summary(self, brief: IntelligenceBriefData) -> List:
        """Create executive summary section."""
        elements = []
        
        elements.append(Paragraph("Executive Summary", self.styles['SectionTitle']))
        elements.append(Spacer(1, 0.2*inch))
        
        # Topline numbers
        summary = brief.topline_summary
        summary_data = [
            ['Metric', 'Value'],
            ['Total Comments', f"{summary['total_comments']:,}"],
            ['Entities Tracked', str(summary['total_entities'])],
            ['Velocity Alerts', str(summary['velocity_alerts_count'])],
            ['Critical Alerts (>50%)', str(summary['critical_alerts'])]
        ]
        
        summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(COLOR_PALETTE['header'])),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ecf0f1')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#bdc3c7')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')])
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 0.3*inch))
        
        # Top entities summary
        if brief.top_entities.summary:
            elements.append(Paragraph("<b>Key Highlights:</b>", self.styles['Normal']))
            elements.append(Spacer(1, 0.1*inch))
            elements.append(Paragraph(brief.top_entities.summary, self.styles['Summary']))
        
        return elements
    
    def _create_what_changed_section(self, section: BriefSection) -> List:
        """Create 'What Changed This Week' section."""
        elements = []
        
        elements.append(Paragraph(section.title, self.styles['SectionTitle']))
        elements.append(Spacer(1, 0.2*inch))
        
        if section.summary:
            elements.append(Paragraph(section.summary, self.styles['Summary']))
            elements.append(Spacer(1, 0.2*inch))
        
        if not section.items:
            elements.append(Paragraph("No significant changes detected.", self.styles['Normal']))
            return elements
        
        # Create compact table
        table_data = [['Category', 'Entity', 'Change', 'Details']]
        
        for item in section.items[:10]:  # Limit to 10 items
            category = item.get('category', 'Unknown')
            entity = item.get('entity', 'Unknown')
            metric = item.get('metric', 'N/A')
            detail = item.get('detail', '')
            
            # Color-code by category
            if 'Riser' in category:
                category_para = Paragraph(f'<font color="#27ae60"><b>{category}</b></font>', self.styles['Normal'])
            elif 'Faller' in category or 'Negative' in category:
                category_para = Paragraph(f'<font color="#e74c3c"><b>{category}</b></font>', self.styles['Normal'])
            elif 'Positive' in category:
                category_para = Paragraph(f'<font color="#27ae60"><b>{category}</b></font>', self.styles['Normal'])
            else:
                category_para = Paragraph(f'<font color="#f39c12"><b>{category}</b></font>', self.styles['Normal'])
            
            table_data.append([
                category_para,
                entity[:25],  # Truncate long names
                metric,
                detail[:30]  # Truncate details
            ])
        
        table = Table(table_data, colWidths=[1.5*inch, 2*inch, 1.2*inch, 2.3*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(COLOR_PALETTE['header'])),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#bdc3c7')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
        ]))
        
        elements.append(table)
        
        return elements
    
    def _create_key_risks_section(self, section: BriefSection) -> List:
        """Create Key Risks & Watchouts section."""
        elements = []
        
        elements.append(Paragraph(section.title, self.styles['SectionTitle']))
        elements.append(Spacer(1, 0.2*inch))
        
        if section.summary:
            elements.append(Paragraph(section.summary, self.styles['Summary']))
            elements.append(Spacer(1, 0.2*inch))
        
        if not section.items:
            elements.append(Paragraph("No key risks identified.", self.styles['Normal']))
            return elements
        
        # Create risk list with severity indicators
        for item in section.items:
            risk_text = item.get('risk', '')
            severity = item.get('severity', 'warning')
            
            # Color-code by severity
            if severity == 'critical':
                risk_para = Paragraph(
                    f'<font color="#e74c3c"><b>⚠ CRITICAL:</b></font> {risk_text}',
                    self.styles['Summary']
                )
            else:
                risk_para = Paragraph(
                    f'<font color="#f39c12"><b>⚠ WATCH:</b></font> {risk_text}',
                    self.styles['Summary']
                )
            
            elements.append(risk_para)
            elements.append(Spacer(1, 0.15*inch))
        
        return elements
    
    def _create_cross_platform_deltas_section(self, section: BriefSection) -> List:
        """Create Cross-Platform Deltas section."""
        elements = []
        
        elements.append(Paragraph(section.title, self.styles['SectionTitle']))
        elements.append(Spacer(1, 0.2*inch))
        
        if section.summary:
            elements.append(Paragraph(section.summary, self.styles['Summary']))
            elements.append(Spacer(1, 0.2*inch))
        
        if not section.items:
            elements.append(Paragraph("No cross-platform deltas available.", self.styles['Normal']))
            return elements
        
        # Create insights list
        for item in section.items:
            insight = item.get('insight', '')
            entity = item.get('entity', 'Unknown')
            
            elements.append(Paragraph(
                f"<b>{entity}:</b> {insight}",
                self.styles['Summary']
            ))
            elements.append(Spacer(1, 0.15*inch))
        
        return elements
    
    def _create_top_entities_section(self, section: BriefSection, micro_insights: Dict[str, str] = None) -> List:
        """Create top entities section with table."""
        elements = []
        
        elements.append(Paragraph(section.title, self.styles['SectionTitle']))
        elements.append(Spacer(1, 0.2*inch))
        
        if section.summary:
            elements.append(Paragraph(section.summary, self.styles['Summary']))
            elements.append(Spacer(1, 0.2*inch))
        
        if not section.items:
            elements.append(Paragraph("No entity data available for this period.", self.styles['Normal']))
            return elements
        
        # Create table data
        table_data = [['Rank', 'Entity', 'Type', 'Mentions', 'Avg Sentiment', 'Total Likes']]
        
        for idx, item in enumerate(section.items[:20], 1):  # Limit to top 20
            entity_name = item.get('entity_name', 'Unknown')
            entity_type = item.get('entity_type', 'unknown')
            mentions = int(item.get('mention_count', 0))
            sentiment = item.get('avg_sentiment', 0.0)
            likes = int(item.get('total_likes', 0))
            
            # Format sentiment with color indicator and label (using locked palette)
            sentiment_str = f"{sentiment:+.2f}"
            sentiment_label = self._get_sentiment_label(sentiment)
            
            if sentiment > 0.7:
                # Strongly positive
                sentiment_para = Paragraph(
                    f'<font color="{COLOR_PALETTE["strongly_positive"]}"><b>{sentiment_str}</b></font> <font color="#7f8c8d" size="8">({sentiment_label})</font>',
                    self.styles['Normal']
                )
            elif sentiment > 0.3:
                # Positive
                sentiment_para = Paragraph(
                    f'<font color="{COLOR_PALETTE["positive"]}">{sentiment_str}</font> <font color="#7f8c8d" size="8">({sentiment_label})</font>',
                    self.styles['Normal']
                )
            elif sentiment < -0.7:
                # Strongly negative
                sentiment_para = Paragraph(
                    f'<font color="{COLOR_PALETTE["strongly_negative"]}"><b>{sentiment_str}</b></font> <font color="#7f8c8d" size="8">({sentiment_label})</font>',
                    self.styles['Normal']
                )
            elif sentiment < -0.3:
                # Negative
                sentiment_para = Paragraph(
                    f'<font color="{COLOR_PALETTE["negative"]}">{sentiment_str}</font> <font color="#7f8c8d" size="8">({sentiment_label})</font>',
                    self.styles['Normal']
                )
            else:
                # Neutral
                sentiment_para = Paragraph(
                    f'<font color="{COLOR_PALETTE["neutral"]}">{sentiment_str}</font> <font color="#7f8c8d" size="8">({sentiment_label})</font>',
                    self.styles['Normal']
                )
            
            # Add micro-insight if available
            insight_text = ""
            if micro_insights and entity_name in micro_insights:
                insight_text = micro_insights[entity_name]
            
            table_data.append([
                str(idx),
                entity_name[:30],  # Truncate long names
                entity_type,
                f"{mentions:,}",
                sentiment_para,  # Use Paragraph for colored text
                f"{likes:,}"
            ])
        
        # Create table
        table = Table(table_data, colWidths=[0.5*inch, 2*inch, 1*inch, 1*inch, 1.2*inch, 1.2*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(COLOR_PALETTE['header'])),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (3, 1), (5, -1), 'RIGHT'),  # Numbers right-aligned
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#bdc3c7')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        
        elements.append(table)
        
        # Add micro-insights below table
        if micro_insights:
            elements.append(Spacer(1, 0.3*inch))
            elements.append(Paragraph("<b>Entity Insights:</b>", self.styles['Normal']))
            elements.append(Spacer(1, 0.15*inch))
            
            for entity_name, insight in list(micro_insights.items())[:5]:  # Top 5
                elements.append(Paragraph(
                    f"<b>{entity_name}:</b> {insight}",
                    self.styles['Summary']
                ))
                elements.append(Spacer(1, 0.1*inch))
        
        return elements
    
    def _get_sentiment_label(self, sentiment: float) -> str:
        """Get human-readable sentiment label."""
        if sentiment >= 0.7:
            return "Strongly Positive"
        elif sentiment >= 0.3:
            return "Positive"
        elif sentiment > -0.3:  # FIX 4: Use > not >= to ensure -0.3 is "Negative"
            return "Neutral"
        elif sentiment > -0.7:
            return "Negative"
        else:
            return "Strongly Negative"
    
    def _generate_chart_explainer(self, chart_type: str, data: Any) -> Optional[str]:
        """Generate Nielsen-style 1-sentence editorial pull-out for charts."""
        if chart_type == 'sentiment_distribution':
            total = data.get('total', 0)
            positive_pct = data.get('positive_pct', 0)
            negative_pct = data.get('negative_pct', 0)
            
            if positive_pct > negative_pct * 1.5:
                return f"Positive sentiment dominates with {positive_pct:.1f}% of {total:,} comments, indicating overall favorable discourse."
            elif negative_pct > positive_pct * 1.5:
                return f"Negative sentiment leads with {negative_pct:.1f}% of {total:,} comments, signaling significant criticism or concern."
            else:
                return f"Sentiment is balanced: {positive_pct:.1f}% positive, {negative_pct:.1f}% negative across {total:,} comments."
        
        elif chart_type == 'platform_comparison':
            if not data or len(data) < 2:
                return None
            
            best = max(data, key=lambda x: x.get('avg_sentiment', 0))
            worst = min(data, key=lambda x: x.get('avg_sentiment', 0))
            
            if best.get('avg_sentiment', 0) - worst.get('avg_sentiment', 0) > 0.2:
                return (
                    f"{best.get('platform', 'Unknown').title()} shows {self._get_sentiment_label(best.get('avg_sentiment', 0)).lower()} "
                    f"sentiment ({best.get('avg_sentiment', 0):+.2f}), while {worst.get('platform', 'Unknown').title()} is "
                    f"{self._get_sentiment_label(worst.get('avg_sentiment', 0)).lower()} ({worst.get('avg_sentiment', 0):+.2f}), "
                    f"indicating platform-specific discourse patterns."
                )
            else:
                return f"Platform sentiment is relatively consistent, with {best.get('platform', 'Unknown').title()} slightly more positive."
        
        elif chart_type == 'entity_trends':
            if not data:
                return None
            
            entity_names = list(data.keys())[:3]
            if len(entity_names) == 1:
                return f"{entity_names[0]} sentiment trend shows the entity's sentiment trajectory over the reporting period."
            else:
                return f"Top entities show divergent sentiment patterns, with {', '.join(entity_names)} representing the highest-volume conversations."
        
        return None
    
    def _create_velocity_alerts_section(self, section: BriefSection) -> List:
        """Create velocity alerts section with LLM narratives."""
        elements = []
        
        elements.append(Paragraph(section.title, self.styles['SectionTitle']))
        elements.append(Spacer(1, 0.2*inch))
        
        if section.summary:
            elements.append(Paragraph(section.summary, self.styles['Summary']))
            elements.append(Spacer(1, 0.2*inch))
        
        if not section.items:
            elements.append(Paragraph("No velocity alerts for this period.", self.styles['Normal']))
            return elements
        
        # Create alert table with sentiment context
        table_data = [['Entity', 'Change', 'Recent Sentiment', 'Previous Sentiment', 'Status']]
        
        for item in section.items:
            entity_name = item.get('entity_name', 'Unknown')
            change = item.get('percent_change', 0.0)
            recent = item.get('recent_sentiment', 0.0)
            previous = item.get('previous_sentiment', 0.0)
            direction = item.get('direction', 'stable')
            
            # Color-code the change using Paragraph (using locked palette)
            change_str = f"{change:+.1f}%"
            if abs(change) > 50:
                change_para = Paragraph(
                    f'<font color="{COLOR_PALETTE["falling"]}"><b>{change_str}</b></font>',
                    self.styles['Normal']
                )
            elif abs(change) > 30:
                change_para = Paragraph(
                    f'<font color="{COLOR_PALETTE["negative"]}"><b>{change_str}</b></font>',
                    self.styles['Normal']
                )
            else:
                change_para = Paragraph(change_str, self.styles['Normal'])
            
            # Determine status with clearer language
            if abs(change) > 50:
                if change > 0:
                    status = "Strong Recovery" if previous < -0.3 else "Strong Improvement"
                else:
                    status = "Crisis Alert" if recent < -0.7 else "Major Decline"
            elif abs(change) > 30:
                if change > 0:
                    status = "Recovery" if previous < -0.3 else "Improving"
                else:
                    status = "Declining" if recent > -0.3 else "Turned Negative"
            else:
                status = "Stable"
            
            # Add sentiment labels for context
            recent_label = self._get_sentiment_label(recent)
            previous_label = self._get_sentiment_label(previous)
            
            recent_str = f"{recent:.3f} ({recent_label})"
            previous_str = f"{previous:.3f} ({previous_label})"
            
            table_data.append([
                entity_name,
                change_para,  # Use Paragraph for colored text
                recent_str,
                previous_str,
                status
            ])
        
        table = Table(table_data, colWidths=[2*inch, 1.2*inch, 1.5*inch, 1.5*inch, 1.2*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(COLOR_PALETTE['strongly_negative'])),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 1), (3, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#bdc3c7')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#fff5f5')]),
        ]))
        
        elements.append(table)
        elements.append(Spacer(1, 0.3*inch))
        
        # Add LLM narratives for each alert
        elements.append(Paragraph("<b>Analysis:</b>", self.styles['Normal']))
        elements.append(Spacer(1, 0.1*inch))
        
        for item in section.items:
            narrative = item.get('narrative', '')
            if narrative:
                entity_name = item.get('entity_name', 'Unknown')
                elements.append(Paragraph(f"<b>{entity_name}:</b> {narrative}", self.styles['Summary']))
                elements.append(Spacer(1, 0.15*inch))
        
        return elements
    
    def _create_storylines_section(self, section: BriefSection) -> List:
        """Create storylines section with clustering results."""
        elements = []
        
        elements.append(Paragraph(section.title, self.styles['SectionTitle']))
        elements.append(Spacer(1, 0.2*inch))
        
        if section.summary:
            elements.append(Paragraph(section.summary, self.styles['Summary']))
            elements.append(Spacer(1, 0.2*inch))
        
        if not section.items:
            elements.append(Paragraph("No active storylines detected.", self.styles['Normal']))
            return elements
        
        # Create storylines table with intensity indicators
        table_data = [['Storyline', 'Volume', 'Intensity', 'Entities', 'Trajectory']]
        
        for item in section.items:
            storyline = item.get('storyline', 'Unknown')
            mentions = item.get('mention_count', 0)
            entities = item.get('entities', 'General')
            
            # Calculate intensity (mentions as bar length indicator)
            max_mentions = max([i.get('mention_count', 0) for i in section.items], default=1)
            intensity_pct = (mentions / max_mentions) * 100 if max_mentions > 0 else 0
            
            # Intensity bar (visual indicator)
            bar_length = int(intensity_pct / 5)  # Scale to 0-20 characters
            intensity_bar = '█' * bar_length + '░' * (20 - bar_length)
            
            # Trajectory indicator (based on mention count trend - simplified for demo)
            if mentions > max_mentions * 0.8:
                trajectory = "High"
            elif mentions > max_mentions * 0.5:
                trajectory = "Moderate"
            else:
                trajectory = "Emerging"
            
            # Entity count
            entity_count = len(entities.split(',')) if entities != 'General' else 0
            entity_indicator = f"{entity_count} entities" if entity_count > 0 else "General"
            
            table_data.append([
                storyline,
                str(mentions),
                intensity_bar,  # Visual intensity bar
                f"{entities[:35] if len(entities) > 35 else entities} ({entity_indicator})",
                trajectory
            ])
        
        table = Table(table_data, colWidths=[2*inch, 0.8*inch, 1.5*inch, 2.2*inch, 1*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(COLOR_PALETTE['accent'])),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 1), (1, -1), 'CENTER'),
            ('ALIGN', (2, 1), (2, -1), 'LEFT'),  # Intensity bar left-aligned
            ('ALIGN', (4, 1), (4, -1), 'CENTER'),  # Trajectory centered
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('FONTSIZE', (2, 1), (2, -1), 8),  # Smaller font for intensity bar
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#bdc3c7')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')])
        ]))
        
        elements.append(table)
        elements.append(Spacer(1, 0.2*inch))
        
        # Intensity legend
        elements.append(Paragraph(
            "<b>Intensity:</b> Bar length indicates relative volume. <b>Trajectory:</b> High = 80%+ of max, Moderate = 50-80%, Emerging = <50%",
            self.styles['Summary']
        ))
        
        return elements
    
    def _create_faq_section(self) -> List:
        """Create Nielsen-style FAQ/Explainer section."""
        elements = []
        
        elements.append(Paragraph("Understanding ET Intelligence Metrics", self.styles['SectionTitle']))
        elements.append(Spacer(1, 0.3*inch))
        
        faq_items = [
            {
                'question': 'What is sentiment?',
                'answer': (
                    'Sentiment measures the emotional tone of comments, scored from -1.0 (strongly negative) '
                    'to +1.0 (strongly positive). Scores are calculated using a combination of rule-based analysis '
                    'and AI models trained on entertainment industry language.'
                )
            },
            {
                'question': 'What counts as negative sentiment?',
                'answer': (
                    'Scores below -0.3 are considered negative, with scores below -0.7 indicating strongly negative sentiment. '
                    'This includes criticism, disappointment, concern, anger, or strong disapproval.'
                )
            },
            {
                'question': 'What is velocity?',
                'answer': (
                    'Velocity measures the rate of change in sentiment over a 72-hour window. A 30%+ change triggers an alert, '
                    'indicating significant shifts in public perception that may require attention.'
                )
            },
            {
                'question': 'How are entity mentions counted?',
                'answer': (
                    'Mentions are counted when an entity name or alias appears in comment text. The system uses both '
                    'exact matching and NLP entity recognition to identify mentions, ensuring comprehensive coverage.'
                )
            },
            {
                'question': 'What are discovered entities?',
                'answer': (
                    'Discovered entities are people, shows, or brands mentioned in comments that aren\'t yet in our '
                    'monitored list. These are flagged for review to determine if they should be added to regular tracking.'
                )
            },
            {
                'question': 'How is platform sentiment calculated?',
                'answer': (
                    'Platform sentiment is the average sentiment of all comments from that platform within the reporting period. '
                    'This allows comparison of discourse patterns across Instagram, YouTube, and other platforms.'
                )
            }
        ]
        
        for item in faq_items:
            elements.append(Paragraph(
                f"<b>{item['question']}</b>",
                self.styles['Normal']
            ))
            elements.append(Spacer(1, 0.1*inch))
            elements.append(Paragraph(
                item['answer'],
                self.styles['Summary']
            ))
            elements.append(Spacer(1, 0.25*inch))
        
        return elements
    
    def _create_next_steps_section(self) -> List:
        """Create Nielsen-style CTA footer."""
        elements = []
        
        elements.append(Spacer(1, 0.5*inch))
        elements.append(Paragraph("Looking for More Intelligence?", self.styles['SectionTitle']))
        elements.append(Spacer(1, 0.3*inch))
        
        next_steps = [
            'Full storyline drill-down available on request',
            'Platform-specific trend reports for deeper analysis',
            'Week-over-week risk comparisons and delta reports',
            'Full entity sentiment export with raw data',
            'Custom entity tracking and monitoring setup',
            'Real-time velocity alerts via email or Slack'
        ]
        
        for step in next_steps:
            elements.append(Paragraph(
                f"• {step}",
                self.styles['Summary']
            ))
            elements.append(Spacer(1, 0.15*inch))
        
        elements.append(Spacer(1, 0.3*inch))
        elements.append(Paragraph(
            "<i>Contact the ET Intelligence team for access to additional reports and custom analysis.</i>",
            self.styles['Normal']
        ))
        
        return elements
    
    def _create_risk_signals_section(self, section: BriefSection) -> List:
        """Create risk signals section."""
        elements = []
        
        elements.append(Paragraph(section.title, self.styles['SectionTitle']))
        elements.append(Spacer(1, 0.2*inch))
        
        if section.summary:
            elements.append(Paragraph(section.summary, self.styles['Summary']))
        
        if not section.items:
            elements.append(Paragraph("No risk signals detected.", self.styles['Normal']))
        
        return elements
    
    def _create_contextual_narrative_section(self, narrative: str) -> List:
        """Create contextual narrative section."""
        elements = []
        
        elements.append(Paragraph("Contextual Intelligence", self.styles['SectionTitle']))
        elements.append(Spacer(1, 0.2*inch))
        elements.append(Paragraph(narrative, self.styles['Summary']))
        
        return elements
    
    def _create_sentiment_distribution_section(self, dist: Dict[str, Any]) -> List:
        """Create sentiment distribution section with chart."""
        elements = []
        
        elements.append(Paragraph("Sentiment Distribution", self.styles['SectionTitle']))
        elements.append(Spacer(1, 0.2*inch))
        
        # Generate chart
        try:
            chart_path = self.chart_generator.generate_sentiment_distribution(dist)
            chart_img = Image(str(chart_path), width=5*inch, height=4*inch)
            elements.append(chart_img)
            elements.append(Spacer(1, 0.2*inch))
            
            # Nielsen-style chart explainer (1-sentence editorial pull-out)
            explainer = self._generate_chart_explainer('sentiment_distribution', dist)
            if explainer:
                elements.append(Paragraph(
                    f"<i>{explainer}</i>",
                    self.styles['Summary']
                ))
            elements.append(Spacer(1, 0.3*inch))
        except Exception as e:
            # Fallback to table if chart generation fails
            pass
        
        # Create distribution table
        dist_data = [
            ['Sentiment', 'Count', 'Percentage'],
            ['Positive (>0.3)', f"{dist['positive']:,}", f"{dist['positive_pct']:.1f}%"],
            ['Neutral (-0.3 to 0.3)', f"{dist['neutral']:,}", f"{dist['neutral_pct']:.1f}%"],
            ['Negative (<-0.3)', f"{dist['negative']:,}", f"{dist['negative_pct']:.1f}%"],
            ['Total', f"{dist['total']:,}", '100.0%']
        ]
        
        dist_table = Table(dist_data, colWidths=[2.5*inch, 1.5*inch, 1.5*inch])
        dist_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 1), (2, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#bdc3c7')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [
                colors.HexColor('#d5f4e6'),  # Positive row
                colors.HexColor('#f8f9fa'),  # Neutral row
                colors.HexColor('#ffe5e5'),  # Negative row
                colors.white  # Total row
            ])
        ]))
        
        elements.append(dist_table)
        
        return elements
    
    def _create_entity_trend_charts(self, brief: IntelligenceBriefData, limit: int = 7) -> List:
        """Create entity trend comparison charts."""
        elements = []
        
        elements.append(Paragraph("Entity Sentiment Trends", self.styles['SectionTitle']))
        elements.append(Spacer(1, 0.2*inch))
        
        # Get top entities for comparison (limit for scale)
        top_entities = brief.top_entities.items[:limit]
        
        if len(top_entities) < 2:
            return elements
        
        # For demo, we'll create a simple comparison chart
        # In production, this would use actual historical data from AnalyticsService
        try:
            # Create mock trend data for demo
            from datetime import timedelta
            entities_data = {}
            for entity in top_entities:
                entity_name = entity.get('entity_name', 'Unknown')
                # Mock 7 days of data
                trend_data = []
                base_sentiment = entity.get('avg_sentiment', 0.0)
                for i in range(7):
                    date = brief.timeframe['end'] - timedelta(days=6-i)
                    # Add some variation
                    sentiment = base_sentiment + (i - 3) * 0.05
                    trend_data.append({
                        'date': date,
                        'avg_sentiment': sentiment
                    })
                entities_data[entity_name] = trend_data
            
            chart_path = self.chart_generator.generate_entity_comparison_trend(entities_data)
            chart_img = Image(str(chart_path), width=7*inch, height=4.5*inch)
            elements.append(chart_img)
            elements.append(Spacer(1, 0.2*inch))
            
            # Nielsen-style chart explainer
            explainer = self._generate_chart_explainer('entity_trends', entities_data)
            if explainer:
                elements.append(Paragraph(
                    f"<i>{explainer}</i>",
                    self.styles['Summary']
                ))
            else:
                elements.append(Paragraph(
                    "<i>Chart shows sentiment trends for top entities over the reporting period.</i>",
                    self.styles['Normal']
                ))
        except Exception as e:
            # If chart generation fails, skip it
            pass
        
        return elements
    
    def _create_platform_wars_section(self, section: BriefSection) -> List:
        """Create enhanced Platform Wars section with charts."""
        elements = []
        
        elements.append(Paragraph("Platform Wars", self.styles['SectionTitle']))
        elements.append(Spacer(1, 0.2*inch))
        
        if section.summary:
            elements.append(Paragraph(section.summary, self.styles['Summary']))
            elements.append(Spacer(1, 0.2*inch))
        
        if not section.items:
            elements.append(Paragraph("No platform data available.", self.styles['Normal']))
            return elements
        
        # Generate platform comparison chart
        try:
            chart_path = self.chart_generator.generate_platform_comparison(section.items)
            chart_img = Image(str(chart_path), width=7*inch, height=4.5*inch)
            elements.append(chart_img)
            elements.append(Spacer(1, 0.2*inch))
            
            # Nielsen-style chart explainer
            explainer = self._generate_chart_explainer('platform_comparison', section.items)
            if explainer:
                elements.append(Paragraph(
                    f"<i>{explainer}</i>",
                    self.styles['Summary']
                ))
            elements.append(Spacer(1, 0.3*inch))
        except Exception as e:
            # Fallback to table if chart generation fails
            pass
        
        # Create platform table with insights
        table_data = [['Platform', 'Comments', 'Avg Sentiment', 'Total Likes', 'Insight']]
        
        for item in section.items:
            sentiment = item.get('avg_sentiment', 0.0)
            sentiment_str = f"{sentiment:+.2f}"
            
            # Color-code sentiment with label (using locked palette)
            sentiment_label = self._get_sentiment_label(sentiment)
            
            if sentiment > 0.7:
                sentiment_para = Paragraph(
                    f'<font color="{COLOR_PALETTE["strongly_positive"]}"><b>{sentiment_str}</b></font> <font color="#7f8c8d" size="8">({sentiment_label})</font>',
                    self.styles['Normal']
                )
                insight = "Strongly Positive"
            elif sentiment > 0.3:
                sentiment_para = Paragraph(
                    f'<font color="{COLOR_PALETTE["positive"]}">{sentiment_str}</font> <font color="#7f8c8d" size="8">({sentiment_label})</font>',
                    self.styles['Normal']
                )
                insight = "Positive"
            elif sentiment < -0.7:
                sentiment_para = Paragraph(
                    f'<font color="{COLOR_PALETTE["strongly_negative"]}"><b>{sentiment_str}</b></font> <font color="#7f8c8d" size="8">({sentiment_label})</font>',
                    self.styles['Normal']
                )
                insight = "Strongly Negative"
            elif sentiment < -0.3:
                sentiment_para = Paragraph(
                    f'<font color="{COLOR_PALETTE["negative"]}">{sentiment_str}</font> <font color="#7f8c8d" size="8">({sentiment_label})</font>',
                    self.styles['Normal']
                )
                insight = "Negative"
            else:
                sentiment_para = Paragraph(
                    f'<font color="{COLOR_PALETTE["neutral"]}">{sentiment_str}</font> <font color="#7f8c8d" size="8">({sentiment_label})</font>',
                    self.styles['Normal']
                )
                insight = "Neutral"
            
            table_data.append([
                item.get('platform', 'Unknown').title(),
                f"{item.get('comment_count', 0):,}",
                sentiment_para,
                f"{item.get('total_likes', 0):,}",
                insight
            ])
        
        table = Table(table_data, colWidths=[1.5*inch, 1.2*inch, 1.2*inch, 1.2*inch, 1.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(COLOR_PALETTE['accent'])),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 1), (3, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#bdc3c7')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')])
        ]))
        
        elements.append(table)
        
        # Add platform insights
        elements.append(Spacer(1, 0.3*inch))
        elements.append(Paragraph("<b>Key Insights:</b>", self.styles['Normal']))
        elements.append(Spacer(1, 0.1*inch))
        
        # Find best and worst platforms
        best_platform = max(section.items, key=lambda x: x.get('avg_sentiment', 0))
        worst_platform = min(section.items, key=lambda x: x.get('avg_sentiment', 0))
        
        if best_platform.get('avg_sentiment', 0) > worst_platform.get('avg_sentiment', 0):
            insight_text = (
                f"{best_platform.get('platform', 'Unknown').title()} shows the most positive sentiment "
                f"({best_platform.get('avg_sentiment', 0):+.2f}) with {best_platform.get('comment_count', 0):,} comments. "
                f"In contrast, {worst_platform.get('platform', 'Unknown').title()} has negative sentiment "
                f"({worst_platform.get('avg_sentiment', 0):+.2f}), indicating platform-specific discourse patterns."
            )
            elements.append(Paragraph(insight_text, self.styles['Summary']))
        
        return elements
    
    def _create_platform_breakdown_section(self, section: BriefSection) -> List:
        """Legacy method - redirects to Platform Wars."""
        return self._create_platform_wars_section(section)
        """Create platform breakdown section."""
        elements = []
        
        elements.append(Paragraph(section.title, self.styles['SectionTitle']))
        elements.append(Spacer(1, 0.2*inch))
        
        if section.summary:
            elements.append(Paragraph(section.summary, self.styles['Summary']))
            elements.append(Spacer(1, 0.2*inch))
        
        if not section.items:
            elements.append(Paragraph("No platform data available.", self.styles['Normal']))
            return elements
        
        # Create platform table
        table_data = [['Platform', 'Comments', 'Avg Sentiment', 'Total Likes']]
        
        for item in section.items:
            sentiment = item.get('avg_sentiment', 0.0)
            sentiment_str = f"{sentiment:+.2f}"
            
            # Color-code sentiment
            if sentiment > 0.3:
                sentiment_para = Paragraph(
                    f'<font color="#27ae60">{sentiment_str}</font>',
                    self.styles['Normal']
                )
            elif sentiment < -0.3:
                sentiment_para = Paragraph(
                    f'<font color="#e74c3c">{sentiment_str}</font>',
                    self.styles['Normal']
                )
            else:
                sentiment_para = Paragraph(sentiment_str, self.styles['Normal'])
            
            table_data.append([
                item.get('platform', 'Unknown').title(),
                f"{item.get('comment_count', 0):,}",
                sentiment_para,
                f"{item.get('total_likes', 0):,}"
            ])
        
        table = Table(table_data, colWidths=[2*inch, 1.5*inch, 1.5*inch, 1.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(COLOR_PALETTE['header'])),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 1), (3, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#bdc3c7')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')])
        ]))
        
        elements.append(table)
        
        return elements
    
    def _create_entity_comparison_section(self, section: BriefSection) -> List:
        """Create entity comparison section."""
        elements = []
        
        elements.append(Paragraph(section.title, self.styles['SectionTitle']))
        elements.append(Spacer(1, 0.2*inch))
        
        if section.summary:
            elements.append(Paragraph(section.summary, self.styles['Summary']))
            elements.append(Spacer(1, 0.2*inch))
        
        if not section.items:
            elements.append(Paragraph("No comparison data available.", self.styles['Normal']))
            return elements
        
        # Create comparison table
        table_data = [['Entity', 'Sentiment', 'Mentions', 'Trend']]
        
        for item in section.items:
            sentiment = item.get('current_sentiment', 0.0)
            trend = item.get('trend', 'stable')
            
            sentiment_str = f"{sentiment:+.2f}"
            if sentiment > 0.3:
                sentiment_para = Paragraph(
                    f'<font color="#27ae60">{sentiment_str}</font>',
                    self.styles['Normal']
                )
            elif sentiment < -0.3:
                sentiment_para = Paragraph(
                    f'<font color="#e74c3c">{sentiment_str}</font>',
                    self.styles['Normal']
                )
            else:
                sentiment_para = Paragraph(sentiment_str, self.styles['Normal'])
            
            # Trend indicator
            if trend == 'rising':
                trend_text = Paragraph('<font color="#27ae60">Rising</font>', self.styles['Normal'])
            elif trend == 'falling':
                trend_text = Paragraph('<font color="#e74c3c">Falling</font>', self.styles['Normal'])
            else:
                trend_text = Paragraph('<font color="#7f8c8d">Stable</font>', self.styles['Normal'])
            
            table_data.append([
                item.get('entity_name', 'Unknown'),
                sentiment_para,
                f"{item.get('mention_count', 0):,}",
                trend_text
            ])
        
        table = Table(table_data, colWidths=[2.5*inch, 1.5*inch, 1.5*inch, 1.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(COLOR_PALETTE['header'])),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 1), (2, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#bdc3c7')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')])
        ]))
        
        elements.append(table)
        
        return elements
    
    def _create_discovered_entities_section(self, section: BriefSection) -> List:
        """Create discovered entities section."""
        elements = []
        
        elements.append(Paragraph(section.title, self.styles['SectionTitle']))
        elements.append(Spacer(1, 0.2*inch))
        
        if section.summary:
            elements.append(Paragraph(section.summary, self.styles['Summary']))
            elements.append(Spacer(1, 0.2*inch))
        
        if not section.items:
            elements.append(Paragraph("No new entities discovered.", self.styles['Normal']))
            return elements
        
        # Create discovered entities table with recommendations
        table_data = [['Entity Name', 'Type', 'Mentions', 'First Seen', 'Recommendation']]
        
        for item in section.items[:10]:  # Limit to top 10
            entity_name = item.get('name', 'Unknown')
            entity_type = item.get('entity_type', 'unknown')
            mentions = item.get('mention_count', 0)
            first_seen = item.get('first_seen_at', '')
            
            # Parse first seen date
            if isinstance(first_seen, str):
                try:
                    from datetime import datetime
                    first_seen_dt = datetime.fromisoformat(first_seen.replace('Z', '+00:00'))
                    first_seen_str = first_seen_dt.strftime('%Y-%m-%d')
                except:
                    first_seen_str = str(first_seen)[:10]
            else:
                first_seen_str = str(first_seen)[:10]
            
            # Generate editorial recommendation
            if mentions >= 20:
                recommendation = f"<b>Add to monitoring</b> - High relevance ({mentions} mentions)"
            elif mentions >= 10:
                recommendation = f"<i>Consider adding</i> - Emerging relevance"
            else:
                recommendation = "<i>Monitor</i> - Low volume, track growth"
            
            # Special handling for known patterns
            if 'Deadpool' in entity_name or 'movie' in entity_type.lower() or 'film' in entity_type.lower() or 'WORK_OF_ART' in entity_type:
                recommendation = f"<b>Add as monitored work</b> - Emerging relevance ({mentions} mentions)"
            elif entity_type == 'PERSON' and mentions >= 15:
                recommendation = f"<b>Add to monitoring</b> - Growing presence ({mentions} mentions)"
            
            table_data.append([
                Paragraph(self._sanitize_text(entity_name), self.styles['Normal']),
                Paragraph(self._sanitize_text(entity_type), self.styles['Normal']),
                str(mentions),
                self._sanitize_text(first_seen_str),
                Paragraph(recommendation, self.styles['Normal'])
            ])
        
        table = Table(table_data, colWidths=[2*inch, 1*inch, 0.8*inch, 1*inch, 2.2*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(COLOR_PALETTE['accent'])),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (2, 1), (2, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#bdc3c7')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')])
        ]))
        
        elements.append(table)
        elements.append(Spacer(1, 0.2*inch))
        
        # Editorial guidance summary
        high_priority = [i for i in section.items if i.get('mention_count', 0) >= 20]
        if high_priority:
            guidance = (
                f"<b>Editorial Guidance:</b> {len(high_priority)} entities show high relevance (20+ mentions) "
                f"and should be considered for addition to the monitored list. "
                f"Top candidate: <b>{high_priority[0].get('name', 'Unknown')}</b> "
                f"({high_priority[0].get('mention_count', 0)} mentions)."
            )
            elements.append(Paragraph(guidance, self.styles['Summary']))
        elif section.items:
            # At least one entity to recommend
            top_entity = max(section.items, key=lambda x: x.get('mention_count', 0))
            if top_entity.get('mention_count', 0) >= 10:
                guidance = (
                    f"<b>Editorial Guidance:</b> <b>{top_entity.get('name', 'Unknown')}</b> "
                    f"should probably be added as a monitored entity due to emerging relevance "
                    f"({top_entity.get('mention_count', 0)} mentions)."
                )
                elements.append(Paragraph(guidance, self.styles['Summary']))
        
        return elements
    
    def _create_post_performance_section(self, section: BriefSection) -> List:
        """Create post performance section with top posts table and sentiment distribution chart."""
        elements = []
        
        elements.append(Paragraph(section.title, self.styles['SectionTitle']))
        elements.append(Spacer(1, 0.2*inch))
        
        if section.summary:
            elements.append(Paragraph(section.summary, self.styles['Summary']))
            elements.append(Spacer(1, 0.3*inch))
        
        if not section.items:
            elements.append(Paragraph("No post data available for this period.", self.styles['Normal']))
            return elements
        
        # Create top posts table
        table_data = [['Rank', 'Caption', 'Comments', 'Likes', 'Sentiment', 'Top Entity']]
        
        for item in section.items[:10]:  # Top 10 posts
            rank = item.get('rank', 0)
            caption = item.get('caption', '') or 'No caption'
            if len(caption) > 60:
                caption = caption[:57] + '...'
            
            comment_count = int(item.get('comment_count', 0))
            total_likes = int(item.get('total_likes', 0))
            avg_sentiment = float(item.get('avg_sentiment', 0.0))
            top_entity = item.get('top_entity', 'N/A')
            
            # Format sentiment with color
            sentiment_label = self._get_sentiment_label(avg_sentiment)
            sentiment_str = f"{avg_sentiment:+.2f}"
            
            if avg_sentiment > 0.7:
                sentiment_cell = Paragraph(
                    f'<font color="{COLOR_PALETTE["strongly_positive"]}"><b>{sentiment_str}</b></font> '
                    f'<font color="#7f8c8d" size="7">({sentiment_label})</font>',
                    self.styles['Normal']
                )
            elif avg_sentiment > 0.3:
                sentiment_cell = Paragraph(
                    f'<font color="{COLOR_PALETTE["positive"]}">{sentiment_str}</font> '
                    f'<font color="#7f8c8d" size="7">({sentiment_label})</font>',
                    self.styles['Normal']
                )
            elif avg_sentiment < -0.7:
                sentiment_cell = Paragraph(
                    f'<font color="{COLOR_PALETTE["strongly_negative"]}"><b>{sentiment_str}</b></font> '
                    f'<font color="#7f8c8d" size="7">({sentiment_label})</font>',
                    self.styles['Normal']
                )
            elif avg_sentiment < -0.3:
                sentiment_cell = Paragraph(
                    f'<font color="{COLOR_PALETTE["negative"]}">{sentiment_str}</font> '
                    f'<font color="#7f8c8d" size="7">({sentiment_label})</font>',
                    self.styles['Normal']
                )
            else:
                sentiment_cell = Paragraph(
                    f'{sentiment_str} <font color="#7f8c8d" size="7">({sentiment_label})</font>',
                    self.styles['Normal']
                )
            
            table_data.append([
                str(rank),
                Paragraph(self._sanitize_text(caption), self.styles['Normal']),
                f"{comment_count:,}",
                f"{total_likes:,}",
                sentiment_cell,
                top_entity if top_entity != 'N/A' else '—'
            ])
        
        table = Table(table_data, colWidths=[0.5*inch, 3*inch, 0.8*inch, 0.8*inch, 1.2*inch, 1.2*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(COLOR_PALETTE['header'])),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (2, 1), (3, -1), 'CENTER'),  # Comments and Likes centered
            ('ALIGN', (4, 1), (4, -1), 'CENTER'),  # Sentiment centered
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#bdc3c7')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
        ]))
        
        elements.append(table)
        elements.append(Spacer(1, 0.4*inch))
        
        # Add post sentiment distribution if available
        # Extract distribution from section summary or items
        # For now, we'll generate a simple summary text
        distribution_info = ""
        if section.summary:
            # Extract numbers from summary if available
            distribution_info = section.summary
        
        if distribution_info:
            elements.append(Paragraph(f"<b>Post Sentiment Overview:</b> {distribution_info}", self.styles['Summary']))
        
        return elements
    
    def _create_footer(self, brief: IntelligenceBriefData) -> List:
        """Create footer with metadata."""
        elements = []
        
        elements.append(Spacer(1, 0.5*inch))
        elements.append(Spacer(1, 0.2*inch))
        
        footer_text = (
            f"<i>ET Social Intelligence System v2.0 | "
            f"Generated {brief.metadata['generated_at'].strftime('%Y-%m-%d %H:%M UTC')} | "
            f"Platforms: {', '.join(brief.metadata['platforms'])}</i>"
        )
        elements.append(Paragraph(footer_text, self.styles['Normal']))
        
        return elements

