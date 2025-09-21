from sru_lint.plugin_base import Plugin


class ChangelogEntry(Plugin):
    """Plugin to check for changelog entry in the patch (implementation pending)."""
    def process(self, patch):
        print("ChangelogEntry")
        patch