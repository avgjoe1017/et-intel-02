"""
ET Social Intelligence System - V2

A production-grade social intelligence platform that converts social media
comments into strategic intelligence.

Core Philosophy:
    Intelligence is derived, not stored. Comments are atoms. Everything else is a view.
"""

__version__ = "2.0.0"
__author__ = "ET Intelligence Team"

# Initialize logging on import
from et_intel_core.logging_config import setup_logging, get_logger

__all__ = [
    "__version__",
    "__author__",
    "setup_logging",
    "get_logger",
]

