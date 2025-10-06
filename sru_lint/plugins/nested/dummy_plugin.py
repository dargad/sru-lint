from sru_lint.plugins.plugin_base import Plugin


class DummyPlugin(Plugin):
    """A dummy plugin for testing purposes."""
    def process(self, patches):
        print("DummyPlugin processing patches")
        return True