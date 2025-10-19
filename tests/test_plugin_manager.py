import unittest
from unittest.mock import patch, MagicMock
from sru_lint.plugin_manager import PluginManager
from sru_lint.plugins.plugin_base import Plugin, ProcessedFile
from sru_lint.common.feedback import SourceSpan, SourceLine
import types
import sys

class DummyPlugin(Plugin):
    def register_file_patterns(self):
        self.add_file_pattern("*.txt")
    
    def process_file(self, processed_file: ProcessedFile):
        pass

class AnotherPlugin(Plugin):
    def register_file_patterns(self):
        self.add_file_pattern("*.py")
    
    def process_file(self, processed_file: ProcessedFile):
        pass

class ThirdPlugin(Plugin):
    def register_file_patterns(self):
        self.add_file_pattern("*.md")
    
    def process_file(self, processed_file: ProcessedFile):
        pass

class NestedDummyPlugin(Plugin):
    def register_file_patterns(self):
        self.add_file_pattern("debian/changelog")
    
    def process_file(self, processed_file: ProcessedFile):
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

def create_test_processed_file(path="test.py", content_lines=None):
    """Helper to create a test ProcessedFile object"""
    if content_lines is None:
        content_lines = ["print('hello')", "return True"]
    
    source_lines = [
        SourceLine(content=line, line_number=i+1, is_added=True)
        for i, line in enumerate(content_lines)
    ]
    
    source_span = SourceSpan(
        path=path,
        start_line=1,
        start_col=1,
        end_line=len(content_lines),
        end_col=1,
        content=source_lines,
        content_with_context=source_lines
    )
    
    return ProcessedFile(path=path, source_span=source_span)

