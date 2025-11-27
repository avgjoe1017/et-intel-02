"""
Basic monitoring and metrics collection.

Provides simple metrics for application health and performance.
"""

import time
from typing import Dict, Optional
from datetime import datetime
from functools import wraps
from collections import defaultdict

from et_intel_core.logging_config import get_logger

logger = get_logger(__name__)


class MetricsCollector:
    """Simple metrics collector for application monitoring."""
    
    def __init__(self):
        self.metrics: Dict[str, list] = defaultdict(list)
        self.counters: Dict[str, int] = defaultdict(int)
        self.timings: Dict[str, list] = defaultdict(list)
    
    def increment(self, metric_name: str, value: int = 1):
        """Increment a counter metric."""
        self.counters[metric_name] += value
        logger.debug(f"Metric {metric_name} incremented by {value}")
    
    def record_timing(self, metric_name: str, duration: float):
        """Record a timing metric in seconds."""
        self.timings[metric_name].append(duration)
        # Keep only last 1000 timings
        if len(self.timings[metric_name]) > 1000:
            self.timings[metric_name] = self.timings[metric_name][-1000:]
        logger.debug(f"Timing {metric_name}: {duration:.3f}s")
    
    def record_value(self, metric_name: str, value: float):
        """Record a value metric."""
        self.metrics[metric_name].append(value)
        # Keep only last 1000 values
        if len(self.metrics[metric_name]) > 1000:
            self.metrics[metric_name] = self.metrics[metric_name][-1000:]
    
    def get_counter(self, metric_name: str) -> int:
        """Get current counter value."""
        return self.counters.get(metric_name, 0)
    
    def get_timing_stats(self, metric_name: str) -> Optional[Dict[str, float]]:
        """Get timing statistics (mean, min, max, p95, p99)."""
        timings = self.timings.get(metric_name, [])
        if not timings:
            return None
        
        sorted_timings = sorted(timings)
        n = len(sorted_timings)
        
        return {
            "count": n,
            "mean": sum(timings) / n,
            "min": min(timings),
            "max": max(timings),
            "p50": sorted_timings[int(n * 0.50)],
            "p95": sorted_timings[int(n * 0.95)],
            "p99": sorted_timings[int(n * 0.99)],
        }
    
    def get_metrics_summary(self) -> Dict:
        """Get summary of all metrics."""
        return {
            "counters": dict(self.counters),
            "timing_stats": {
                name: self.get_timing_stats(name)
                for name in self.timings.keys()
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def reset(self):
        """Reset all metrics (useful for testing)."""
        self.metrics.clear()
        self.counters.clear()
        self.timings.clear()


# Global metrics collector
_metrics = MetricsCollector()


def get_metrics() -> MetricsCollector:
    """Get global metrics collector."""
    return _metrics


def track_timing(metric_name: str):
    """Decorator to track function execution time."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start
                _metrics.record_timing(f"{metric_name}.{func.__name__}", duration)
        return wrapper
    return decorator


def track_errors(metric_name: str):
    """Decorator to track function errors."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                _metrics.increment(f"{metric_name}.{func.__name__}.errors")
                logger.error(f"Error in {func.__name__}: {e}", exc_info=True)
                raise
        return wrapper
    return decorator


class HealthChecker:
    """Simple health check for application components."""
    
    def __init__(self):
        self.checks: Dict[str, bool] = {}
        self.last_check: Dict[str, datetime] = {}
    
    def check_database(self, session) -> bool:
        """Check database connectivity."""
        try:
            from sqlalchemy import text
            session.execute(text("SELECT 1"))
            self.checks["database"] = True
            self.last_check["database"] = datetime.utcnow()
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            self.checks["database"] = False
            self.last_check["database"] = datetime.utcnow()
            return False
    
    def get_health_status(self) -> Dict:
        """Get overall health status."""
        all_healthy = all(self.checks.values())
        
        return {
            "status": "healthy" if all_healthy else "unhealthy",
            "checks": dict(self.checks),
            "last_check": {
                name: dt.isoformat() if dt else None
                for name, dt in self.last_check.items()
            },
            "timestamp": datetime.utcnow().isoformat()
        }


# Global health checker
_health = HealthChecker()


def get_health() -> HealthChecker:
    """Get global health checker."""
    return _health

