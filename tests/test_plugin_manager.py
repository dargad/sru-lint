import unittest
from unittest.mock import patch, MagicMock
from sru_lint.plugin_manager import PluginManager
from sru_lint.plugin_base import Plugin
import types
import sys

class DummyPlugin(Plugin):
    def register_file_patterns(self):
        self.add_file_pattern("*.txt")
    
    def process_file(self, patched_file):
        pass

class AnotherPlugin(Plugin):
    def register_file_patterns(self):
        self.add_file_pattern("*.py")
    
    def process_file(self, patched_file):
        pass

class ThirdPlugin(Plugin):
    def register_file_patterns(self):
        self.add_file_pattern("*.md")
    
    def process_file(self, patched_file):
        pass

class NestedDummyPlugin(Plugin):
    def register_file_patterns(self):
        self.add_file_pattern("debian/changelog")
    
    def process_file(self, patched_file):
        pass

class NotAPlugin:
    """This is not a Plugin subclass"""
    pass

def create_mock_module(name, classes):
    """Create a mock module with actual class attributes that inspect.getmembers can find"""
    module = types.ModuleType(name)
    for class_name, class_obj in classes.items():
        setattr(module, class_name, class_obj)
    return module

class TestPluginManager(unittest.TestCase):
    @patch("sru_lint.plugin_manager.importlib.import_module")
    @patch("sru_lint.plugin_manager.pkgutil.iter_modules")
    @patch("sru_lint.plugin_manager.sru_lint.plugins")
    def test_load_plugins_with_submodules(self, mock_plugins, mock_iter_modules, mock_import_module):
        # Create actual module objects instead of MagicMock
        mock_plugins_module = create_mock_module("sru_lint.plugins", {
            "DummyPlugin": DummyPlugin,
            "AnotherPlugin": AnotherPlugin
        })
        mock_plugins_module.__path__ = ["dummy_path"]
        mock_plugins_module.__name__ = "sru_lint.plugins"
        mock_plugins.return_value = mock_plugins_module
        mock_plugins.__path__ = mock_plugins_module.__path__
        mock_plugins.__name__ = mock_plugins_module.__name__
        
        # Copy attributes for inspect.getmembers to work
        for attr in ['DummyPlugin', 'AnotherPlugin']:
            setattr(mock_plugins, attr, getattr(mock_plugins_module, attr))
        
        mock_iter_modules.return_value = [
            (None, "sru_lint.plugins.dummy_plugin", False),
            (None, "sru_lint.plugins.another_plugin", False)
        ]

        # Create actual submodule objects
        dummy_plugin_mod = create_mock_module("sru_lint.plugins.dummy_plugin", {
            "DummyPlugin": DummyPlugin
        })
        another_plugin_mod = create_mock_module("sru_lint.plugins.another_plugin", {
            "AnotherPlugin": AnotherPlugin
        })

        # Add to sys.modules (update, don't replace)
        sys.modules["sru_lint.plugins.dummy_plugin"] = dummy_plugin_mod
        sys.modules["sru_lint.plugins.another_plugin"] = another_plugin_mod
        
        try:
            plugins = PluginManager.load_plugins()
            self.assertTrue(any(isinstance(p, DummyPlugin) for p in plugins))
            self.assertTrue(any(isinstance(p, AnotherPlugin) for p in plugins))
            self.assertEqual(len(plugins), 2)
        finally:
            # Cleanup
            sys.modules.pop("sru_lint.plugins.dummy_plugin", None)
            sys.modules.pop("sru_lint.plugins.another_plugin", None)

    @patch("sru_lint.plugin_manager.sru_lint.plugins")
    def test_load_plugins_no_submodules(self, mock_plugins):
        # Create actual module object
        mock_plugins_module = create_mock_module("sru_lint.plugins", {
            "DummyPlugin": DummyPlugin,
            "AnotherPlugin": AnotherPlugin
        })
        
        # Copy attributes for inspect.getmembers to work
        for attr in ['DummyPlugin', 'AnotherPlugin']:
            setattr(mock_plugins, attr, getattr(mock_plugins_module, attr))
        
        plugins = PluginManager.load_plugins()
        self.assertTrue(any(isinstance(p, DummyPlugin) for p in plugins))
        self.assertTrue(any(isinstance(p, AnotherPlugin) for p in plugins))
        self.assertEqual(len(plugins), 2)

    @patch("sru_lint.plugin_manager.importlib.import_module")
    @patch("sru_lint.plugin_manager.pkgutil.iter_modules")
    @patch("sru_lint.plugin_manager.sru_lint.plugins")
    def test_load_plugins_with_nested_packages(self, mock_plugins, mock_iter_modules, mock_import_module):
        """Test loading plugins from nested package structure (e.g., sru_lint.plugins.nested.dummy_plugin)"""
        mock_plugins_module = types.ModuleType("sru_lint.plugins")
        mock_plugins_module.__path__ = ["dummy_path"]
        mock_plugins_module.__name__ = "sru_lint.plugins"
        mock_plugins.__path__ = mock_plugins_module.__path__
        mock_plugins.__name__ = mock_plugins_module.__name__
        
        # Create nested package and module as actual module objects
        nested_package = types.ModuleType("sru_lint.plugins.nested")
        nested_package.__path__ = ["nested_path"]
        nested_package.__name__ = "sru_lint.plugins.nested"
        
        nested_dummy_plugin_mod = create_mock_module("sru_lint.plugins.nested.dummy_plugin", {
            "NestedDummyPlugin": NestedDummyPlugin
        })
        
        # Mock iter_modules to return nested package on first call, nested module on recursive call
        def iter_modules_side_effect(path, prefix):
            if prefix == "sru_lint.plugins.":
                return [(None, "sru_lint.plugins.nested", True)]
            elif prefix == "sru_lint.plugins.nested.":
                return [(None, "sru_lint.plugins.nested.dummy_plugin", False)]
            return []
        
        mock_iter_modules.side_effect = iter_modules_side_effect
        
        # Mock import_module to return the nested package and module
        def import_module_side_effect(name):
            if name == "sru_lint.plugins.nested":
                return nested_package
            elif name == "sru_lint.plugins.nested.dummy_plugin":
                return nested_dummy_plugin_mod
            return MagicMock()
        
        mock_import_module.side_effect = import_module_side_effect
        
        # Add to sys.modules
        sys.modules["sru_lint.plugins.nested"] = nested_package
        sys.modules["sru_lint.plugins.nested.dummy_plugin"] = nested_dummy_plugin_mod
        
        try:
            plugins = PluginManager.load_plugins()
            
            # Should find the plugin in the nested module
            self.assertEqual(len(plugins), 1)
            self.assertIsInstance(plugins[0], NestedDummyPlugin)
        finally:
            # Cleanup
            sys.modules.pop("sru_lint.plugins.nested", None)
            sys.modules.pop("sru_lint.plugins.nested.dummy_plugin", None)

    @patch("sru_lint.plugin_manager.pkgutil.iter_modules")
    @patch("sru_lint.plugin_manager.sru_lint.plugins")
    def test_load_plugins_filters_base_plugin_class(self, mock_plugins, mock_iter_modules):
        """Test that the base Plugin class itself is not instantiated"""
        mock_plugins_module = create_mock_module("sru_lint.plugins", {
            "DummyPlugin": DummyPlugin,
            "Plugin": Plugin
        })
        mock_plugins_module.__path__ = ["dummy_path"]
        mock_plugins_module.__name__ = "sru_lint.plugins"
        mock_plugins.__path__ = mock_plugins_module.__path__
        mock_plugins.__name__ = mock_plugins_module.__name__
        
        # Copy attributes for inspect.getmembers to work
        for attr in ['DummyPlugin', 'Plugin']:
            setattr(mock_plugins, attr, getattr(mock_plugins_module, attr))
        
        mock_iter_modules.return_value = []
        
        plugins = PluginManager.load_plugins()
        
        # Should only have DummyPlugin, not the base Plugin class
        self.assertEqual(len(plugins), 1)
        self.assertIsInstance(plugins[0], DummyPlugin)
        self.assertFalse(any(p.__class__ is Plugin for p in plugins))

    @patch("sru_lint.plugin_manager.pkgutil.iter_modules")
    @patch("sru_lint.plugin_manager.sru_lint.plugins")
    def test_load_plugins_filters_non_plugin_classes(self, mock_plugins, mock_iter_modules):
        """Test that non-Plugin classes are not instantiated"""
        mock_plugins_module = create_mock_module("sru_lint.plugins", {
            "DummyPlugin": DummyPlugin,
            "NotAPlugin": NotAPlugin
        })
        mock_plugins_module.__path__ = ["dummy_path"]
        mock_plugins_module.__name__ = "sru_lint.plugins"
        mock_plugins.__path__ = mock_plugins_module.__path__
        mock_plugins.__name__ = mock_plugins_module.__name__
        
        # Copy attributes for inspect.getmembers to work
        for attr in ['DummyPlugin', 'NotAPlugin']:
            setattr(mock_plugins, attr, getattr(mock_plugins_module, attr))
        
        mock_iter_modules.return_value = []
        
        plugins = PluginManager.load_plugins()
        
        # Should only have DummyPlugin
        self.assertEqual(len(plugins), 1)
        self.assertIsInstance(plugins[0], DummyPlugin)
        self.assertFalse(any(isinstance(p, NotAPlugin) for p in plugins))

    @patch("sru_lint.plugin_manager.importlib.import_module")
    @patch("sru_lint.plugin_manager.pkgutil.iter_modules")
    @patch("sru_lint.plugin_manager.sru_lint.plugins")
    def test_load_plugins_handles_duplicate_classes(self, mock_plugins, mock_iter_modules, mock_import_module):
        """Test that duplicate plugin classes are not instantiated multiple times"""
        mock_plugins_module = create_mock_module("sru_lint.plugins", {
            "DummyPlugin": DummyPlugin
        })
        mock_plugins_module.__path__ = ["dummy_path"]
        mock_plugins_module.__name__ = "sru_lint.plugins"
        mock_plugins.__path__ = mock_plugins_module.__path__
        mock_plugins.__name__ = mock_plugins_module.__name__
        
        # Copy attributes for inspect.getmembers to work
        setattr(mock_plugins, 'DummyPlugin', DummyPlugin)
        
        mock_iter_modules.return_value = [
            (None, "sru_lint.plugins.duplicate_module", False)
        ]
        
        duplicate_module = create_mock_module("sru_lint.plugins.duplicate_module", {
            "DummyPlugin": DummyPlugin
        })
        
        # Add to sys.modules
        sys.modules["sru_lint.plugins.duplicate_module"] = duplicate_module
        
        try:
            plugins = PluginManager.load_plugins()
            
            # Should only have one instance despite appearing in multiple places
            self.assertEqual(len(plugins), 1)
            self.assertIsInstance(plugins[0], DummyPlugin)
        finally:
            # Cleanup
            sys.modules.pop("sru_lint.plugins.duplicate_module", None)

    @patch("sru_lint.plugin_manager.importlib.import_module")
    @patch("sru_lint.plugin_manager.pkgutil.iter_modules")
    @patch("sru_lint.plugin_manager.sru_lint.plugins")
    def test_load_plugins_handles_import_errors(self, mock_plugins, mock_iter_modules, mock_import_module):
        """Test that plugin loading continues even if a submodule import fails"""
        mock_plugins_module = create_mock_module("sru_lint.plugins", {
            "DummyPlugin": DummyPlugin
        })
        mock_plugins_module.__path__ = ["dummy_path"]
        mock_plugins_module.__name__ = "sru_lint.plugins"
        mock_plugins.__path__ = mock_plugins_module.__path__
        mock_plugins.__name__ = mock_plugins_module.__name__
        
        # Copy attributes for inspect.getmembers to work
        setattr(mock_plugins, 'DummyPlugin', DummyPlugin)
        
        mock_iter_modules.return_value = [
            (None, "sru_lint.plugins.good_module", False),
            (None, "sru_lint.plugins.bad_module", False)
        ]
        
        # One module imports successfully, another fails
        def side_effect(module_name):
            if module_name == "sru_lint.plugins.bad_module":
                raise ImportError("Module not found")
            return MagicMock()
        
        mock_import_module.side_effect = side_effect
        
        good_module = create_mock_module("sru_lint.plugins.good_module", {
            "AnotherPlugin": AnotherPlugin
        })
        
        # Add to sys.modules
        sys.modules["sru_lint.plugins.good_module"] = good_module
        
        try:
            # Should not raise an exception
            plugins = PluginManager.load_plugins()
            
            # Should still load plugins from successful imports
            self.assertEqual(len(plugins), 2)
            self.assertTrue(any(isinstance(p, DummyPlugin) for p in plugins))
            self.assertTrue(any(isinstance(p, AnotherPlugin) for p in plugins))
        finally:
            # Cleanup
            sys.modules.pop("sru_lint.plugins.good_module", None)

    @patch("sru_lint.plugin_manager.pkgutil.iter_modules")
    @patch("sru_lint.plugin_manager.sru_lint.plugins")
    def test_load_plugins_handles_typeerror_on_issubclass(self, mock_plugins, mock_iter_modules):
        """Test that TypeError from issubclass is handled gracefully"""
        mock_plugins_module = create_mock_module("sru_lint.plugins", {
            "DummyPlugin": DummyPlugin
        })
        mock_plugins_module.__path__ = ["dummy_path"]
        mock_plugins_module.__name__ = "sru_lint.plugins"
        mock_plugins.__path__ = mock_plugins_module.__path__
        mock_plugins.__name__ = mock_plugins_module.__name__
        
        # Add a non-class object that will cause TypeError
        mock_plugins_module.NotARealClass = "not_a_class"
        setattr(mock_plugins, 'DummyPlugin', DummyPlugin)
        setattr(mock_plugins, 'NotARealClass', "not_a_class")
        
        mock_iter_modules.return_value = []
        
        # Should not raise an exception
        plugins = PluginManager.load_plugins()
        
        # Should only have the valid plugin
        self.assertEqual(len(plugins), 1)
        self.assertIsInstance(plugins[0], DummyPlugin)

    @patch("sru_lint.plugin_manager.importlib.import_module")
    @patch("sru_lint.plugin_manager.pkgutil.iter_modules")
    @patch("sru_lint.plugin_manager.sru_lint.plugins")
    def test_load_plugins_filters_sys_modules_correctly(self, mock_plugins, mock_iter_modules, mock_import_module):
        """Test that sys.modules filtering only includes sru_lint.plugins.* modules"""
        mock_plugins_module = types.ModuleType("sru_lint.plugins")
        mock_plugins_module.__path__ = ["dummy_path"]
        mock_plugins_module.__name__ = "sru_lint.plugins"
        mock_plugins.__path__ = mock_plugins_module.__path__
        mock_plugins.__name__ = mock_plugins_module.__name__
        
        mock_iter_modules.return_value = []
        
        # Create modules with various names
        plugin_module = create_mock_module("sru_lint.plugins.valid_module", {
            "DummyPlugin": DummyPlugin
        })
        
        other_sru_module = create_mock_module("sru_lint.other_package.module", {
            "AnotherPlugin": AnotherPlugin
        })
        
        unrelated_module = create_mock_module("some_other_package.module", {
            "ThirdPlugin": ThirdPlugin
        })
        
        # Add to sys.modules
        sys.modules["sru_lint.plugins.valid_module"] = plugin_module
        sys.modules["sru_lint.other_package.module"] = other_sru_module
        sys.modules["some_other_package.module"] = unrelated_module
        
        try:
            plugins = PluginManager.load_plugins()
            
            # Should only load from sru_lint.plugins.* modules
            self.assertEqual(len(plugins), 1)
            self.assertIsInstance(plugins[0], DummyPlugin)
        finally:
            # Cleanup
            sys.modules.pop("sru_lint.plugins.valid_module", None)
            sys.modules.pop("sru_lint.other_package.module", None)
            sys.modules.pop("some_other_package.module", None)

    @patch("sru_lint.plugin_manager.pkgutil.iter_modules")
    def test_import_submodules_recursively_handles_non_package(self, mock_iter_modules):
        """Test that _import_submodules_recursively returns early for non-packages"""
        # Create a module without __path__ (not a package)
        non_package_module = types.ModuleType("non_package")
        
        # Should not call iter_modules
        PluginManager._import_submodules_recursively(non_package_module)
        
        # iter_modules should not have been called
        mock_iter_modules.assert_not_called()

    @patch("sru_lint.plugin_manager.pkgutil.iter_modules")
    @patch("sru_lint.plugin_manager.sru_lint.plugins")
    def test_load_plugins_empty_package(self, mock_plugins, mock_iter_modules):
        """Test loading from an empty package (no plugins found)"""
        mock_plugins_module = types.ModuleType("sru_lint.plugins")
        mock_plugins_module.__path__ = ["dummy_path"]
        mock_plugins_module.__name__ = "sru_lint.plugins"
        mock_plugins.__path__ = mock_plugins_module.__path__
        mock_plugins.__name__ = mock_plugins_module.__name__
        
        mock_iter_modules.return_value = []
        
        plugins = PluginManager.load_plugins()
        self.assertEqual(len(plugins), 0)

    @patch("sru_lint.plugin_manager.importlib.import_module")
    @patch("sru_lint.plugin_manager.pkgutil.iter_modules")
    @patch("sru_lint.plugin_manager.sru_lint.plugins")
    def test_load_plugins_handles_generic_exception(self, mock_plugins, mock_iter_modules, mock_import_module):
        """Test that generic exceptions during import are caught and handled"""
        mock_plugins_module = create_mock_module("sru_lint.plugins", {
            "DummyPlugin": DummyPlugin
        })
        mock_plugins_module.__path__ = ["dummy_path"]
        mock_plugins_module.__name__ = "sru_lint.plugins"
        mock_plugins.__path__ = mock_plugins_module.__path__
        mock_plugins.__name__ = mock_plugins_module.__name__
        
        # Copy attributes for inspect.getmembers to work
        setattr(mock_plugins, 'DummyPlugin', DummyPlugin)
        
        mock_iter_modules.return_value = [
            (None, "sru_lint.plugins.error_module", False)
        ]
        
        # Raise a generic exception
        mock_import_module.side_effect = RuntimeError("Unexpected error")
        
        # Should not raise an exception
        plugins = PluginManager.load_plugins()
        
        # Should still load plugins from the main module
        self.assertEqual(len(plugins), 1)
        self.assertIsInstance(plugins[0], DummyPlugin)

if __name__ == "__main__":
    unittest.main()