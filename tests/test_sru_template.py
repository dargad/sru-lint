import unittest
from unittest.mock import MagicMock, patch
from sru_lint.plugins.sru_template import SRUTemplate
from sru_lint.plugins.plugin_base import ProcessedFile
from sru_lint.common.feedback import SourceSpan, SourceLine, Severity
from sru_lint.common.errors import ErrorCode


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


class TestSRUTemplate(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        self.plugin = SRUTemplate()
        self.plugin.feedback = []
        
        # Mock Launchpad helper
        self.mock_lp_helper = MagicMock()
        self.plugin.lp_helper = self.mock_lp_helper

    def test_register_file_patterns(self):
        """Test that the plugin registers debian/changelog pattern"""
        self.plugin.register_file_patterns()
        
        # Check that debian/changelog pattern is registered
        self.assertTrue(self.plugin.matches_file("debian/changelog"))
        self.assertTrue(self.plugin.matches_file("package/debian/changelog"))
        self.assertFalse(self.plugin.matches_file("debian/control"))
        self.assertFalse(self.plugin.matches_file("changelog"))

    def test_process_file_empty_content(self):
        """Test processing file with no added lines"""
        processed_file = create_test_processed_file(
            "debian/changelog", 
            ["# Some existing content"],
            lines_added_indices=[]  # No lines added
        )
        
        self.plugin.process_file(processed_file)

        # Should create info feedback about no bugs referenced        
        self.assertEqual(len(self.plugin.feedback), 1)
        feedback = self.plugin.feedback[0]
        self.assertEqual(feedback.rule_id, ErrorCode.SRU_NO_BUGS_REFERENCED)
        self.assertEqual(feedback.severity, Severity.INFO)
        self.assertIn("No Launchpad bugs referenced in", feedback.message)

    @patch('sru_lint.common.launchpad_helper.LaunchpadHelper.extract_lp_bugs')
    def test_process_file_sru_with_valid_template(self, mock_extract_bugs):
        """Test processing SRU changelog with bug that has valid SRU template"""
        changelog_content = [
            "package (1.0-1ubuntu1~22.04.1) jammy; urgency=medium",
            "",
            "  * Fix critical security issue (LP: #1234567)",
            "",
            " -- Author <author@example.com>  Mon, 01 Jan 2024 12:00:00 +0000"
        ]
        
        processed_file = create_test_processed_file("debian/changelog", changelog_content)
        
        # Mock bug extraction
        mock_extract_bugs.return_value = [1234567]
        
        # Mock Launchpad helper - bug has SRU template
        self.mock_lp_helper.has_sru_template.return_value = True
        
        self.plugin.process_file(processed_file)
        
        # Should not create any feedback for valid SRU template
        self.assertEqual(len(self.plugin.feedback), 0)
        self.mock_lp_helper.has_sru_template.assert_called_once_with(1234567)

    @patch('sru_lint.common.launchpad_helper.LaunchpadHelper.extract_lp_bugs')
    def test_process_file_sru_missing_template(self, mock_extract_bugs):
        """Test processing SRU changelog with bug that lacks SRU template"""
        changelog_content = [
            "package (1.0-1ubuntu1~22.04.1) jammy; urgency=medium",
            "",
            "  * Fix critical security issue (LP: #1234567)",
            "",
            " -- Author <author@example.com>  Mon, 01 Jan 2024 12:00:00 +0000"
        ]
        
        processed_file = create_test_processed_file("debian/changelog", changelog_content)
        
        # Mock bug extraction
        mock_extract_bugs.return_value = [1234567]
        
        # Mock Launchpad helper - bug lacks SRU template
        self.mock_lp_helper.has_sru_template.return_value = False
        
        self.plugin.process_file(processed_file)
        
        # Should create feedback for missing SRU template
        self.assertEqual(len(self.plugin.feedback), 1)
        feedback = self.plugin.feedback[0]
        self.assertEqual(feedback.rule_id, ErrorCode.SRU_TEMPLATE_MISSING)
        self.assertEqual(feedback.severity, Severity.ERROR)
        self.assertIn("SRU template not found for bug LP: ", feedback.message)

    @patch('sru_lint.common.launchpad_helper.LaunchpadHelper.extract_lp_bugs')
    def test_process_file_sru_multiple_bugs(self, mock_extract_bugs):
        """Test processing SRU changelog with multiple bugs"""
        changelog_content = [
            "package (1.0-1ubuntu1~22.04.1) jammy; urgency=medium",
            "",
            "  * Fix security issue (LP: #1234567)",
            "  * Fix another bug (LP: #7654321)",
            "",
            " -- Author <author@example.com>  Mon, 01 Jan 2024 12:00:00 +0000"
        ]
        
        processed_file = create_test_processed_file("debian/changelog", changelog_content)
        
        # Mock bug extraction
        mock_extract_bugs.return_value = [1234567, 7654321]
        
        # Mock Launchpad helper - first bug has template, second doesn't
        def mock_has_template(bug_no):
            return bug_no == 1234567
        
        self.mock_lp_helper.has_sru_template.side_effect = mock_has_template
        
        self.plugin.process_file(processed_file)
        
        # Should create feedback for the bug missing SRU template
        self.assertEqual(len(self.plugin.feedback), 1)
        feedback = self.plugin.feedback[0]
        self.assertEqual(feedback.rule_id, ErrorCode.SRU_TEMPLATE_MISSING)
        self.assertIn("SRU template not found for bug LP: #7654321", feedback.message)
        
        # Should have checked both bugs
        self.assertEqual(self.mock_lp_helper.has_sru_template.call_count, 2)

    @patch('sru_lint.common.launchpad_helper.LaunchpadHelper.extract_lp_bugs')
    def test_process_file_no_bugs_referenced(self, mock_extract_bugs):
        """Test processing SRU changelog with no LP bugs referenced"""
        changelog_content = [
            "package (1.0-1ubuntu1~22.04.1) jammy; urgency=medium",
            "",
            "  * Fix without bug reference",
            "",
            " -- Author <author@example.com>  Mon, 01 Jan 2024 12:00:00 +0000"
        ]
        
        processed_file = create_test_processed_file("debian/changelog", changelog_content)
        
        # Mock bug extraction - no bugs found
        mock_extract_bugs.return_value = []
        
        self.plugin.process_file(processed_file)
        
        # Should create feedback for missing bug reference in SRU
        self.assertEqual(len(self.plugin.feedback), 1)
        feedback = self.plugin.feedback[0]
        self.assertEqual(feedback.rule_id, ErrorCode.SRU_NO_BUGS_REFERENCED)
        self.assertEqual(feedback.severity, Severity.INFO)
        self.assertIn("No Launchpad bugs referenced in", feedback.message)

    @patch('sru_lint.common.launchpad_helper.LaunchpadHelper.extract_lp_bugs')
    def test_process_file_launchpad_api_error(self, mock_extract_bugs):
        """Test handling of Launchpad API errors"""
        changelog_content = [
            "package (1.0-1ubuntu1~22.04.1) jammy; urgency=medium",
            "",
            "  * Fix critical security issue (LP: #1234567)",
            "",
            " -- Author <author@example.com>  Mon, 01 Jan 2024 12:00:00 +0000"
        ]
        
        processed_file = create_test_processed_file("debian/changelog", changelog_content)
        
        # Mock bug extraction
        mock_extract_bugs.return_value = [1234567]
        
        # Mock Launchpad API error
        self.mock_lp_helper.has_sru_template.side_effect = Exception("API Error")
        
        self.plugin.process_file(processed_file)
        
        # Should create feedback for API error
        self.assertEqual(len(self.plugin.feedback), 1)
        feedback = self.plugin.feedback[0]
        self.assertEqual(feedback.rule_id, ErrorCode.SRU_LP_API_ERROR)
        self.assertEqual(feedback.severity, Severity.WARNING)
        self.assertIn("Error checking SRU template for bug LP: #1234567", feedback.message)
        self.assertIn("API Error", feedback.message)

    def test_symbolic_name(self):
        """Test that plugin has correct symbolic name"""
        self.assertEqual(self.plugin.__symbolic_name__, "sru-template")

    @patch('sru_lint.common.launchpad_helper.LaunchpadHelper.extract_lp_bugs')
    def test_mixed_sru_and_regular_entries(self, mock_extract_bugs):
        """Test processing changelog with both SRU and regular entries"""
        changelog_content = [
            "package (1.0-1ubuntu1~22.04.1) jammy; urgency=medium",
            "",
            "  * SRU fix (LP: #1234567)",
            "",
            " -- Author <author@example.com>  Mon, 01 Jan 2024 12:00:00 +0000",
            "",
            "package (1.0-1ubuntu1) jammy; urgency=medium",
            "",
            "  * Regular fix (LP: #7654321)",
            "",
            " -- Author <author@example.com>  Sun, 31 Dec 2023 12:00:00 +0000"
        ]
        
        processed_file = create_test_processed_file("debian/changelog", changelog_content)
        
        # Mock bug extraction - should find both bugs in the text
        mock_extract_bugs.return_value = [1234567, 7654321]
        
        # Mock Launchpad helper - SRU bug has template
        self.mock_lp_helper.has_sru_template.return_value = True
        
        self.plugin.process_file(processed_file)
        
        # Should not create any feedback - plugin should only check bugs in SRU versions
        # The plugin logic should filter to only check bugs associated with SRU versions
        self.assertEqual(len(self.plugin.feedback), 0)


if __name__ == '__main__':
    unittest.main()