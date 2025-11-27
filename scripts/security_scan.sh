#!/bin/bash
# Security scanning script for ET Intelligence system

set -e

echo "🔒 Running security scans..."

# Check for security vulnerabilities in dependencies
echo "📦 Checking dependencies for vulnerabilities..."
if command -v safety &> /dev/null; then
    safety check --json || true
else
    echo "⚠️  'safety' not installed. Install with: pip install safety"
fi

# Check for known security issues
echo "🔍 Checking for common security issues..."

# Check for hardcoded secrets
echo "  - Checking for hardcoded secrets..."
if grep -r "password.*=.*['\"].*[^ENV]" --include="*.py" . 2>/dev/null | grep -v "#.*password" | grep -v "test" | head -5; then
    echo "    ⚠️  Potential hardcoded passwords found"
else
    echo "    ✓ No obvious hardcoded passwords"
fi

# Check for SQL injection risks (basic check)
echo "  - Checking for SQL injection risks..."
if grep -r "execute.*%" --include="*.py" . 2>/dev/null | grep -v "test" | head -5; then
    echo "    ⚠️  Potential SQL injection risks (string formatting in queries)"
else
    echo "    ✓ No obvious SQL injection patterns"
fi

# Check for exposed API keys
echo "  - Checking for exposed API keys..."
if grep -r "api[_-]key.*=.*['\"][^ENV]" --include="*.py" . 2>/dev/null | grep -v "test" | head -5; then
    echo "    ⚠️  Potential exposed API keys found"
else
    echo "    ✓ No obvious exposed API keys"
fi

# Check file permissions
echo "  - Checking file permissions..."
if find . -name "*.env" -o -name "*.key" -o -name "*.pem" 2>/dev/null | head -5; then
    echo "    ⚠️  Sensitive files found - ensure proper permissions"
else
    echo "    ✓ No obvious sensitive files in repo"
fi

echo "✅ Security scan complete"
