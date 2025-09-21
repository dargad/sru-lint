from sru_lint.plugin_base import Plugin


class VersionNumber(Plugin):
    """Plugin to verify version number updates in the patch (implementation pending)."""
    def process(self, patch):
        print("VersionNumber")