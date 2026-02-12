# Recon-ng Test Suite

This directory contains the test suite for recon-ng.

## Setup

Install test dependencies:

```bash
pip install -r requirements-test.txt
```

**Note:** The `requirements-test.txt` includes optional Flask dependencies. If you only want to run core tests (without web/API tests), you can install just the core dependencies:

```bash
pip install pytest pytest-cov pytest-mock pytest-timeout responses freezegun
```

## Running Tests

### Basic Test Run

```bash
# Run all tests
pytest tests/

# Run with verbose output
pytest tests/ -v

# Run specific test file
pytest tests/unit/test_validators.py

# Run specific test
pytest tests/unit/test_validators.py::TestValidators::test_validate_email_valid
```

### Running Tests by Category

```bash
# Run only unit tests
pytest tests/unit/

# Run only integration tests
pytest tests/integration/

# Run tests by marker
pytest -m unit
pytest -m integration
pytest -m "not slow"
```

### Running Tests with Coverage

```bash
# Run with terminal coverage report
pytest --cov=recon tests/

# Run with detailed missing lines
pytest --cov=recon --cov-report=term-missing tests/

# Generate HTML coverage report
pytest --cov=recon --cov-report=html tests/
# Then open htmlcov/index.html in your browser

# Generate both terminal and HTML reports
pytest --cov=recon --cov-report=term-missing --cov-report=html tests/
```

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures
├── unit/                    # Unit tests
│   ├── test_validators.py   # Input validation tests
│   ├── test_parsers.py      # Parser function tests
│   ├── test_options.py      # Options class tests
│   ├── test_framework.py    # Framework class tests
│   ├── test_module.py       # BaseModule tests
│   ├── test_base.py         # Recon class tests
│   ├── mixins/
│   │   ├── test_resolver.py # DNS resolver mixin tests
│   │   └── test_threads.py  # Threading mixin tests
│   └── web/
│       └── test_exports.py  # Web export function tests
└── integration/
    ├── test_database.py     # Database CRUD tests
    ├── test_workspace.py    # Workspace management tests
    └── test_api.py          # Flask REST API tests
```

## Skipped Tests

Some tests are skipped due to known bugs in recon-ng:

1. **`test_table_with_title`** - Bug in `framework.py:336` where `tdata` (title) isn't joined properly
2. **`test_table_empty_data`** - Bug in `framework.py:319` where empty data causes iteration error
3. **`test_ascii_sanitize`** - Bug in `module.py:91` with Python 3 incompatibility (list + range)

## Flask-Dependent Tests

The following test files require Flask and related dependencies:
- `tests/unit/web/test_exports.py`
- `tests/integration/test_api.py`

These tests will be automatically skipped if Flask is not installed. To run the full test suite:

```bash
pip install flask flask-restful flasgger dicttoxml XlsxWriter unicodecsv rq redis
pytest tests/
```

## Writing New Tests

### Fixtures

Common fixtures are available in `conftest.py`:
- `temp_workspace` - Temporary workspace directory
- `mock_framework` - Mocked Framework instance
- `sample_data` - Sample test data

### Markers

Available pytest markers (defined in `pytest.ini`):
- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.slow` - Slow-running tests
- `@pytest.mark.web` - Web/Flask-dependent tests

### Example Test

```python
import pytest
from recon.core.framework import Framework

class TestExample:
    """Example test class."""
    
    @pytest.mark.unit
    def test_something(self, mock_framework):
        """Test description."""
        result = mock_framework.some_method()
        assert result == expected_value
```

## Continuous Integration

To run the full test suite with coverage in CI:

```bash
pip install -r requirements-test.txt
pytest --cov=recon --cov-report=xml --cov-report=term-missing tests/
```

The XML report can be uploaded to coverage services like Codecov or Coveralls.
