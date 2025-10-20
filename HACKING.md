# Hacking on sru-lint

This document provides information for developers who want to contribute to or modify sru-lint.

## Development Setup

### Prerequisites

- Python 3.8 or higher
- Poetry for dependency management
- Git

### Setting up the development environment

1. Clone the repository:
   ```bash
   git clone https://github.com/dargad/sru-lint.git
   cd sru-lint
   ```

2. Install dependencies using Poetry:
   ```bash
   poetry install
   ```

3. Activate the virtual environment:
   ```bash
   poetry shell
   ```

## Running the Application

### Using Poetry

To run sru-lint with Poetry, use the `poetry run` command:

```bash
# Basic usage - analyze a patch file
poetry run sru-lint check path/to/patch.debdiff

# Check with specific modules only
poetry run sru-lint check -m changelog-entry path/to/patch.debdiff

# Output in JSON format
poetry run sru-lint check -f json path/to/patch.debdiff

# Quiet mode (suppress logging)
poetry run sru-lint -q check path/to/patch.debdiff

# Verbose mode
poetry run sru-lint -v check path/to/patch.debdiff

# List available plugins
poetry run sru-lint plugins

# Read from stdin
cat patch.debdiff | poetry run sru-lint check -
```

### Development Mode

For development, you can also install the package in editable mode:

```bash
poetry install
```

Then run directly:
```bash
sru-lint check path/to/patch.debdiff
```

## Running Tests

### Unit Tests

Run all unit tests:
```bash
poetry run python -m unittest discover -s tests
```

Run tests with verbose output:
```bash
poetry run python -m unittest discover -s tests -v
```

Run specific test files:
```bash
poetry run python -m unittest tests.test_changelog_entry
poetry run python -m unittest tests.test_patch_format
```

Run a specific test method:
```bash
poetry run python -m unittest tests.test_changelog_entry.TestChangelogEntry.test_process_file_valid_changelog
```

### Test Coverage

To run tests with coverage reporting:
```bash
poetry run coverage run -m unittest discover -s tests
poetry run coverage report
poetry run coverage html  # Generate HTML coverage report
```

## Project Structure

```
sru-lint/
├── sru_lint/                  # Main package
│   ├── cli.py                 # Command-line interface
│   ├── plugin_manager.py      # Plugin loading and management
│   ├── plugins/               # Built-in plugins
│   │   ├── changelog_entry.py
│   │   ├── patch_format.py
│   │   └── ...
│   └── common/                # Shared utilities
│       ├── feedback.py        # Feedback and error reporting
│       ├── errors.py          # Error codes and types
│       ├── logging.py         # Logging configuration
│       └── ...
├── tests/                     # Unit tests
├── pyproject.toml            # Poetry configuration
└── README.md
```

## Adding New Plugins

### Plugin Structure

Create a new plugin by inheriting from the `Plugin` base class:

```python
from sru_lint.plugins.plugin_base import Plugin
from sru_lint.common.feedback import FeedbackItem, Severity
from sru_lint.common.errors import ErrorCode
from sru_lint.common.logging import get_logger

class MyPlugin(Plugin):
    """Description of what this plugin checks."""
    
    def __init__(self):
        super().__init__()
        self.logger = get_logger("plugins.my-plugin")
    
    def register_file_patterns(self):
        """Register file patterns this plugin should process."""
        self.add_file_pattern("debian/control")
        self.add_file_pattern("*.py")
    
    def process_file(self, processed_file):
        """Process a single file."""
        self.logger.info(f"Processing file: {processed_file.path}")
        
        # Your validation logic here
        if some_condition:
            feedback = FeedbackItem(
                message="Issue description",
                rule_id=ErrorCode.MY_ERROR_CODE,
                severity=Severity.ERROR,
                span=processed_file.source_span
            )
            self.feedback.append(feedback)
```

### Plugin Registration

Plugins are automatically discovered if they:
1. Are placed in the `sru_lint/plugins/` directory
2. Inherit from the `Plugin` base class
3. Have a `__symbolic_name__` attribute

### Testing Plugins

Create corresponding test files in the `tests/` directory:

```python
import unittest
from unittest.mock import MagicMock
from sru_lint.plugins.my_plugin import MyPlugin
from sru_lint.plugins.plugin_base import ProcessedFile

class TestMyPlugin(unittest.TestCase):
    def setUp(self):
        self.plugin = MyPlugin()
        self.plugin.feedback = []
    
    def test_plugin_functionality(self):
        # Test your plugin logic
        pass
```

## Code Style and Standards

### Python Style

- Follow PEP 8 style guidelines
- Use type hints where appropriate
- Document functions and classes with docstrings
- Keep line length under 100 characters

### Error Handling

- Use the `ErrorCode` enum for consistent error codes
- Create appropriate `FeedbackItem` objects for issues
- Log errors and warnings using the logging system

### Logging

Use the common logging system:

```python
from sru_lint.common.logging import get_logger

logger = get_logger("module.name")
logger.info("Informational message")
logger.warning("Warning message")
logger.error("Error message")
logger.debug("Debug message")
```

## Debugging

### Enable Debug Logging

```bash
poetry run sru-lint -vv check path/to/patch.debdiff
```

### Common Issues

1. **Plugin not found**: Ensure your plugin is in the `sru_lint/plugins/` directory and inherits from `Plugin`
2. **Import errors**: Check that all dependencies are properly installed with `poetry install`
3. **Test failures**: Run tests individually to isolate issues

## Contributing

### Before Submitting

1. Run all tests: `poetry run python -m unittest discover -s tests`
2. Check code style (if using linters)
3. Add tests for new functionality
4. Update documentation as needed

### Pull Request Process

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Ensure all tests pass
6. Submit a pull request

## Useful Development Commands

```bash
# Install development dependencies
poetry install

# Update dependencies
poetry update

# Add a new dependency
poetry add package-name

# Add a development dependency
poetry add --group dev package-name

# Run in development mode
poetry run sru-lint --help

# Run tests with coverage
poetry run coverage run -m unittest discover -s tests
poetry run coverage report

# Format code (if using formatters)
poetry run black sru_lint/ tests/

# Type checking (if using mypy)
poetry run mypy sru_lint/
```

## Additional Resources

- [Poetry Documentation](https://python-poetry.org/docs/)
- [Python unittest Documentation](https://docs.python.org/3/library/unittest.html)
- [PEP 8 Style Guide](https://pep8.org/)