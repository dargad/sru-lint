import unittest
from unittest.mock import patch, MagicMock, mock_open
from io import StringIO
import typer
from typer.testing import CliRunner
from sru_lint.cli import app


class TestCLI(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    @patch('sru_lint.cli.unidiff.PatchSet')
    @patch('sru_lint.cli.PluginManager')
    def test_check_command_default_modules(self, mock_plugin_manager, mock_patchset):
        """Test check command with default 'all' modules"""
        mock_pm = MagicMock()
        mock_plugin_manager.return_value = mock_pm
        
        mock_plugin1 = MagicMock()
        mock_plugin1.__symbolic_name__ = 'plugin1'
        mock_plugin2 = MagicMock()
        mock_plugin2.__symbolic_name__ = 'plugin2'
        mock_pm.load_plugins.return_value = [mock_plugin1, mock_plugin2]
        
        mock_patchset_instance = MagicMock()
        mock_patchset.return_value = mock_patchset_instance
        
        # Create a mock file with patch content
        with patch('builtins.open', mock_open(read_data='patch content')):
            result = self.runner.invoke(app, ['check', '-'])
        
        self.assertEqual(result.exit_code, 0)
        mock_plugin1.process.assert_called_once_with(mock_patchset_instance)
        mock_plugin2.process.assert_called_once_with(mock_patchset_instance)

    @patch('sru_lint.cli.unidiff.PatchSet')
    @patch('sru_lint.cli.PluginManager')
    def test_check_command_specific_modules(self, mock_plugin_manager, mock_patchset):
        """Test check command with specific modules"""
        mock_pm = MagicMock()
        mock_plugin_manager.return_value = mock_pm
        
        mock_plugin1 = MagicMock()
        mock_plugin1.__symbolic_name__ = 'plugin1'
        mock_plugin2 = MagicMock()
        mock_plugin2.__symbolic_name__ = 'plugin2'
        mock_pm.load_plugins.return_value = [mock_plugin1, mock_plugin2]
        
        mock_patchset_instance = MagicMock()
        mock_patchset.return_value = mock_patchset_instance
        
        with patch('builtins.open', mock_open(read_data='patch content')):
            result = self.runner.invoke(app, ['check', '-', '--modules', 'plugin1'])
        
        self.assertEqual(result.exit_code, 0)
        mock_plugin1.process.assert_called_once_with(mock_patchset_instance)
        mock_plugin2.process.assert_not_called()

    @patch('sru_lint.cli.unidiff.PatchSet')
    @patch('sru_lint.cli.PluginManager')
    def test_check_command_comma_separated_modules(self, mock_plugin_manager, mock_patchset):
        """Test check command with comma-separated modules"""
        mock_pm = MagicMock()
        mock_plugin_manager.return_value = mock_pm
        
        mock_plugin1 = MagicMock()
        mock_plugin1.__symbolic_name__ = 'plugin1'
        mock_plugin2 = MagicMock()
        mock_plugin2.__symbolic_name__ = 'plugin2'
        mock_plugin3 = MagicMock()
        mock_plugin3.__symbolic_name__ = 'plugin3'
        mock_pm.load_plugins.return_value = [mock_plugin1, mock_plugin2, mock_plugin3]
        
        mock_patchset_instance = MagicMock()
        mock_patchset.return_value = mock_patchset_instance
        
        with patch('builtins.open', mock_open(read_data='patch content')):
            result = self.runner.invoke(app, ['check', '-', '--modules', 'plugin1,plugin2'])
        
        self.assertEqual(result.exit_code, 0)
        mock_plugin1.process.assert_called_once_with(mock_patchset_instance)
        mock_plugin2.process.assert_called_once_with(mock_patchset_instance)
        mock_plugin3.process.assert_not_called()

    @patch('sru_lint.cli.unidiff.PatchSet')
    @patch('sru_lint.cli.PluginManager')
    def test_check_command_nonexistent_modules(self, mock_plugin_manager, mock_patchset):
        """Test check command with nonexistent modules"""
        mock_pm = MagicMock()
        mock_plugin_manager.return_value = mock_pm
        
        mock_plugin1 = MagicMock()
        mock_plugin1.__symbolic_name__ = 'plugin1'
        mock_pm.load_plugins.return_value = [mock_plugin1]
        
        mock_patchset_instance = MagicMock()
        mock_patchset.return_value = mock_patchset_instance
        
        with patch('builtins.open', mock_open(read_data='patch content')):
            result = self.runner.invoke(app, ['check', '-', '--modules', 'nonexistent'])
        
        self.assertEqual(result.exit_code, 0)
        self.assertIn('Warning: No plugins found matching', result.stdout)
        self.assertIn('Available modules:', result.stdout)
        self.assertIn('plugin1', result.stdout)

    @patch('sru_lint.cli.PluginManager')
    def test_plugins_command_with_plugins(self, mock_plugin_manager):
        """Test plugins command when plugins are available"""
        mock_pm = MagicMock()
        mock_plugin_manager.return_value = mock_pm
        
        mock_plugin1 = MagicMock()
        mock_plugin1.__class__.__name__ = 'TestPlugin1'
        mock_plugin1.__symbolic_name__ = 'test-plugin1'
        mock_plugin1.__class__.__doc__ = 'Test plugin description'
        mock_plugin2 = MagicMock()
        mock_plugin2.__class__.__name__ = 'TestPlugin2'
        mock_plugin2.__symbolic_name__ = 'test-plugin2'
        mock_plugin2.__class__.__doc__ = None
        
        mock_pm.load_plugins.return_value = [mock_plugin1, mock_plugin2]
        
        result = self.runner.invoke(app, ['plugins'])
        
        self.assertEqual(result.exit_code, 0)
        self.assertIn('Available plugins:', result.stdout)
        # Check for aligned output - both plugin names should be padded to the same width
        # The longer name 'test-plugin2' (12 chars) determines the alignment
        self.assertIn('test-plugin1 : Test plugin description', result.stdout)
        self.assertIn('test-plugin2 : No description available', result.stdout)

    @patch('sru_lint.cli.PluginManager')
    def test_plugins_command_no_plugins(self, mock_plugin_manager):
        """Test plugins command when no plugins are available"""
        mock_pm = MagicMock()
        mock_plugin_manager.return_value = mock_pm
        mock_pm.load_plugins.return_value = []
        
        result = self.runner.invoke(app, ['plugins'])
        
        self.assertEqual(result.exit_code, 0)
        self.assertIn('Available plugins:', result.stdout)
        self.assertIn('No plugins found.', result.stdout)

    def test_inspect_command(self):
        """Test inspect command"""
        result = self.runner.invoke(app, ['inspect'])
        
        self.assertEqual(result.exit_code, 0)
        self.assertIn('Inspecting code...', result.stdout)

    def test_help_command_no_args(self):
        """Test help command without arguments"""
        result = self.runner.invoke(app, ['help'])
        
        self.assertEqual(result.exit_code, 0)
        # Should show the same as --help
        help_result = self.runner.invoke(app, ['--help'])
        self.assertEqual(result.stdout, help_result.stdout)

    def test_help_command_with_valid_command(self):
        """Test help command with valid subcommand"""
        result = self.runner.invoke(app, ['help', 'check'])
        
        self.assertEqual(result.exit_code, 0)
        self.assertIn('check', result.stdout)
        self.assertIn('Run the linter on the specified patch', result.stdout)

    def test_help_command_with_invalid_command(self):
        """Test help command with invalid subcommand"""
        result = self.runner.invoke(app, ['help', 'invalid'])
        
        self.assertEqual(result.exit_code, 2)
        self.assertIn('Unknown command: invalid', result.stderr)

    @patch('sru_lint.cli.unidiff.PatchSet')
    @patch('sru_lint.cli.PluginManager')
    def test_check_multiple_modules_options(self, mock_plugin_manager, mock_patchset):
        """Test check command with multiple --modules options"""
        mock_pm = MagicMock()
        mock_plugin_manager.return_value = mock_pm
        
        mock_plugin1 = MagicMock()
        mock_plugin1.__symbolic_name__ = 'plugin1'
        mock_plugin2 = MagicMock()
        mock_plugin2.__symbolic_name__ = 'plugin2'
        mock_plugin3 = MagicMock()
        mock_plugin3.__symbolic_name__ = 'plugin3'
        mock_pm.load_plugins.return_value = [mock_plugin1, mock_plugin2, mock_plugin3]
        
        mock_patchset_instance = MagicMock()
        mock_patchset.return_value = mock_patchset_instance
        
        with patch('builtins.open', mock_open(read_data='patch content')):
            result = self.runner.invoke(app, ['check', '-', '-m', 'plugin1', '-m', 'plugin2'])
        
        self.assertEqual(result.exit_code, 0)
        mock_plugin1.process.assert_called_once_with(mock_patchset_instance)
        mock_plugin2.process.assert_called_once_with(mock_patchset_instance)
        mock_plugin3.process.assert_not_called()

    @patch('sru_lint.cli.unidiff.PatchSet')
    @patch('sru_lint.cli.PluginManager')
    def test_check_mixed_comma_and_multiple_options(self, mock_plugin_manager, mock_patchset):
        """Test check command mixing comma-separated and multiple options"""
        mock_pm = MagicMock()
        mock_plugin_manager.return_value = mock_pm
        
        mock_plugin1 = MagicMock()
        mock_plugin1.__symbolic_name__ = 'plugin1'
        mock_plugin2 = MagicMock()
        mock_plugin2.__symbolic_name__ = 'plugin2'
        mock_plugin3 = MagicMock()
        mock_plugin3.__symbolic_name__ = 'plugin3'
        mock_pm.load_plugins.return_value = [mock_plugin1, mock_plugin2, mock_plugin3]
        
        mock_patchset_instance = MagicMock()
        mock_patchset.return_value = mock_patchset_instance
        
        with patch('builtins.open', mock_open(read_data='patch content')):
            result = self.runner.invoke(app, ['check', '-', '-m', 'plugin1,plugin2', '-m', 'plugin3'])
        
        self.assertEqual(result.exit_code, 0)
        mock_plugin1.process.assert_called_once_with(mock_patchset_instance)
        mock_plugin2.process.assert_called_once_with(mock_patchset_instance)
        mock_plugin3.process.assert_called_once_with(mock_patchset_instance)


if __name__ == '__main__':
    unittest.main()