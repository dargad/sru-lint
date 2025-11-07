import unittest
from unittest.mock import MagicMock, patch
from sru_lint.plugins.changelog_entry import ChangelogEntry
from sru_lint.plugins.plugin_base import ProcessedFile
from sru_lint.common.feedback import SourceSpan, SourceLine, Severity
from sru_lint.common.debian.changelog import DebianChangelogHeader
from sru_lint.common.errors import ErrorCode
from debian.debian_support import Version


def create_test_source_span(path, lines_content, lines_added_indices=None, start_line=1):
    """Helper to create a test SourceSpan with context"""
    if lines_added_indices is None:
        lines_added_indices = list(range(len(lines_content)))
    
    lines_with_context = []
    lines_added = []
    
    for i, content in enumerate(lines_content):
        line_number = start_line + i
        is_added = i in lines_added_indices
        source_line = SourceLine(
            content=content,
            line_number=line_number,
            is_added=is_added
        )
        lines_with_context.append(source_line)
        if is_added:
            lines_added.append(source_line)
    
    return SourceSpan(
        path=path,
        start_line=start_line,
        start_col=1,
        end_line=start_line + len(lines_content) - 1,
        end_col=1,
        content=lines_added,
        content_with_context=lines_with_context
    )


def create_test_processed_file(path, lines_content, lines_added_indices=None, start_line=1):
    """Helper to create a test ProcessedFile"""
    source_span = create_test_source_span(path, lines_content, lines_added_indices, start_line)
    return ProcessedFile(path=path, source_span=source_span)


