"""
Tests for monitoring and metrics collection.
"""

import pytest
import time
from datetime import datetime
from sqlalchemy import text

from et_intel_core.monitoring import (
    MetricsCollector,
    get_metrics,
    track_timing,
    track_errors,
    HealthChecker,
    get_health
)


class TestMetricsCollector:
    """Tests for MetricsCollector."""
    
    def test_increment(self):
        """Test incrementing counter metrics."""
        collector = MetricsCollector()
        
        collector.increment("test_counter")
        assert collector.get_counter("test_counter") == 1
        
        collector.increment("test_counter", 5)
        assert collector.get_counter("test_counter") == 6
        
        collector.increment("other_counter")
        assert collector.get_counter("other_counter") == 1
        assert collector.get_counter("test_counter") == 6
    
    def test_record_timing(self):
        """Test recording timing metrics."""
        collector = MetricsCollector()
        
        collector.record_timing("test_timing", 0.5)
        collector.record_timing("test_timing", 1.0)
        collector.record_timing("test_timing", 1.5)
        
        stats = collector.get_timing_stats("test_timing")
        assert stats is not None
        assert stats["count"] == 3
        assert stats["mean"] == 1.0
        assert stats["min"] == 0.5
        assert stats["max"] == 1.5
        assert stats["p50"] == 1.0
        assert stats["p95"] == 1.5
        assert stats["p99"] == 1.5
    
    def test_record_timing_limit(self):
        """Test that timing metrics are limited to 1000 values."""
        collector = MetricsCollector()
        
        # Add 1001 timings
        for i in range(1001):
            collector.record_timing("test_timing", float(i))
        
        stats = collector.get_timing_stats("test_timing")
        assert stats["count"] == 1000
        assert stats["min"] == 1.0  # First value (0) was dropped
    
    def test_record_value(self):
        """Test recording value metrics."""
        collector = MetricsCollector()
        
        collector.record_value("test_value", 10.5)
        collector.record_value("test_value", 20.0)
        collector.record_value("test_value", 30.5)
        
        assert len(collector.metrics["test_value"]) == 3
        assert collector.metrics["test_value"] == [10.5, 20.0, 30.5]
    
    def test_record_value_limit(self):
        """Test that value metrics are limited to 1000 values."""
        collector = MetricsCollector()
        
        # Add 1001 values
        for i in range(1001):
            collector.record_value("test_value", float(i))
        
        assert len(collector.metrics["test_value"]) == 1000
    
    def test_get_timing_stats_empty(self):
        """Test getting timing stats when no data exists."""
        collector = MetricsCollector()
        
        stats = collector.get_timing_stats("nonexistent")
        assert stats is None
    
    def test_get_metrics_summary(self):
        """Test getting metrics summary."""
        collector = MetricsCollector()
        
        collector.increment("counter1", 5)
        collector.increment("counter2", 10)
        collector.record_timing("timing1", 1.0)
        collector.record_timing("timing1", 2.0)
        
        summary = collector.get_metrics_summary()
        
        assert "counters" in summary
        assert summary["counters"]["counter1"] == 5
        assert summary["counters"]["counter2"] == 10
        assert "timing_stats" in summary
        assert "timing1" in summary["timing_stats"]
        assert summary["timing_stats"]["timing1"]["count"] == 2
        assert "timestamp" in summary
    
    def test_reset(self):
        """Test resetting all metrics."""
        collector = MetricsCollector()
        
        collector.increment("counter1", 5)
        collector.record_timing("timing1", 1.0)
        collector.record_value("value1", 10.0)
        
        collector.reset()
        
        assert collector.get_counter("counter1") == 0
        assert collector.get_timing_stats("timing1") is None
        assert len(collector.metrics["value1"]) == 0


class TestGlobalMetrics:
    """Tests for global metrics functions."""
    
    def test_get_metrics(self):
        """Test getting global metrics collector."""
        metrics = get_metrics()
        assert isinstance(metrics, MetricsCollector)
        
        # Should return same instance
        metrics2 = get_metrics()
        assert metrics is metrics2
    
    def test_track_timing_decorator(self):
        """Test track_timing decorator."""
        @track_timing("test_metric")
        def test_function():
            time.sleep(0.01)  # Small delay to measure
            return "result"
        
        result = test_function()
        assert result == "result"
        
        # Check that timing was recorded
        metrics = get_metrics()
        stats = metrics.get_timing_stats("test_metric.test_function")
        assert stats is not None
        assert stats["count"] == 1
        assert stats["mean"] > 0
    
    def test_track_timing_decorator_with_exception(self):
        """Test track_timing decorator handles exceptions."""
        @track_timing("test_metric")
        def failing_function():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            failing_function()
        
        # Timing should still be recorded
        metrics = get_metrics()
        stats = metrics.get_timing_stats("test_metric.failing_function")
        assert stats is not None
    
    def test_track_errors_decorator(self):
        """Test track_errors decorator."""
        @track_errors("test_metric")
        def successful_function():
            return "success"
        
        result = successful_function()
        assert result == "success"
        
        # No errors should be recorded
        metrics = get_metrics()
        assert metrics.get_counter("test_metric.successful_function.errors") == 0
    
    def test_track_errors_decorator_with_exception(self):
        """Test track_errors decorator tracks errors."""
        @track_errors("test_metric")
        def failing_function():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            failing_function()
        
        # Error should be recorded
        metrics = get_metrics()
        assert metrics.get_counter("test_metric.failing_function.errors") == 1


class TestHealthChecker:
    """Tests for HealthChecker."""
    
    def test_check_database_success(self, db_session):
        """Test successful database health check."""
        checker = HealthChecker()
        
        result = checker.check_database(db_session)
        
        assert result is True
        assert checker.checks["database"] is True
        assert "database" in checker.last_check
    
    def test_check_database_failure(self):
        """Test database health check with invalid session."""
        checker = HealthChecker()
        
        # Create a mock session that will fail
        class BadSession:
            def execute(self, query):
                raise Exception("Connection failed")
        
        result = checker.check_database(BadSession())
        
        assert result is False
        assert checker.checks["database"] is False
        assert "database" in checker.last_check
    
    def test_get_health_status_healthy(self, db_session):
        """Test getting health status when all checks pass."""
        checker = HealthChecker()
        checker.check_database(db_session)
        
        status = checker.get_health_status()
        
        assert status["status"] == "healthy"
        assert status["checks"]["database"] is True
        assert "last_check" in status
        assert "timestamp" in status
    
    def test_get_health_status_unhealthy(self):
        """Test getting health status when checks fail."""
        checker = HealthChecker()
        
        class BadSession:
            def execute(self, query):
                raise Exception("Connection failed")
        
        checker.check_database(BadSession())
        
        status = checker.get_health_status()
        
        assert status["status"] == "unhealthy"
        assert status["checks"]["database"] is False
    
    def test_get_health(self):
        """Test getting global health checker."""
        health = get_health()
        assert isinstance(health, HealthChecker)
        
        # Should return same instance
        health2 = get_health()
        assert health is health2

