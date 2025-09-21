from sru_lint.plugin_base import Plugin


class PublicationHistory(Plugin):
    """Plugin to validate publication history in the patch (implementation pending)."""
    def process(self, patch):
        print("PublicationHistory")