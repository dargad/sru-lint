import unittest
from unittest.mock import patch, MagicMock
from sru_lint.plugin_manager import PluginManager
from sru_lint.plugin_base import Plugin

class DummyPlugin(Plugin):
    def process(self, patches):
        return super().process(patches)

class AnotherPlugin(Plugin):
    def process(self, patches):
        return super().process(patches)

class TestPluginManager(unittest.TestCase):
    @patch("sru_lint.plugin_manager.importlib.import_module")
    @patch("sru_lint.plugin_manager.pkgutil.iter_modules")
    @patch("sru_lint.plugins", new_callable=MagicMock)
    def test_load_plugins_with_submodules(self, mock_plugins, mock_iter_modules, mock_import_module):
        # Simulate plugins as a package
        mock_plugins.__path__ = ["dummy_path"]
        mock_plugins.__name__ = "sru_lint.plugins"
        mock_iter_modules.return_value = [
            (None, "sru_lint.plugins.dummy_plugin", False),
            (None, "sru_lint.plugins.another_plugin", False)
        ]
        # Simulate Plugin subclasses in plugins
        setattr(mock_plugins, "DummyPlugin", DummyPlugin)
        setattr(mock_plugins, "AnotherPlugin", AnotherPlugin)

        # Simulate sys.modules for submodules
        dummy_plugin_mod = MagicMock()
        another_plugin_mod = MagicMock()
        setattr(dummy_plugin_mod, "DummyPlugin", DummyPlugin)
        setattr(another_plugin_mod, "AnotherPlugin", AnotherPlugin)

        sys_modules_patch = {
            "sru_lint.plugins.dummy_plugin": dummy_plugin_mod,
            "sru_lint.plugins.another_plugin": another_plugin_mod
        }

        with patch("sru_lint.plugin_manager.sys.modules", sys_modules_patch):
            plugins = PluginManager.load_plugins()
            self.assertTrue(any(isinstance(p, DummyPlugin) for p in plugins))
            self.assertTrue(any(isinstance(p, AnotherPlugin) for p in plugins))
            self.assertEqual(len(plugins), 2)

    @patch("sru_lint.plugins", new_callable=MagicMock)
    def test_load_plugins_no_submodules(self, mock_plugins):
        # Simulate plugins as a module (not a package)
        if hasattr(mock_plugins, "__path__"):
            delattr(mock_plugins, "__path__")
        setattr(mock_plugins, "DummyPlugin", DummyPlugin)
        setattr(mock_plugins, "AnotherPlugin", AnotherPlugin)

        plugins = PluginManager.load_plugins()
        self.assertTrue(any(isinstance(p, DummyPlugin) for p in plugins))
        self.assertTrue(any(isinstance(p, AnotherPlugin) for p in plugins))
        self.assertEqual(len(plugins), 2)

if __name__ == "__main__":
    unittest.main()