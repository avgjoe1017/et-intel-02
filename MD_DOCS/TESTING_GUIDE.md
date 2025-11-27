# Testing Guide

Complete guide to testing the ET Intelligence system.

---

## Test Structure

### Test Files

- `test_models.py` - Database model tests
- `test_ingestion.py` - Data ingestion tests
- `test_nlp.py` - NLP component tests
- `test_enrichment.py` - Enrichment service tests
- `test_analytics.py` - Analytics service tests
- `test_reporting.py` - Reporting tests
- `test_cli.py` - CLI command tests
- `test_integration.py` - **NEW** End-to-end workflow tests
- `test_edge_cases.py` - **NEW** Edge case and boundary tests
- `test_performance.py` - **NEW** Performance benchmarks
- `test_security.py` - **NEW** Security tests

---

## Running Tests

### Basic Test Execution

```bash
# Run all tests
pytest tests/

# Run with verbose output
pytest tests/ -v

# Run specific test file
pytest tests/test_integration.py

# Run specific test
pytest tests/test_integration.py::TestEndToEndWorkflow::test_full_workflow_ingest_enrich_analyze
```

### With Coverage

```bash
# Run with coverage report
pytest tests/ --cov=et_intel_core --cov-report=html --cov-report=term

# View HTML coverage report
open htmlcov/index.html  # macOS
# or
start htmlcov/index.html  # Windows
```

### Using Test Scripts

```bash
# Run all tests with coverage (target: 80%+)
./scripts/run_tests.sh

# Run security scans
./scripts/security_scan.sh
```

### Parallel Execution

```bash
# Run tests in parallel (faster)
pytest tests/ -n auto
```

### Benchmark Tests

```bash
# Run performance benchmarks
pytest tests/test_performance.py --benchmark-only

# Compare benchmarks
pytest tests/test_performance.py --benchmark-compare
```

---

## Test Categories

### Unit Tests

**Purpose**: Test individual components in isolation

**Examples**:
- Model creation and relationships
- Service methods
- Utility functions

**Run**: `pytest tests/test_models.py tests/test_nlp.py`

### Integration Tests

**Purpose**: Test complete workflows end-to-end

**Examples**:
- Ingest → Enrich → Analyze → Report
- Multi-service interactions
- Error recovery

**Run**: `pytest tests/test_integration.py -m integration`

### Edge Case Tests

**Purpose**: Test boundary conditions and error handling

**Examples**:
- Empty datasets
- Large datasets
- Invalid inputs
- Failure scenarios

**Run**: `pytest tests/test_edge_cases.py`

### Performance Tests

**Purpose**: Benchmark system performance

**Examples**:
- Ingestion throughput
- Query performance
- Memory usage

**Run**: `pytest tests/test_performance.py --benchmark-only`

### Security Tests

**Purpose**: Verify security measures

**Examples**:
- SQL injection prevention
- Input validation
- Data access controls

**Run**: `pytest tests/test_security.py`

---

## Coverage Goals

### Current Coverage

Run coverage report to see current status:
```bash
pytest tests/ --cov=et_intel_core --cov-report=term
```

### Target Coverage

- **Overall**: 80%+
- **Critical paths**: 90%+
- **Services**: 85%+
- **Models**: 95%+

### Coverage Exclusions

Some code is excluded from coverage:
- Test files themselves
- Migration files
- Abstract base classes
- Type checking blocks

See `.coveragerc` for full configuration.

---

## Writing New Tests

### Test Structure

```python
import pytest
from et_intel_core.db import get_session

class TestMyFeature:
    """Test suite for my feature."""
    
    def test_basic_functionality(self, db_session):
        """Test basic functionality."""
        # Arrange
        # Act
        # Assert
        pass
    
    def test_edge_case(self, db_session):
        """Test edge case."""
        pass
```

### Using Fixtures

```python
# Use existing fixtures
def test_with_entity(db_session, sample_entity):
    # sample_entity is available
    pass

# Create custom fixtures in conftest.py
@pytest.fixture
def my_custom_fixture(db_session):
    # Setup
    yield resource
    # Teardown
```

### Best Practices

1. **One assertion per test** (when possible)
2. **Descriptive test names**: `test_ingestion_creates_posts_and_comments`
3. **Arrange-Act-Assert pattern**
4. **Use fixtures for setup/teardown**
5. **Test both success and failure cases**
6. **Keep tests independent** (no shared state)

---

## CI/CD Integration

### GitHub Actions

Tests run automatically on:
- Push to main/develop
- Pull requests

See `.github/workflows/ci.yml` for configuration.

### Coverage Reporting

Coverage reports are uploaded to Codecov (if configured).

### Test Failures

If tests fail in CI:
1. Check the error message
2. Run tests locally to reproduce
3. Fix the issue
4. Ensure all tests pass before merging

---

## Performance Benchmarks

### Running Benchmarks

```bash
# Run all benchmarks
pytest tests/test_performance.py --benchmark-only

# Compare with previous run
pytest tests/test_performance.py --benchmark-compare
```

### Benchmark Targets

- **Ingestion**: 100+ comments/second
- **Enrichment**: 50+ comments/second
- **Analytics queries**: <1 second (p95)
- **PDF generation**: <30 seconds

### Interpreting Results

Benchmark results show:
- Mean execution time
- Min/Max times
- Percentiles (p50, p95, p99)

Use these to identify performance regressions.

---

## Security Testing

### Running Security Tests

```bash
# Run security test suite
pytest tests/test_security.py

# Run security scans
./scripts/security_scan.sh
```

### Security Checks

1. **SQL Injection**: All queries use parameterization
2. **Input Validation**: All user inputs validated
3. **Authentication**: No hardcoded credentials
4. **Data Access**: Proper access controls

### Security Scanning

- **Safety**: Dependency vulnerability scanning
- **Bandit**: Code security scanning

---

## Troubleshooting Tests

### Common Issues

**Database connection errors**:
- Ensure test database is available
- Check DATABASE_URL in test environment

**Import errors**:
- Ensure all dependencies installed
- Check Python path

**Fixture errors**:
- Verify fixtures in conftest.py
- Check fixture scope

**Timeout errors**:
- Increase timeout in pytest.ini
- Optimize slow tests

### Debug Mode

```bash
# Run with debug output
pytest tests/ -v -s

# Drop into debugger on failure
pytest tests/ --pdb

# Show print statements
pytest tests/ -s
```

---

## Test Maintenance

### Keeping Tests Updated

- Update tests when adding features
- Remove obsolete tests
- Refactor tests for clarity
- Keep test data minimal

### Test Data

- Use fixtures for reusable data
- Create minimal test datasets
- Clean up after tests (automatic with fixtures)

### Test Performance

- Keep tests fast (<1 second each when possible)
- Use parallel execution for large suites
- Mock external dependencies
- Use in-memory database for tests

---

*Last Updated: 2025-11-24*