class TestPluginManager(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        self.plugin_manager = PluginManager()
        self.test_processed_files = [
            create_test_processed_file("test.txt", ["Hello world"]),
            create_test_processed_file("test.py", ["print('hello')", "return True"]),
            create_test_processed_file("README.md", ["# Title", "Content"])
        ]

    @patch("sru_lint.common.launchpad_helper.get_launchpad_helper")
    @patch("sru_lint.plugin_manager.importlib.import_module")
    @patch("sru_lint.plugin_manager.pkgutil.iter_modules")
    @patch("sru_lint.plugin_manager.sru_lint.plugins")
    @patch("sru_lint.plugin_manager.inspect.getmembers")
    def test_load_plugins_with_submodules(self, mock_getmembers, mock_plugins, mock_iter_modules, mock_import_module, mock_launchpad_helper):
        """Test loading plugins from submodules"""
        mock_launchpad_helper.return_value = MagicMock()
        
        mock_plugins_module = create_mock_module("sru_lint.plugins", {
            "DummyPlugin": DummyPlugin,
            "AnotherPlugin": AnotherPlugin
        })
        mock_plugins_module.__path__ = ["dummy_path"]
        mock_plugins_module.__name__ = "sru_lint.plugins"
        mock_plugins.__path__ = mock_plugins_module.__path__
        mock_plugins.__name__ = mock_plugins_module.__name__
        
        dummy_plugin_mod = create_mock_module("sru_lint.plugins.dummy_plugin", {
            "DummyPlugin": DummyPlugin
        })
        another_plugin_mod = create_mock_module("sru_lint.plugins.another_plugin", {
            "AnotherPlugin": AnotherPlugin
        })

        def getmembers_side_effect(module, predicate=None):
            if module is mock_plugins:
                return [
                    ("DummyPlugin", DummyPlugin),
                    ("AnotherPlugin", AnotherPlugin)
                ]
            elif module is dummy_plugin_mod:
                return [("DummyPlugin", DummyPlugin)]
            elif module is another_plugin_mod:
                return [("AnotherPlugin", AnotherPlugin)]
            return []
        
        mock_getmembers.side_effect = getmembers_side_effect
        
        mock_iter_modules.return_value = [
            (None, "sru_lint.plugins.dummy_plugin", False),
            (None, "sru_lint.plugins.another_plugin", False)
        ]

        def import_side_effect(name):
            if name == "sru_lint.plugins.dummy_plugin":
                return dummy_plugin_mod
            elif name == "sru_lint.plugins.another_plugin":
                return another_plugin_mod
            return MagicMock()
        
        mock_import_module.side_effect = import_side_effect
        
        plugins = self.plugin_manager.load_plugins()
        self.assertTrue(any(isinstance(p, DummyPlugin) for p in plugins))
        self.assertTrue(any(isinstance(p, AnotherPlugin) for p in plugins))
        self.assertEqual(len(plugins), 2)

    @patch("sru_lint.common.launchpad_helper.get_launchpad_helper")
    @patch("sru_lint.plugin_manager.sru_lint.plugins")
    @patch("sru_lint.plugin_manager.inspect.getmembers")
    def test_load_plugins_no_submodules(self, mock_getmembers, mock_plugins, mock_launchpad_helper):
        """Test loading plugins from main module only"""
        mock_launchpad_helper.return_value = MagicMock()
        
        mock_plugins_module = create_mock_module("sru_lint.plugins", {
            "DummyPlugin": DummyPlugin,
            "AnotherPlugin": AnotherPlugin
        })
        
        mock_getmembers.return_value = [
            ("DummyPlugin", DummyPlugin),
            ("AnotherPlugin", AnotherPlugin)
        ]
        
        plugins = self.plugin_manager.load_plugins()
        self.assertTrue(any(isinstance(p, DummyPlugin) for p in plugins))
        self.assertTrue(any(isinstance(p, AnotherPlugin) for p in plugins))
        self.assertEqual(len(plugins), 2)

    @patch("sru_lint.common.launchpad_helper.get_launchpad_helper")
    @patch("sru_lint.plugin_manager.pkgutil.iter_modules")
    @patch("sru_lint.plugin_manager.sru_lint.plugins")
    @patch("sru_lint.plugin_manager.inspect.getmembers")
    def test_load_plugins_filters_base_plugin_class(self, mock_getmembers, mock_plugins, mock_iter_modules, mock_launchpad_helper):
        """Test that the base Plugin class itself is not instantiated"""
        mock_launchpad_helper.return_value = MagicMock()
        
        mock_plugins_module = create_mock_module("sru_lint.plugins", {
            "DummyPlugin": DummyPlugin,
            "Plugin": Plugin
        })
        mock_plugins_module.__path__ = ["dummy_path"]
        mock_plugins_module.__name__ = "sru_lint.plugins"
        mock_plugins.__path__ = mock_plugins_module.__path__
        mock_plugins.__name__ = mock_plugins_module.__name__
        
        mock_getmembers.return_value = [
            ("DummyPlugin", DummyPlugin),
            ("Plugin", Plugin)
        ]
        
        mock_iter_modules.return_value = []
        
        plugins = self.plugin_manager.load_plugins()
        
        self.assertEqual(len(plugins), 1)
        self.assertIsInstance(plugins[0], DummyPlugin)
        self.assertFalse(any(p.__class__ is Plugin for p in plugins))

    @patch("sru_lint.common.launchpad_helper.get_launchpad_helper")
    @patch("sru_lint.plugin_manager.pkgutil.iter_modules")
    @patch("sru_lint.plugin_manager.sru_lint.plugins")
    @patch("sru_lint.plugin_manager.inspect.getmembers")
    def test_load_plugins_filters_non_plugin_classes(self, mock_getmembers, mock_plugins, mock_iter_modules, mock_launchpad_helper):
        """Test that non-Plugin classes are not instantiated"""
        mock_launchpad_helper.return_value = MagicMock()
        
        mock_plugins_module = create_mock_module("sru_lint.plugins", {
            "DummyPlugin": DummyPlugin,
            "NotAPlugin": NotAPlugin
        })
        mock_plugins_module.__path__ = ["dummy_path"]
        mock_plugins_module.__name__ = "sru_lint.plugins"
        mock_plugins.__path__ = mock_plugins_module.__path__
        mock_plugins.__name__ = mock_plugins_module.__name__
        
        mock_getmembers.return_value = [
            ("DummyPlugin", DummyPlugin),
            ("NotAPlugin", NotAPlugin)
        ]
        
        mock_iter_modules.return_value = []
        
        plugins = self.plugin_manager.load_plugins()
        
        self.assertEqual(len(plugins), 1)
        self.assertIsInstance(plugins[0], DummyPlugin)
        self.assertFalse(any(isinstance(p, NotAPlugin) for p in plugins))

    @patch("sru_lint.common.launchpad_helper.get_launchpad_helper")
    @patch("sru_lint.plugin_manager.importlib.import_module")
    @patch("sru_lint.plugin_manager.pkgutil.iter_modules")
    @patch("sru_lint.plugin_manager.sru_lint.plugins")
    @patch("sru_lint.plugin_manager.inspect.getmembers")
    def test_load_plugins_handles_duplicate_classes(self, mock_getmembers, mock_plugins, mock_iter_modules, mock_import_module, mock_launchpad_helper):
        """Test that duplicate plugin classes are not instantiated multiple times"""
        mock_launchpad_helper.return_value = MagicMock()
        
        mock_plugins_module = create_mock_module("sru_lint.plugins", {
            "DummyPlugin": DummyPlugin
        })
        mock_plugins_module.__path__ = ["dummy_path"]
        mock_plugins_module.__name__ = "sru_lint.plugins"
        mock_plugins.__path__ = mock_plugins_module.__path__
        mock_plugins.__name__ = mock_plugins_module.__name__
        
        duplicate_module = create_mock_module("sru_lint.plugins.duplicate_module", {
            "DummyPlugin": DummyPlugin
        })
        
        def getmembers_side_effect(module, predicate=None):
            if module is mock_plugins:
                return [("DummyPlugin", DummyPlugin)]
            elif module is duplicate_module:
                return [("DummyPlugin", DummyPlugin)]
            return []
        
        mock_getmembers.side_effect = getmembers_side_effect
        
        mock_iter_modules.return_value = [
            (None, "sru_lint.plugins.duplicate_module", False)
        ]
        
        mock_import_module.return_value = duplicate_module
        
        plugins = self.plugin_manager.load_plugins()
        
        self.assertEqual(len(plugins), 1)
        self.assertIsInstance(plugins[0], DummyPlugin)

    @patch("sru_lint.common.launchpad_helper.get_launchpad_helper")
    @patch("sru_lint.plugin_manager.pkgutil.iter_modules")
    @patch("sru_lint.plugin_manager.sru_lint.plugins")
    @patch("sru_lint.plugin_manager.inspect.getmembers")
    def test_load_plugins_only_processes_classes(self, mock_getmembers, mock_plugins, mock_iter_modules, mock_launchpad_helper):
        """Test that plugin loading only processes actual class objects"""
        mock_launchpad_helper.return_value = MagicMock()
        
        mock_plugins_module = create_mock_module("sru_lint.plugins", {
            "DummyPlugin": DummyPlugin
        })
        mock_plugins_module.__path__ = ["dummy_path"]
        mock_plugins_module.__name__ = "sru_lint.plugins"
        mock_plugins.__path__ = mock_plugins_module.__path__
        mock_plugins.__name__ = mock_plugins_module.__name__
        
        mock_getmembers.return_value = [
            ("DummyPlugin", DummyPlugin),
            ("Plugin", Plugin)
        ]
        
        mock_iter_modules.return_value = []
        
        plugins = self.plugin_manager.load_plugins()
        
        self.assertEqual(len(plugins), 1)
        self.assertIsInstance(plugins[0], DummyPlugin)

    @patch("sru_lint.plugin_manager.pkgutil.iter_modules")
    def test_import_submodules_recursively_handles_non_package(self, mock_iter_modules):
        """Test that _import_submodules_recursively returns early for non-packages"""
        non_package_module = types.ModuleType("non_package")
        
        self.plugin_manager._import_submodules_recursively(non_package_module)
        
        mock_iter_modules.assert_not_called()

    @patch("sru_lint.plugin_manager.pkgutil.iter_modules")
    @patch("sru_lint.plugin_manager.sru_lint.plugins")
    @patch("sru_lint.plugin_manager.inspect.getmembers")
    def test_load_plugins_empty_package(self, mock_getmembers, mock_plugins, mock_iter_modules):
        """Test loading from an empty package (no plugins found)"""
        mock_plugins_module = types.ModuleType("sru_lint.plugins")
        mock_plugins_module.__path__ = ["dummy_path"]
        mock_plugins_module.__name__ = "sru_lint.plugins"
        mock_plugins.__path__ = mock_plugins_module.__path__
        mock_plugins.__name__ = mock_plugins_module.__name__
        
        mock_getmembers.return_value = []
        mock_iter_modules.return_value = []
        
        plugins = self.plugin_manager.load_plugins()
        self.assertEqual(len(plugins), 0)

    @patch("sru_lint.common.launchpad_helper.get_launchpad_helper")
    @patch("sru_lint.plugin_manager.importlib.import_module")
    @patch("sru_lint.plugin_manager.pkgutil.iter_modules")
    @patch("sru_lint.plugin_manager.sru_lint.plugins")
    @patch("sru_lint.plugin_manager.inspect.getmembers")
    def test_load_plugins_handles_generic_exception(self, mock_getmembers, mock_plugins, mock_iter_modules, mock_import_module, mock_launchpad_helper):
        """Test that generic exceptions during import are caught and handled"""
        mock_launchpad_helper.return_value = MagicMock()
        
        mock_plugins_module = create_mock_module("sru_lint.plugins", {
            "DummyPlugin": DummyPlugin
        })
        mock_plugins_module.__path__ = ["dummy_path"]
        mock_plugins_module.__name__ = "sru_lint.plugins"
        mock_plugins.__path__ = mock_plugins_module.__path__
        mock_plugins.__name__ = mock_plugins_module.__name__
        
        def getmembers_side_effect(module, predicate=None):
            if module is mock_plugins:
                return [("DummyPlugin", DummyPlugin)]
            return []
        
        mock_getmembers.side_effect = getmembers_side_effect
        
        mock_iter_modules.return_value = [
            (None, "sru_lint.plugins.error_module", False)
        ]
        
        mock_import_module.side_effect = RuntimeError("Unexpected error")
        
        plugins = self.plugin_manager.load_plugins()
        
        self.assertEqual(len(plugins), 1)
        self.assertIsInstance(plugins[0], DummyPlugin)

    @patch("sru_lint.common.launchpad_helper.get_launchpad_helper")
    def test_plugin_initialization(self, mock_launchpad_helper):
        """Test plugin initialization and basic functionality"""
        mock_launchpad_helper.return_value = MagicMock()
        
        plugin = DummyPlugin()
        
        # Test basic properties
        self.assertIsInstance(plugin.feedback, list)
        self.assertTrue(hasattr(plugin, 'logger'))
        self.assertEqual(plugin.__symbolic_name__, "dummy-plugin")
        
        # Test file pattern matching
        self.assertTrue(plugin.matches_file("test.txt"))
        self.assertTrue(plugin.matches_file("path/to/test.txt"))
        self.assertFalse(plugin.matches_file("test.py"))

    @patch("sru_lint.common.launchpad_helper.get_launchpad_helper")
    def test_plugin_feedback_management(self, mock_launchpad_helper):
        """Test plugin feedback collection functionality"""
        mock_launchpad_helper.return_value = MagicMock()
        
        plugin = DummyPlugin()
        
        # Initially empty
        self.assertEqual(len(plugin.feedback), 0)
        
        # Test processing clears feedback
        processed_files = [create_test_processed_file("test.txt")]
        feedback = plugin.process(processed_files)
        
        self.assertIs(feedback, plugin.feedback)
        
        # Test multiple calls clear previous feedback
        plugin.feedback.append(MagicMock())
        self.assertEqual(len(plugin.feedback), 1)
        
        feedback = plugin.process(processed_files)
        self.assertEqual(len(plugin.feedback), 0)

    @patch("sru_lint.common.launchpad_helper.get_launchpad_helper")
    def test_plugin_symbolic_name_generation(self, mock_launchpad_helper):
        """Test plugin symbolic name generation"""
        mock_launchpad_helper.return_value = MagicMock()
        
        dummy_plugin = DummyPlugin()
        self.assertEqual(dummy_plugin.__symbolic_name__, "dummy-plugin")
        
        another_plugin = AnotherPlugin()
        self.assertEqual(another_plugin.__symbolic_name__, "another-plugin")
        
        nested_plugin = NestedDummyPlugin()
        self.assertEqual(nested_plugin.__symbolic_name__, "nested-dummy-plugin")

    @patch("sru_lint.common.launchpad_helper.get_launchpad_helper")
    def test_plugin_logger_initialization(self, mock_launchpad_helper):
        """Test that plugins have properly initialized loggers"""
        mock_launchpad_helper.return_value = MagicMock()
        
        plugin = DummyPlugin()
        
        self.assertTrue(hasattr(plugin, 'logger'))
        self.assertIsNotNone(plugin.logger)
        
        expected_name = f"sru-lint.plugins.{plugin.__symbolic_name__}"
        self.assertEqual(plugin.logger.name, expected_name)

    @patch("sru_lint.common.launchpad_helper.get_launchpad_helper")
    def test_plugin_create_feedback_helpers(self, mock_launchpad_helper):
        """Test plugin feedback creation helper methods"""
        mock_launchpad_helper.return_value = MagicMock()
        
        plugin = DummyPlugin()
        processed_file = create_test_processed_file("test.txt", ["Hello world", "Second line"])
        
        # Test create_feedback method
        feedback = plugin.create_feedback(
            message="Test message",
            rule_id="TEST001",
            source_span=processed_file.source_span,
            line_number=2
        )
        
        self.assertEqual(len(plugin.feedback), 1)
        self.assertEqual(plugin.feedback[0], feedback)
        self.assertEqual(feedback.message, "Test message")
        self.assertEqual(feedback.rule_id, "TEST001")
        self.assertEqual(feedback.span.start_line, 2)
        self.assertEqual(feedback.span.path, "test.txt")

    @patch("sru_lint.common.launchpad_helper.get_launchpad_helper")
    def test_plugin_create_line_feedback(self, mock_launchpad_helper):
        """Test plugin line-specific feedback creation"""
        mock_launchpad_helper.return_value = MagicMock()
        
        plugin = DummyPlugin()
        processed_file = create_test_processed_file("test.txt", ["Hello world", "Second line"])
        
        # Test create_line_feedback method
        feedback = plugin.create_line_feedback(
            message="Line-specific message",
            rule_id="TEST002",
            source_span=processed_file.source_span,
            target_line_content="Hello world"
        )
        
        self.assertEqual(len(plugin.feedback), 1)
        self.assertEqual(plugin.feedback[0], feedback)
        self.assertEqual(feedback.span.start_line, 1)
        self.assertEqual(feedback.span.start_col, 1)

    def test_plugin_manager_initialization(self):
        """Test PluginManager initialization"""
        pm = PluginManager()
        self.assertIsInstance(pm, PluginManager)
        
        # Test that load_plugins returns a list
        with patch("sru_lint.plugin_manager.inspect.getmembers") as mock_getmembers:
            mock_getmembers.return_value = []
            plugins = pm.load_plugins()
            self.assertIsInstance(plugins, list)

    @patch("sru_lint.common.launchpad_helper.get_launchpad_helper")
    @patch("sru_lint.plugin_manager.sru_lint.plugins")
    @patch("sru_lint.plugin_manager.inspect.getmembers")
    def test_plugin_manager_multiple_calls(self, mock_getmembers, mock_plugins, mock_launchpad_helper):
        """Test that multiple calls to load_plugins work correctly"""
        mock_launchpad_helper.return_value = MagicMock()
        
        mock_plugins_module = create_mock_module("sru_lint.plugins", {
            "DummyPlugin": DummyPlugin
        })
        
        mock_getmembers.return_value = [
            ("DummyPlugin", DummyPlugin)
        ]
        
        # First call
        plugins1 = self.plugin_manager.load_plugins()
        self.assertEqual(len(plugins1), 1)
        
        # Second call should return new instances
        plugins2 = self.plugin_manager.load_plugins()
        self.assertEqual(len(plugins2), 1)
        
        # Should be different instances
        self.assertIsNot(plugins1[0], plugins2[0])

if __name__ == "__main__":
    unittest.main()