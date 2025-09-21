# sru-lint

Static checks for Ubuntu SRU (Stable Release Update) patches — built to run in CI and to generate human-friendly reports.

- **`sru-lint`**: the fast, scriptable checker (exit codes for CI).
- **`sru-inspect`**: the viewer (renders JSON reports to minimal HTML with annotations).

Under the hood, `sru-lint` parses patches with [`unidiff`](https://pypi.org/project/unidiff/), runs a set of **plugins**, and emits a structured **FeedbackReport** you can render or post-process.

---

## Features

- 🔌 **Plugin architecture**: drop-in checks under `sru_lint.plugins.*`.
- 📄 **Precise locations**: line/column + byte offsets for robust highlighting.
- 🧰 **Extensible report schema**: JSON-serializable `FeedbackReport`.
- 🖥️ **Two UIs**: machine-readable JSON for pipelines, HTML for humans.
- 🧪 **Tests included** (`pytest`).

---

## Install

```bash
# Local dev (editable)
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"     # if you defined a 'dev' extra; otherwise:
pip install -e .

# or with pipx (isolated)
pipx install .
```

> Requires Python 3.10+.

---

## Quick start

Lint a patch file:

```bash
sru-lint path/to/patch.diff --format json > report.json
```

From stdin:

```bash
git show -p HEAD | sru-lint - --format json > report.json
```

Render HTML:

```bash
sru-inspect report.json --html out.html
# or open in your browser:
sru-inspect report.json --open
```

---

## CLI

### `sru-lint` (checker)

```
Usage: sru-lint [FILE|-] [options]

Arguments:
  FILE                   Patch file to read, or "-" for stdin (default: "-")

Options:
  --format [text|json]   Output format (default: text)
  --severity-threshold [info|warning|error]
                         Fail if any finding ≥ threshold (default: error)
  --debian-changelog PATH
                         Override changelog path tail (default: debian/changelog)
  --rule-set NAME        Select a ruleset (future-proof; default: default)
  -q, --quiet            Suppress non-essential output
  -v, --version
  -h, --help
```

**Exit codes**
- `0` – no findings at/above threshold
- `1` – findings at/above threshold
- `2` – usage or internal error

### `sru-inspect` (viewer)

```
Usage: sru-inspect REPORT.json [options]

Options:
  --html PATH            Write an HTML file
  --open                 Render a temp HTML and open in default browser
  -h, --help
```

---

## What it checks (conceptually)

Checks are implemented as **plugins**. You’ll see these placeholders out of the box:

- `ChangelogEntry` – validations around `debian/changelog`.
- `VersionNumber` – version bump semantics.
- `PublicationHistory` – SRU metadata/history.
- `PatchFormat` – unified diff shape, headers, trailers, etc.

> The stub classes are empty on purpose — you implement the logic.

---

## Report schema (summary)

Findings are emitted as a `FeedbackReport` containing `FeedbackItem`s with precise `SourceSpan`s.

```json
{
  "tool_name": "sru-lint",
  "tool_version": "0.1.0",
  "summary": { "error": 1, "warning": 2 },
  "items": [
    {
      "id": "ef76…",
      "rule_id": "FMT001",
      "severity": "warning",
      "message": "Keys should be snake_case.",
      "hint": "Use 'site_title'",
      "doc_url": "https://example.test/rules/FMT001",
      "span": {
        "path": "debian/changelog",
        "start_line": 12, "start_col": 5,
        "end_line": 12,   "end_col": 14,
        "start_offset": 238, "end_offset": 247
      },
      "tags": ["style","yaml"],
      "fixits": []
    }
  ]
}
```

The included minimal HTML template highlights spans and shows an annotation panel. `sru-inspect` uses it under the hood.

---

## Plugins

### Base interface

```python
# src/sru_lint/plugin_base.py
from abc import ABC, abstractmethod
from unidiff import PatchSet  # type: ignore[import-not-found]

class Plugin(ABC):
    """Interface for a patch-processing plugin."""
    name: str = "plugin"

    @abstractmethod
    def process(self, patch: PatchSet, report) -> None:
        """Analyze the PatchSet and add findings to the report."""
        raise NotImplementedError
```

> `report` is your `FeedbackReport` (or a façade exposing `add()`).

### Built-in (empty) plugins

```python
# src/sru_lint/plugins/changelog_entry.py
from sru_lint.plugin_base import Plugin

class ChangelogEntry(Plugin):
    name = "changelog-entry"
    def process(self, patch, report):  # implement me
        pass
```

Similarly: `VersionNumber`, `PublicationHistory`, `PatchFormat`.

### Discovery

`PluginManager` loads all subclasses of `Plugin` from `sru_lint.plugins` and instantiates one of each. Any new class you add under that package is picked up automatically.

---

## Configuration

### Make “changelog path” configurable (still a 1-arg matcher)

If you need a callable `filename -> bool` but want the path to be configurable:

```python
from pathlib import PurePath
from typing import Callable, Union, os
PathLike = Union[str, os.PathLike[str]]

def make_changelog_matcher(changelog_path: str = "debian/changelog") -> Callable[[PathLike], bool]:
    tail = tuple(PurePath(changelog_path).parts)
    def match(filename: PathLike) -> bool:
        parts = PurePath(str(filename)).parts
        return len(parts) >= len(tail) and tuple(parts[-len(tail):]) == tail
    return match

# default matcher
match_changelog = make_changelog_matcher()
```

`--debian-changelog` on `sru-lint` can rebind this at startup.

---

## Usage examples

Lint a patch and fail CI on warnings or worse:

```bash
sru-lint my.patch --format json --severity-threshold warning > report.json
```

Render to HTML and open:

```bash
sru-inspect report.json --open
```

Pipe from `git`:

```bash
git show -p origin/stable..HEAD | sru-lint - --format text
```

---

## Development

### Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install  # if you add a config
```

Suggested (optional) dev deps:
- `pytest`, `pytest-cov`
- `ruff` (lint), `mypy` (types)
- `unidiff`

### Run tests

```bash
pytest -q
```

### Project layout (abridged)

```
src/
  sru_lint/
    __init__.py
    cli.py                 # exposes linter_main() and inspect_main()
    html_report.py         # minimal HTML renderer
    plugin_base.py         # Plugin interface
    plugin_manager.py      # dynamic discovery
    plugins/
      __init__.py
      changelog_entry.py
      version_number.py
      publication_history.py
      patch_format.py
tests/
  test_cli.py
  test_plugins.py
  test_html_report.py
```

### Console scripts (in `pyproject.toml`)

```toml
[project.scripts]
sru-lint = "sru_lint.cli:linter_main"
sru-inspect = "sru_lint.cli:inspect_main"
```

---

## Contributing

- Open an issue for substantial changes.
- Add tests for new behavior.
- Keep plugins single-purpose and fast (they run in CI).

---

## License

Specify your license (e.g., MIT, Apache-2.0) in `LICENSE`.

---

## FAQ

**Why two commands?**  
`sru-lint` matches “linter” expectations in CI; `sru-inspect` focuses on human-friendly triage and doesn’t affect build status.

**Can I add my own checks?**  
Yes — create a new class under `sru_lint.plugins` that subclasses `Plugin`. The manager discovers it automatically.

**Do I need to dump JSON to view HTML?**  
By design, yes: JSON is the interchange format. That also lets you archive/report results independently of source code.
