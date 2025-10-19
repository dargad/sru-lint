import unittest
from unittest.mock import patch, MagicMock, mock_open
from io import StringIO
import typer
from typer.testing import CliRunner
from sru_lint.cli import app
from sru_lint.common.feedback import FeedbackItem, Severity, SourceSpan
from sru_lint.plugins.plugin_base import ProcessedFile


class TestCLI(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    @patch('sru_lint.cli.process_patch_content')
    @patch('sru_lint.cli.PluginManager')
    def test_check_command_default_modules(self, mock_plugin_manager, mock_process_patch):
        """Test check command with default 'all' modules"""
        mock_pm = MagicMock()
        mock_plugin_manager.return_value = mock_pm
        
        mock_plugin1 = MagicMock()
        mock_plugin1.__symbolic_name__ = 'plugin1'
        mock_plugin1.process.return_value = []
        mock_plugin2 = MagicMock()
        mock_plugin2.__symbolic_name__ = 'plugin2'
        mock_plugin2.process.return_value = []
        mock_pm.load_plugins.return_value = [mock_plugin1, mock_plugin2]
        
        # Mock processed files
        mock_processed_files = [
            ProcessedFile(path="test.py", source_span=MagicMock()),
            ProcessedFile(path="test2.py", source_span=MagicMock())
        ]
        mock_process_patch.return_value = mock_processed_files
        
        # Create a mock file with patch content
        with patch('builtins.open', mock_open(read_data='patch content')):
            result = self.runner.invoke(app, ['check', '-'])
        
        self.assertEqual(result.exit_code, 0)
        mock_process_patch.assert_called_once_with('patch content')
        mock_plugin1.process.assert_called_once_with(mock_processed_files)
        mock_plugin2.process.assert_called_once_with(mock_processed_files)

    @patch('sru_lint.cli.process_patch_content')
    @patch('sru_lint.cli.PluginManager')
    def test_check_command_specific_modules(self, mock_plugin_manager, mock_process_patch):
        """Test check command with specific modules"""
        mock_pm = MagicMock()
        mock_plugin_manager.return_value = mock_pm
        
        mock_plugin1 = MagicMock()
        mock_plugin1.__symbolic_name__ = 'plugin1'
        mock_plugin1.process.return_value = []
        mock_plugin2 = MagicMock()
        mock_plugin2.__symbolic_name__ = 'plugin2'
        mock_plugin2.process.return_value = []
        mock_pm.load_plugins.return_value = [mock_plugin1, mock_plugin2]
        
        mock_processed_files = [ProcessedFile(path="test.py", source_span=MagicMock())]
        mock_process_patch.return_value = mock_processed_files
        
        with patch('builtins.open', mock_open(read_data='patch content')):
            result = self.runner.invoke(app, ['check', '-', '--modules', 'plugin1'])
        
        self.assertEqual(result.exit_code, 0)
        mock_plugin1.process.assert_called_once_with(mock_processed_files)
        mock_plugin2.process.assert_not_called()

    @patch('sru_lint.cli.process_patch_content')
    @patch('sru_lint.cli.PluginManager')
    def test_check_command_comma_separated_modules(self, mock_plugin_manager, mock_process_patch):
        """Test check command with comma-separated modules"""
        mock_pm = MagicMock()
        mock_plugin_manager.return_value = mock_pm
        
        mock_plugin1 = MagicMock()
        mock_plugin1.__symbolic_name__ = 'plugin1'
        mock_plugin1.process.return_value = []
        mock_plugin2 = MagicMock()
        mock_plugin2.__symbolic_name__ = 'plugin2'
        mock_plugin2.process.return_value = []
        mock_plugin3 = MagicMock()
        mock_plugin3.__symbolic_name__ = 'plugin3'
        mock_plugin3.process.return_value = []
        mock_pm.load_plugins.return_value = [mock_plugin1, mock_plugin2, mock_plugin3]
        
        mock_processed_files = [ProcessedFile(path="test.py", source_span=MagicMock())]
        mock_process_patch.return_value = mock_processed_files
        
        with patch('builtins.open', mock_open(read_data='patch content')):
            result = self.runner.invoke(app, ['check', '-', '--modules', 'plugin1,plugin2'])
        
        self.assertEqual(result.exit_code, 0)
        mock_plugin1.process.assert_called_once_with(mock_processed_files)
        mock_plugin2.process.assert_called_once_with(mock_processed_files)
        mock_plugin3.process.assert_not_called()

    @patch('sru_lint.cli.process_patch_content')
    @patch('sru_lint.cli.PluginManager')
    def test_check_command_nonexistent_modules(self, mock_plugin_manager, mock_process_patch):
        """Test check command with nonexistent modules"""
        mock_pm = MagicMock()
        mock_plugin_manager.return_value = mock_pm
        
        mock_plugin1 = MagicMock()
        mock_plugin1.__symbolic_name__ = 'plugin1'
        mock_pm.load_plugins.return_value = [mock_plugin1]
        
        mock_processed_files = [ProcessedFile(path="test.py", source_span=MagicMock())]
        mock_process_patch.return_value = mock_processed_files
        
        with patch('builtins.open', mock_open(read_data='patch content')):
            result = self.runner.invoke(app, ['check', '-', '--modules', 'nonexistent'])
        
        self.assertEqual(result.exit_code, 0)
        self.assertIn('Available modules:', result.stdout)
        self.assertIn('plugin1', result.stdout)

    @patch('sru_lint.cli.process_patch_content')
    @patch('sru_lint.cli.PluginManager')
    def test_check_command_with_errors(self, mock_plugin_manager, mock_process_patch):
        """Test check command with plugins that return errors"""
        mock_pm = MagicMock()
        mock_plugin_manager.return_value = mock_pm
        
        # Create a mock feedback item with error severity
        error_feedback = FeedbackItem(
            message="Test error",
            span=SourceSpan(path="test.py", start_line=1, start_col=1, end_line=1, end_col=1),
            rule_id="TEST001",
            severity=Severity.ERROR
        )
        
        mock_plugin1 = MagicMock()
        mock_plugin1.__symbolic_name__ = 'plugin1'
        mock_plugin1.process.return_value = [error_feedback]
        mock_pm.load_plugins.return_value = [mock_plugin1]
        
        mock_processed_files = [ProcessedFile(path="test.py", source_span=MagicMock())]
        mock_process_patch.return_value = mock_processed_files
        
        with patch('builtins.open', mock_open(read_data='patch content')):
            result = self.runner.invoke(app, ['check', '-'])
        
        self.assertEqual(result.exit_code, 1)  # Should exit with error code due to errors
        self.assertIn('Test error', result.stdout)

    @patch('sru_lint.cli.process_patch_content')
    @patch('sru_lint.cli.PluginManager')
    def test_check_command_with_warnings_only(self, mock_plugin_manager, mock_process_patch):
        """Test check command with plugins that return only warnings"""
        mock_pm = MagicMock()
        mock_plugin_manager.return_value = mock_pm
        
        # Create a mock feedback item with warning severity
        warning_feedback = FeedbackItem(
            message="Test warning",
            span=SourceSpan(path="test.py", start_line=1, start_col=1, end_line=1, end_col=1),
            rule_id="TEST002",
            severity=Severity.WARNING
        )
        
        mock_plugin1 = MagicMock()
        mock_plugin1.__symbolic_name__ = 'plugin1'
        mock_plugin1.process.return_value = [warning_feedback]
        mock_pm.load_plugins.return_value = [mock_plugin1]
        
        mock_processed_files = [ProcessedFile(path="test.py", source_span=MagicMock())]
        mock_process_patch.return_value = mock_processed_files
        
        with patch('builtins.open', mock_open(read_data='patch content')):
            result = self.runner.invoke(app, ['check', '-'])
        
        self.assertEqual(result.exit_code, 0)  # Should exit successfully (warnings don't cause exit code 1)
        self.assertIn('Test warning', result.stdout)

    @patch('sru_lint.cli.process_patch_content')
    @patch('sru_lint.cli.PluginManager')
    def test_check_command_no_files_in_patch(self, mock_plugin_manager, mock_process_patch):
        """Test check command when patch contains no files"""
        mock_pm = MagicMock()
        mock_plugin_manager.return_value = mock_pm
        mock_pm.load_plugins.return_value = []
        
        # Mock empty processed files
        mock_process_patch.return_value = []
        
        with patch('builtins.open', mock_open(read_data='empty patch')):
            result = self.runner.invoke(app, ['check', '-'])
        
        self.assertEqual(result.exit_code, 2)  # Should exit with error code for no files

    @patch('sru_lint.cli.process_patch_content')
    @patch('sru_lint.cli.PluginManager')
    def test_check_command_patch_parse_failure(self, mock_plugin_manager, mock_process_patch):
        """Test check command when patch parsing fails"""
        mock_pm = MagicMock()
        mock_plugin_manager.return_value = mock_pm
        mock_pm.load_plugins.return_value = []
        
        # Mock patch processing failure
        mock_process_patch.return_value = []
        
        with patch('builtins.open', mock_open(read_data='invalid patch')):
            result = self.runner.invoke(app, ['check', '-'])
        
        self.assertEqual(result.exit_code, 2)

    @patch('sru_lint.cli.PluginManager')
    def test_plugins_command_with_plugins(self, mock_plugin_manager):
        """Test plugins command when plugins are available"""
        mock_pm = MagicMock()
        mock_plugin_manager.return_value = mock_pm
        
        mock_plugin1 = MagicMock()
        mock_plugin1.__class__.__name__ = 'TestPlugin1'
        mock_plugin1.__symbolic_name__ = 'test-plugin1'
        mock_plugin1.__class__.__doc__ = 'Test plugin description'
        mock_plugin1.__class__.__module__ = 'test.module1'
        mock_plugin2 = MagicMock()
        mock_plugin2.__class__.__name__ = 'TestPlugin2'
        mock_plugin2.__symbolic_name__ = 'test-plugin2'
        mock_plugin2.__class__.__doc__ = None
        mock_plugin2.__class__.__module__ = 'test.module2'
        
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

    @patch('sru_lint.cli.process_patch_content')
    @patch('sru_lint.cli.PluginManager')
    def test_check_multiple_modules_options(self, mock_plugin_manager, mock_process_patch):
        """Test check command with multiple --modules options"""
        mock_pm = MagicMock()
        mock_plugin_manager.return_value = mock_pm
        
        mock_plugin1 = MagicMock()
        mock_plugin1.__symbolic_name__ = 'plugin1'
        mock_plugin1.process.return_value = []
        mock_plugin2 = MagicMock()
        mock_plugin2.__symbolic_name__ = 'plugin2'
        mock_plugin2.process.return_value = []
        mock_plugin3 = MagicMock()
        mock_plugin3.__symbolic_name__ = 'plugin3'
        mock_plugin3.process.return_value = []
        mock_pm.load_plugins.return_value = [mock_plugin1, mock_plugin2, mock_plugin3]
        
        mock_processed_files = [ProcessedFile(path="test.py", source_span=MagicMock())]
        mock_process_patch.return_value = mock_processed_files
        
        with patch('builtins.open', mock_open(read_data='patch content')):
            result = self.runner.invoke(app, ['check', '-', '-m', 'plugin1', '-m', 'plugin2'])
        
        self.assertEqual(result.exit_code, 0)
        mock_plugin1.process.assert_called_once_with(mock_processed_files)
        mock_plugin2.process.assert_called_once_with(mock_processed_files)
        mock_plugin3.process.assert_not_called()

    @patch('sru_lint.cli.process_patch_content')
    @patch('sru_lint.cli.PluginManager')
    def test_check_mixed_comma_and_multiple_options(self, mock_plugin_manager, mock_process_patch):
        """Test check command mixing comma-separated and multiple options"""
        mock_pm = MagicMock()
        mock_plugin_manager.return_value = mock_pm
        
        mock_plugin1 = MagicMock()
        mock_plugin1.__symbolic_name__ = 'plugin1'
        mock_plugin1.process.return_value = []
        mock_plugin2 = MagicMock()
        mock_plugin2.__symbolic_name__ = 'plugin2'
        mock_plugin2.process.return_value = []
        mock_plugin3 = MagicMock()
        mock_plugin3.__symbolic_name__ = 'plugin3'
        mock_plugin3.process.return_value = []
        mock_pm.load_plugins.return_value = [mock_plugin1, mock_plugin2, mock_plugin3]
        
        mock_processed_files = [ProcessedFile(path="test.py", source_span=MagicMock())]
        mock_process_patch.return_value = mock_processed_files
        
        with patch('builtins.open', mock_open(read_data='patch content')):
            result = self.runner.invoke(app, ['check', '-', '-m', 'plugin1,plugin2', '-m', 'plugin3'])
        
        self.assertEqual(result.exit_code, 0)
        mock_plugin1.process.assert_called_once_with(mock_processed_files)
        mock_plugin2.process.assert_called_once_with(mock_processed_files)
        mock_plugin3.process.assert_called_once_with(mock_processed_files)

    def test_verbose_flag(self):
        """Test verbose flag functionality"""
        with patch('sru_lint.cli.setup_logger') as mock_setup_logger:
            result = self.runner.invoke(app, ['-v', 'plugins'])
            # Check that logging was configured with INFO level
            mock_setup_logger.assert_called()

    def test_quiet_flag(self):
        """Test quiet flag functionality"""
        with patch('sru_lint.cli.setup_logger') as mock_setup_logger:
            result = self.runner.invoke(app, ['-q', 'plugins'])
            # Check that logging was configured
            mock_setup_logger.assert_called()

    @patch('sru_lint.cli.process_patch_content')
    @patch('sru_lint.cli.PluginManager')
    def test_quiet_suppresses_success_message(self, mock_plugin_manager, mock_process_patch):
        """Test that quiet mode suppresses success message"""
        mock_pm = MagicMock()
        mock_plugin_manager.return_value = mock_pm
        
        mock_plugin1 = MagicMock()
        mock_plugin1.__symbolic_name__ = 'plugin1'
        mock_plugin1.process.return_value = []  # No feedback
        mock_pm.load_plugins.return_value = [mock_plugin1]
        
        mock_processed_files = [ProcessedFile(path="test.py", source_span=MagicMock())]
        mock_process_patch.return_value = mock_processed_files
        
        with patch('builtins.open', mock_open(read_data='patch content')):
            result = self.runner.invoke(app, ['-q', 'check', '-'])
        
        self.assertEqual(result.exit_code, 0)
        # In quiet mode, success message should not appear
        self.assertNotIn('No issues found', result.stdout)


if __name__ == '__main__':
    unittest.main()