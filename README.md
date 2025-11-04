# sru-lint

Static analysis tool for Ubuntu SRU (Stable Release Update) patches — built to run in CI and generate human-friendly reports.

## Documentation

**For complete documentation, installation instructions, usage examples, and plugin development guides, visit:**

**[https://canonical-sru-lint.readthedocs-hosted.com/en/latest/](https://canonical-sru-lint.readthedocs-hosted.com/en/latest/)**

## Quick Start

```bash
# Install from snap (recommended)
snap install --edge sru-lint

# Or install with Poetry (for development)
git clone https://github.com/dargad/sru-lint.git
cd sru-lint
poetry install

# Check a patch file or URL
sru-lint check path/to/patch.debdiff  # if installed via snap
poetry run sru-lint check path/to/patch.debdiff  # if using Poetry
sru-lint check https://example.com/patch.diff

# Check from stdin
cat patch.debdiff | sru-lint check -  # if installed via snap
cat patch.debdiff | poetry run sru-lint check -  # if using Poetry

# List available plugins
sru-lint plugins  # if installed via snap
poetry run sru-lint plugins  # if using Poetry
```

## What it checks

- **Changelog entries** (valid distributions, LP bugs, version ordering)
- **DEP-3 patch format** compliance
- **Launchpad integration** (bug targeting, SRU templates, publication history)
- **Upload queue** conflicts
- And more via the plugin system...

## License

MIT License - see [LICENSE](LICENSE) for details.
