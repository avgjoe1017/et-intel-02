#!/bin/bash
# Test runner script with coverage reporting

set -e

echo "Running tests with coverage..."

# Run tests with coverage
pytest tests/ \
    -v \
    --cov=et_intel_core \
    --cov-report=html \
    --cov-report=term \
    --cov-report=xml \
    --cov-fail-under=80

echo ""
echo "Coverage report generated in htmlcov/index.html"
echo "XML report generated in coverage.xml"

