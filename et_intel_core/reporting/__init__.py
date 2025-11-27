"""
Reporting module for ET Intelligence system.

Provides brief building and PDF rendering capabilities.
"""

from et_intel_core.reporting.brief_builder import BriefBuilder, BriefSection, IntelligenceBriefData
from et_intel_core.reporting.pdf_renderer import PDFRenderer
from et_intel_core.reporting.narrative_generator import NarrativeGenerator
from et_intel_core.reporting.chart_generator import ChartGenerator

__all__ = [
    'BriefBuilder',
    'BriefSection',
    'IntelligenceBriefData',
    'PDFRenderer',
    'NarrativeGenerator',
    'ChartGenerator',
]