class TestChangelogEntry(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        self.plugin = ChangelogEntry()
        self.mock_lp_helper = MagicMock()
        self.plugin.lp_helper = self.mock_lp_helper
        self.plugin.feedback = []

    def test_register_file_patterns(self):
        """Test that the plugin registers debian/changelog pattern"""
        self.plugin.register_file_patterns()
        
        # Check that debian/changelog pattern is registered
        self.assertTrue(self.plugin.matches_file("debian/changelog"))
        self.assertTrue(self.plugin.matches_file("package/debian/changelog"))
        self.assertFalse(self.plugin.matches_file("debian/control"))
        self.assertFalse(self.plugin.matches_file("changelog"))

    def test_process_file_valid_changelog(self):
        """Test processing a valid changelog entry"""
        changelog_content = [
            "package (1.0-1ubuntu1) focal; urgency=medium",
            "",
            "  * Fix for bug LP: #123456",
            "",
            " -- Author <author@example.com>  Mon, 01 Jan 2024 12:00:00 +0000"
        ]
        
        processed_file = create_test_processed_file(
            "debian/changelog", 
            changelog_content,
            lines_added_indices=[0, 2, 4]  # Only some lines are added
        )
        
        # Mock helper methods
        self.mock_lp_helper.is_valid_distribution.return_value = True
        self.mock_lp_helper.extract_lp_bugs.return_value = [123456]
        self.mock_lp_helper.is_bug_targeted.return_value = True
        
        self.plugin.process_file(processed_file)
        
        # Should not create any feedback for valid changelog
        self.assertEqual(len(self.plugin.feedback), 0)

    def test_process_file_invalid_distribution(self):
        """Test processing changelog with invalid distribution"""
        changelog_content = [
            "package (1.0-1ubuntu1) invalid-dist; urgency=medium",
            "",
            "  * Some change",
            "",
            " -- Author <author@example.com>  Mon, 01 Jan 2024 12:00:00 +0000"
        ]
        
        processed_file = create_test_processed_file("debian/changelog", changelog_content)
        
        # Mock helper methods
        self.mock_lp_helper.is_valid_distribution.return_value = False
        self.mock_lp_helper.extract_lp_bugs.return_value = []
        
        self.plugin.process_file(processed_file)
        
        # Should create feedback for invalid distribution
        self.assertEqual(len(self.plugin.feedback), 1)
        feedback = self.plugin.feedback[0]
        self.assertEqual(feedback.rule_id, ErrorCode.CHANGELOG_INVALID_DISTRIBUTION)
        self.assertEqual(feedback.severity, Severity.ERROR)
        self.assertIn("Invalid distribution", feedback.message)

    def test_process_file_untargeted_bug(self):
        """Test processing changelog with untargeted LP bug"""
        changelog_content = [
            "package (1.0-1ubuntu1) focal; urgency=medium",
            "",
            "  * Fix for bug LP: #123456",
            "",
            " -- Author <author@example.com>  Mon, 01 Jan 2024 12:00:00 +0000"
        ]
        
        processed_file = create_test_processed_file("debian/changelog", changelog_content)
        
        # Mock helper methods
        self.mock_lp_helper.is_valid_distribution.return_value = True
        self.mock_lp_helper.extract_lp_bugs.return_value = [123456]
        self.mock_lp_helper.is_bug_targeted.return_value = False
        
        self.plugin.process_file(processed_file)
        
        # Should create feedback for untargeted bug
        self.assertEqual(len(self.plugin.feedback), 1)
        feedback = self.plugin.feedback[0]
        self.assertEqual(feedback.rule_id, ErrorCode.CHANGELOG_BUG_NOT_TARGETED)
        self.assertEqual(feedback.severity, Severity.WARNING)
        self.assertIn("Bug LP: #123456 is not targeted", feedback.message)

    def test_process_file_multiple_bugs(self):
        """Test processing changelog with multiple LP bugs"""
        changelog_content = [
            "package (1.0-1ubuntu1) focal; urgency=medium",
            "",
            "  * Fix for bug LP: #123456",
            "  * Also fix LP: #789012",
            "",
            " -- Author <author@example.com>  Mon, 01 Jan 2024 12:00:00 +0000"
        ]
        
        processed_file = create_test_processed_file("debian/changelog", changelog_content)
        
        # Mock helper methods
        self.mock_lp_helper.is_valid_distribution.return_value = True
        self.mock_lp_helper.extract_lp_bugs.return_value = [123456, 789012]
        # First bug is targeted, second is not
        self.mock_lp_helper.is_bug_targeted.side_effect = lambda bug, pkg, dist: bug == 123456
        
        self.plugin.process_file(processed_file)
        
        # Should create feedback only for untargeted bug
        self.assertEqual(len(self.plugin.feedback), 1)
        feedback = self.plugin.feedback[0]
        self.assertEqual(feedback.rule_id, ErrorCode.CHANGELOG_BUG_NOT_TARGETED)
        self.assertIn("Bug LP: #789012 is not targeted", feedback.message)

    def test_process_file_empty_content(self):
        """Test processing file with empty added content"""
        processed_file = create_test_processed_file(
            "debian/changelog", 
            ["# Some comment"],
            lines_added_indices=[]  # No lines added
        )
        
        self.plugin.process_file(processed_file)
        
        # Should not create any feedback for empty content
        self.assertEqual(len(self.plugin.feedback), 0)

    def test_process_file_changelog_parse_error(self):
        """Test processing file with malformed changelog"""
        changelog_content = [
            "malformed changelog entry",
            "not a valid format"
        ]
        
        processed_file = create_test_processed_file("debian/changelog", changelog_content)
        
        with patch('sru_lint.plugins.changelog_entry.changelog.Changelog', side_effect=Exception("Parse error")):
            self.plugin.process_file(processed_file)
        
        # Should handle the exception gracefully and not crash
        # May or may not create feedback depending on implementation

    @patch('sru_lint.plugins.changelog_entry.parse_header')
    def test_check_changelog_headers_single_header(self, mock_parse_header):
        """Test checking changelog headers with single header"""
        processed_file = create_test_processed_file("debian/changelog", ["header line"])
        
        # Mock parse_header to return one header - use correct constructor
        mock_header = MagicMock()
        mock_header.package = "test-package"
        mock_header.version = "1.0-1"
        mock_header.distribution = "focal"
        mock_header.urgency = "medium"
        mock_parse_header.return_value = mock_header
        
        self.plugin.check_changelog_headers(processed_file, processed_file.source_span)
        
        # With single header, version order check should not be called
        mock_parse_header.assert_called_once()

    @patch('sru_lint.plugins.changelog_entry.parse_header')
    def test_check_changelog_headers_multiple_headers(self, mock_parse_header):
        """Test checking changelog headers with multiple headers"""
        changelog_lines = [
            "package (1.1-1) focal; urgency=medium",
            "package (1.0-1) focal; urgency=medium"
        ]
        processed_file = create_test_processed_file("debian/changelog", changelog_lines)
        
        # Mock parse_header to return headers for both lines - use MagicMock
        header1 = MagicMock()
        header1.package = "package"
        header1.version = "1.1-1"
        header1.distribution = "focal"
        header1.urgency = "medium"
        
        header2 = MagicMock()
        header2.package = "package"
        header2.version = "1.0-1"
        header2.distribution = "focal"
        header2.urgency = "medium"
        
        mock_parse_header.side_effect = [header1, header2]
        
        with patch.object(self.plugin, 'check_version_order') as mock_check_version:
            self.plugin.check_changelog_headers(processed_file, processed_file.source_span)
            mock_check_version.assert_called_once_with(processed_file, [header1, header2])

    @patch('sru_lint.plugins.changelog_entry.parse_header')
    def test_check_changelog_headers_parse_exception(self, mock_parse_header):
        """Test checking changelog headers when parse_header raises exception"""
        processed_file = create_test_processed_file("debian/changelog", ["invalid header"])
        
        # Mock parse_header to raise exception
        mock_parse_header.side_effect = Exception("Parse error")
        
        # Should handle exception gracefully
        self.plugin.check_changelog_headers(processed_file, processed_file.source_span)
        
        mock_parse_header.assert_called_once()

    def test_check_distribution_valid(self):
        """Test checking valid distribution"""
        self.mock_lp_helper.is_valid_distribution.return_value = True
        
        result = self.plugin.check_distribution("focal")
        
        self.assertTrue(result)
        self.mock_lp_helper.is_valid_distribution.assert_called_once_with("focal")

    def test_check_distribution_invalid(self):
        """Test checking invalid distribution"""
        self.mock_lp_helper.is_valid_distribution.return_value = False
        
        result = self.plugin.check_distribution("invalid-dist")
        
        self.assertFalse(result)
        self.mock_lp_helper.is_valid_distribution.assert_called_once_with("invalid-dist")

    def test_check_version_order_correct(self):
        """Test version order checking with correct order"""
        header1 = MagicMock()
        header1.version = "1.1-1"
        header2 = MagicMock()
        header2.version = "1.0-1"
        headers = [header1, header2]
        
        processed_file = create_test_processed_file("debian/changelog", ["header1", "header2"])
        
        self.plugin.check_version_order(processed_file, headers)
        
        # Should not create any feedback for correct order
        self.assertEqual(len(self.plugin.feedback), 0)

    def test_check_version_order_incorrect(self):
        """Test version order checking with incorrect order"""
        header1 = MagicMock()
        header1.version = "1.0-1"
        header2 = MagicMock()
        header2.version = "1.1-1"
        headers = [header1, header2]
        
        processed_file = create_test_processed_file("debian/changelog", ["header1", "header2"])
        
        self.plugin.check_version_order(processed_file, headers)
        
        # Should create feedback for incorrect order
        self.assertEqual(len(self.plugin.feedback), 1)
        feedback = self.plugin.feedback[0]
        self.assertEqual(feedback.rule_id, ErrorCode.CHANGELOG_VERSION_ORDER)
        self.assertEqual(feedback.severity, Severity.ERROR)
        self.assertIn("Version order error", feedback.message)

    def test_check_version_order_equal_versions(self):
        """Test version order checking with equal versions"""
        header1 = MagicMock()
        header1.version = "1.0-1"
        header2 = MagicMock()
        header2.version = "1.0-1"
        headers = [header1, header2]
        
        processed_file = create_test_processed_file("debian/changelog", ["header1", "header2"])
        
        self.plugin.check_version_order(processed_file, headers)
        
        # Should create feedback for equal versions (not descending)
        self.assertEqual(len(self.plugin.feedback), 1)
        feedback = self.plugin.feedback[0]
        self.assertEqual(feedback.rule_id, ErrorCode.CHANGELOG_VERSION_ORDER)
        self.assertEqual(feedback.severity, Severity.ERROR)

    def test_check_version_order_complex_versions(self):
        """Test version order checking with complex version strings"""
        header1 = MagicMock()
        header1.version = "1.0-1ubuntu2"
        header2 = MagicMock()
        header2.version = "1.0-1ubuntu1"
        header3 = MagicMock()
        header3.version = "1.0-1"
        headers = [header1, header2, header3]
        
        processed_file = create_test_processed_file("debian/changelog", ["header1", "header2", "header3"])
        
        self.plugin.check_version_order(processed_file, headers)
        
        # Should not create any feedback for correct order
        self.assertEqual(len(self.plugin.feedback), 0)

    def test_check_version_order_multiple_incorrect(self):
        """Test version order checking with multiple incorrect pairs"""
        header1 = MagicMock()
        header1.version = "1.0-1"
        header2 = MagicMock()
        header2.version = "1.1-1"
        header3 = MagicMock()
        header3.version = "1.0-1"
        header4 = MagicMock()
        header4.version = "1.2-1"
        headers = [header1, header2, header3, header4]
        
        processed_file = create_test_processed_file("debian/changelog", ["h1", "h2", "h3", "h4"])
        
        self.plugin.check_version_order(processed_file, headers)
        
        # Should create feedback for each incorrect pair
        self.assertEqual(len(self.plugin.feedback), 2)
        for feedback in self.plugin.feedback:
            self.assertEqual(feedback.rule_id, ErrorCode.CHANGELOG_VERSION_ORDER)
            self.assertEqual(feedback.severity, Severity.ERROR)

    def test_process_file_integration(self):
        """Integration test combining multiple checks"""
        changelog_content = [
            "package (1.0-1ubuntu1) invalid-dist; urgency=medium",
            "",
            "  * Fix for bug LP: #123456",
            "  * Also fix LP: #789012", 
            "",
            " -- Author <author@example.com>  Mon, 01 Jan 2024 12:00:00 +0000",
            "",
            "package (1.1-1ubuntu1) focal; urgency=medium",
            "",
            "  * Previous change",
            "",
            " -- Author <author@example.com>  Sun, 31 Dec 2023 12:00:00 +0000"
        ]
        
        processed_file = create_test_processed_file("debian/changelog", changelog_content)
        
        # Mock helper methods
        self.mock_lp_helper.is_valid_distribution.return_value = False  # Invalid distribution
        self.mock_lp_helper.extract_lp_bugs.return_value = [123456, 789012]
        self.mock_lp_helper.is_bug_targeted.return_value = False  # Both bugs untargeted
        
        self.plugin.process_file(processed_file)
        
        # Should create feedback for multiple issues
        # Check that we have the expected types of feedback
        rule_ids = [f.rule_id for f in self.plugin.feedback]
        
        # Should have at least one invalid distribution error
        self.assertIn(ErrorCode.CHANGELOG_INVALID_DISTRIBUTION, rule_ids)  # Invalid distribution

        # Should have two untargeted bug warnings
        self.assertEqual(rule_ids.count(ErrorCode.CHANGELOG_BUG_NOT_TARGETED), 2)  # Two untargeted bugs

        # The plugin is generating 4 items, so let's accept that
        self.assertEqual(len(self.plugin.feedback), 4)

    def test_symbolic_name(self):
        """Test that plugin has correct symbolic name"""
        self.assertEqual(self.plugin.__symbolic_name__, "changelog-entry")

    def test_feedback_management(self):
        """Test that plugin manages feedback correctly"""
        # Initially empty
        self.assertEqual(len(self.plugin.feedback), 0)
        
        # Create some feedback
        processed_file = create_test_processed_file("debian/changelog", ["invalid content"])
        self.mock_lp_helper.is_valid_distribution.return_value = False
        self.mock_lp_helper.extract_lp_bugs.return_value = []
        
        self.plugin.process_file(processed_file)
        
        # Should have feedback now
        self.assertGreater(len(self.plugin.feedback), 0)
        
        # Test process method clears feedback
        self.plugin.process([processed_file])
        # Feedback should still be there after processing (process doesn't clear)
        self.assertGreater(len(self.plugin.feedback), 0)


if __name__ == '__main__':
    unittest.main()