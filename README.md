# sru-lint

Static checks for Ubuntu SRU (Stable Release Update) patches — built to run in CI and to generate human-friendly reports.

- **`sru-lint`**: the fast, scriptable checker (exit codes for CI).
- **`sru-inspect`**: the viewer (renders JSON reports to minimal HTML with annotations).

Under the hood, `sru-lint` parses patches with [`unidiff`](https://pypi.org/project/unidiff/), runs a set of **plugins**, and emits structured **FeedbackItem**s you can render or post-process.

---

## Features

- 🔌 **Plugin architecture**: drop-in checks under `sru_lint.plugins.*`.
- 📄 **Precise locations**: line/column spans with content context for robust highlighting.
- 🧰 **Extensible feedback system**: JSON-serializable `FeedbackItem` with severity levels.
- 🖥️ **Two UIs**: machine-readable JSON for pipelines, console output with snippets for humans.
- 🧪 **Tests included** (unittest).

---

## Install

```bash
# Using Poetry (recommended for development)
git clone https://github.com/dargad/sru-lint.git
cd sru-lint
poetry install

# Using pip
pip install sru-lint
```

> Requires Python 3.8+.

---

## Quick start

Lint a patch file:

```bash
# Using Poetry
poetry run sru-lint check path/to/patch.debdiff

# Console output (default)
poetry run sru-lint check path/to/patch.debdiff --format console

# JSON output for machine processing
poetry run sru-lint check path/to/patch.debdiff --format json > report.json
```

From stdin:

```bash
cat patch.debdiff | poetry run sru-lint check -
git show -p HEAD | poetry run sru-lint check -
```

List available plugins:

```bash
poetry run sru-lint plugins
```

---

## CLI

### `sru-lint` (checker)

```
Usage: sru-lint [OPTIONS] COMMAND [ARGS]...

Options:
  -v, --verbose INTEGER   Increase verbosity (use multiple times for more verbose)
  -q, --quiet            Suppress non-essential output
  --help                 Show this message and exit

Commands:
  check     Run the linter on the specified patch
  plugins   List all available plugins
  inspect   Inspect the patch and generate a HTML report (TODO)
  help      Show help for commands
```

#### `check` command

```
Usage: sru-lint check [OPTIONS] [FILE]

Arguments:
  FILE  File to read, or '-' for stdin [default: -]

Options:
  -m, --modules TEXT     Only run the specified module(s). Default is 'all'. 
                         Can be specified as comma-separated list or multiple times
  -f, --format [console|json]  
                         Output format: 'console' for human-readable output with 
                         snippets, 'json' for machine-readable JSON array 
                         [default: console]
  --help                 Show this message and exit
```

**Exit codes**
- `0` – no errors found
- `1` – errors found
- `2` – no files found in patch or failed to parse patch

---

## What it checks

Checks are implemented as **plugins**. Current plugins include:

- **`changelog-entry`** – Validates `debian/changelog` entries (distributions, LP bugs, version order)
- **`patch-format`** – Checks DEP-3 compliance for patches in `debian/patches/`
- **`publishing-history`** – Checks if versions are already published (TODO)
- **`upload-queue`** – Checks if versions are in the upload queue (TODO)

---

## Report schema

Findings are emitted as `FeedbackItem`s with precise `SourceSpan`s:

```json
[
  {
    "message": "Invalid distribution 'invalid-dist'",
    "rule_id": "CHANGELOG001", 
    "severity": "error",
    "span": {
      "path": "debian/changelog",
      "start_line": 1,
      "start_col": 1, 
      "end_line": 1,
      "end_col": 1,
      "content": [
        {
          "content": "package (1.0-1ubuntu1) invalid-dist; urgency=medium",
          "line_number": 1,
          "is_added": true
        }
      ]
    }
  }
]
```

Console output shows snippets with line numbers and highlights for human-friendly debugging.

---

## Plugins

### Base interface

```python
from sru_lint.plugins.plugin_base import Plugin
from sru_lint.common.feedback import FeedbackItem, Severity
from sru_lint.common.errors import ErrorCode

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

### Built-in plugins

```python
# sru_lint/plugins/changelog_entry.py
class ChangelogEntry(Plugin):
    """Checks changelog entries for valid distributions, LP bugs, version order."""
    
    def register_file_patterns(self):
        self.add_file_pattern("debian/changelog")
    
    def process_file(self, processed_file):
        # Validates distributions, checks LP bug targeting, etc.
```

```python
# sru_lint/plugins/patch_format.py  
class PatchFormat(Plugin):
    """Checks DEP-3 compliance for patches."""
    
    def register_file_patterns(self):
        self.add_file_pattern("debian/patches/*")
    
    def process_file(self, processed_file):
        # Validates DEP-3 headers: Description, Author/Origin, etc.
```

### Discovery

`PluginManager` automatically discovers all subclasses of `Plugin` from `sru_lint.plugins` and nested packages. Any new plugin class is picked up automatically.

---

## Error Codes

Error codes are defined in `sru_lint.common.errors.ErrorCode`:

- **CHANGELOG001** - Invalid distribution
- **CHANGELOG002** - Bug not targeted to distribution  
- **CHANGELOG003** - Version order error
- **PATCH_DEP3_FORMAT** - General DEP-3 format issue
- **PATCH_DEP3_MISSING_DESCRIPTION** - Missing Description/Subject field
- **PATCH_DEP3_EMPTY_DESCRIPTION** - Empty description field
- **PATCH_DEP3_MISSING_ORIGIN_AUTHOR** - Missing Origin or Author field
- **PATCH_DEP3_INVALID_DATE** - Invalid Last-Update date format
- **PATCH_DEP3_INVALID_FORWARDED** - Invalid Forwarded field

---

## Usage examples

Lint a patch and get console output:

```bash
poetry run sru-lint check my.patch
```

Check only changelog entries:

```bash
poetry run sru-lint check -m changelog-entry my.patch
```

Get JSON output for machine processing:

```bash
poetry run sru-lint check --format json my.patch > report.json
```

Quiet mode (suppress logging):

```bash
poetry run sru-lint -q check my.patch
```

Verbose mode for debugging:

```bash
poetry run sru-lint -v check my.patch
poetry run sru-lint -vv check my.patch  # extra verbose
```

Pipe from git:

```bash
git show -p origin/stable..HEAD | poetry run sru-lint check -
```

---

## Development

### Setup

```bash
git clone https://github.com/dargad/sru-lint.git
cd sru-lint
poetry install
```

### Run tests

```bash
# All tests
poetry run python -m unittest discover -s tests

# Specific test file  
poetry run python -m unittest tests.test_changelog_entry

# With coverage
poetry run coverage run -m unittest discover -s tests
poetry run coverage report
```

### Project layout

```
sru-lint/
├── sru_lint/                  # Main package
│   ├── cli.py                 # Command-line interface (Typer-based)
│   ├── plugin_manager.py      # Plugin loading and management
│   ├── plugins/               # Built-in plugins
│   │   ├── changelog_entry.py # Changelog validation
│   │   ├── patch_format.py    # DEP-3 patch format checking
│   │   ├── publishing_history.py
│   │   ├── upload_queue.py
│   │   └── nested/            # Nested plugin example
│   │       └── dummy_plugin.py
│   └── common/                # Shared utilities
│       ├── feedback.py        # Feedback and error reporting
│       ├── errors.py          # Error codes and enum serialization
│       ├── logging.py         # Logging configuration
│       ├── patch_processor.py # Patch parsing and ProcessedFile creation
│       ├── debian/            # Debian-specific utilities
│       │   ├── changelog.py   # Changelog parsing
│       │   └── dep3.py        # DEP-3 compliance checking
│       └── ui/
│           └── snippet.py     # Code snippet rendering
├── tests/                     # Unit tests
│   ├── test_changelog_entry.py
│   ├── test_patch_format.py
│   ├── test_cli.py
│   └── ...
├── pyproject.toml            # Poetry configuration
├── HACKING.md               # Development documentation
└── README.md
```

### Console entry points

The CLI is built with [Typer](https://typer.tiangolo.com/) and configured in `pyproject.toml`:

```toml
[project.scripts]
sru-lint = "sru_lint.cli:app"
```

---

## Contributing

- Open an issue for substantial changes.
- Add tests for new behavior in the `tests/` directory.
- Keep plugins single-purpose and fast (they run in CI).
- Follow the existing plugin patterns and error code conventions.
- See [HACKING.md](HACKING.md) for detailed development guidelines.

---

## License

Specify your license (e.g., MIT, Apache-2.0) in `LICENSE`.

---

## FAQ

**Why two commands?**  
`sru-lint` matches "linter" expectations in CI; `sru-inspect` focuses on human-friendly triage and doesn't affect build status.

**Can I add my own checks?**  
Yes — create a new class under `sru_lint.plugins` that subclasses `Plugin`. The manager discovers it automatically. See the plugin examples and [HACKING.md](HACKING.md).

**Do I need to dump JSON to view HTML?**  
By design, yes: JSON is the interchange format. That also lets you archive/report results independently of source code.

**How do I run only specific plugins?**  
Use the `-m`/`--modules` option: `sru-lint check -m changelog-entry,patch-format my.patch`

**What's the difference between console and JSON output?**  
Console output shows human-friendly snippets with syntax highlighting and context. JSON output provides structured data suitable for machine processing and integration with other tools.
