import unittest
from unittest.mock import MagicMock, patch
from sru_lint.plugins.patch_format import PatchFormat
from sru_lint.plugins.plugin_base import ProcessedFile
from sru_lint.common.feedback import SourceSpan, SourceLine, Severity, FeedbackItem
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


class TestPatchFormat(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        self.plugin = PatchFormat()
        self.plugin.feedback = []

    def test_register_file_patterns(self):
        """Test that the plugin registers debian/patches/* pattern"""
        self.plugin.register_file_patterns()
        
        # Check that debian/patches/* pattern is registered
        self.assertTrue(self.plugin.matches_file("debian/patches/fix-something.patch"))
        self.assertTrue(self.plugin.matches_file("package/debian/patches/upstream-fix.patch"))
        self.assertFalse(self.plugin.matches_file("debian/control"))
        self.assertFalse(self.plugin.matches_file("patches/fix.patch"))  # Not in debian/patches

    def test_process_file_skips_series_file(self):
        """Test that series file is skipped"""
        series_content = [
            "fix-bug.patch",
            "upstream-fix.patch",
            "# This is a comment"
        ]
        
        processed_file = create_test_processed_file("debian/patches/series", series_content)
        
        self.plugin.process_file(processed_file)
        
        # Should not create any feedback for series file
        self.assertEqual(len(self.plugin.feedback), 0)

    def test_process_file_empty_content(self):
        """Test processing file with no added lines"""
        processed_file = create_test_processed_file(
            "debian/patches/fix.patch", 
            ["# Some existing content"],
            lines_added_indices=[]  # No lines added
        )
        
        self.plugin.process_file(processed_file)
        
        # Should not create any feedback for empty content
        self.assertEqual(len(self.plugin.feedback), 0)

    @patch('sru_lint.plugins.patch_format.check_dep3_compliance')
    def test_process_file_compliant_patch(self, mock_check_dep3):
        """Test processing a DEP-3 compliant patch"""
        patch_content = [
            "Description: Fix widget frobnication",
            "Author: John Doe <john@example.com>",
            "Last-Update: 2024-01-15",
            "---",
            "--- a/file.c",
            "+++ b/file.c",
            "@@ -1,3 +1,3 @@",
            "-old line",
            "+new line"
        ]
        
        processed_file = create_test_processed_file("debian/patches/fix.patch", patch_content)
        
        # Mock compliant result
        mock_check_dep3.return_value = (True, [])
        
        self.plugin.process_file(processed_file)
        
        # Should not create any feedback for compliant patch
        self.assertEqual(len(self.plugin.feedback), 0)
        mock_check_dep3.assert_called_once()

    @patch('sru_lint.plugins.patch_format.check_dep3_compliance')
    def test_process_file_non_compliant_patch(self, mock_check_dep3):
        """Test processing a non-compliant patch"""
        patch_content = [
            "# Patch without proper DEP-3 headers",
            "---",
            "--- a/file.c",
            "+++ b/file.c",
            "@@ -1,3 +1,3 @@",
            "-old line",
            "+new line"
        ]
        
        processed_file = create_test_processed_file("debian/patches/bad.patch", patch_content)
        
        # Create mock feedback items
        mock_feedback1 = FeedbackItem(
            message="Missing required Description/Subject field",
            rule_id=ErrorCode.PATCH_DEP3_MISSING_DESCRIPTION,
            severity=Severity.ERROR,
            span=MagicMock()
        )
        mock_feedback2 = FeedbackItem(
            message="Either an Origin field or an Author/From field must be provided",
            rule_id=ErrorCode.PATCH_DEP3_MISSING_ORIGIN_AUTHOR,
            severity=Severity.ERROR,
            span=MagicMock()
        )
        
        # Mock non-compliant result
        mock_check_dep3.return_value = (False, [mock_feedback1, mock_feedback2])
        
        self.plugin.process_file(processed_file)
        
        # Should create feedback for non-compliant patch
        self.assertEqual(len(self.plugin.feedback), 2)
        self.assertEqual(self.plugin.feedback[0], mock_feedback1)
        self.assertEqual(self.plugin.feedback[1], mock_feedback2)
        mock_check_dep3.assert_called_once()

    @patch('sru_lint.plugins.patch_format.check_dep3_compliance')
    def test_process_file_partial_compliance(self, mock_check_dep3):
        """Test processing a patch with warnings but no errors"""
        patch_content = [
            "Description: Fix something",
            "Author: Jane Doe <jane@example.com>",
            "Last-Update: invalid-date",  # Invalid date format
            "---",
            "--- a/file.c",
            "+++ b/file.c"
        ]
        
        processed_file = create_test_processed_file("debian/patches/partial.patch", patch_content)
        
        # Create mock warning feedback
        mock_feedback = FeedbackItem(
            message="Last-Update field must be a valid ISO date (YYYY-MM-DD)",
            rule_id=ErrorCode.PATCH_DEP3_INVALID_DATE,
            severity=Severity.WARNING,
            span=MagicMock()
        )
        
        # Mock result with warnings
        mock_check_dep3.return_value = (False, [mock_feedback])
        
        self.plugin.process_file(processed_file)
        
        # Should create warning feedback
        self.assertEqual(len(self.plugin.feedback), 1)
        self.assertEqual(self.plugin.feedback[0], mock_feedback)
        self.assertEqual(self.plugin.feedback[0].severity, Severity.WARNING)

    @patch('sru_lint.plugins.patch_format.check_dep3_compliance')
    def test_process_file_check_dep3_exception(self, mock_check_dep3):
        """Test handling of exceptions from check_dep3_compliance"""
        patch_content = [
            "Malformed patch content",
            "That causes parsing errors"
        ]
        
        processed_file = create_test_processed_file("debian/patches/malformed.patch", patch_content)
        
        # Mock exception
        mock_check_dep3.side_effect = Exception("Parse error occurred")
        
        self.plugin.process_file(processed_file)
        
        # Should create feedback for parsing error
        self.assertEqual(len(self.plugin.feedback), 1)
        feedback = self.plugin.feedback[0]
        self.assertEqual(feedback.rule_id, ErrorCode.PATCH_DEP3_FORMAT)
        self.assertEqual(feedback.severity, Severity.WARNING)
        self.assertIn("Failed to parse patch for DEP-3 compliance", feedback.message)
        self.assertIn("Parse error occurred", feedback.message)

    @patch('sru_lint.plugins.patch_format.check_dep3_compliance')
    def test_check_dep3_format_with_file_path(self, mock_check_dep3):
        """Test that check_dep3_format passes the correct file path"""
        patch_content = "Description: Test patch\n---\n"
        processed_file = create_test_processed_file("debian/patches/test.patch", [patch_content])
        
        mock_check_dep3.return_value = (True, [])
        
        self.plugin.check_dep3_format(processed_file, patch_content)
        
        # Verify that check_dep3_compliance was called with the file path
        mock_check_dep3.assert_called_once_with(patch_content, "debian/patches/test.patch")

    def test_symbolic_name(self):
        """Test that plugin has correct symbolic name"""
        self.assertEqual(self.plugin.__symbolic_name__, "patch-format")

    def test_feedback_management(self):
        """Test that plugin manages feedback correctly"""
        # Initially empty
        self.assertEqual(len(self.plugin.feedback), 0)
        
        # Create some feedback through exception handling
        patch_content = ["invalid content"]
        processed_file = create_test_processed_file("debian/patches/test.patch", patch_content)
        
        with patch('sru_lint.plugins.patch_format.check_dep3_compliance', side_effect=Exception("Test error")):
            self.plugin.process_file(processed_file)
        
        # Should have feedback now
        self.assertGreater(len(self.plugin.feedback), 0)

    @patch('sru_lint.plugins.patch_format.check_dep3_compliance')
    def test_multiple_patches_processing(self, mock_check_dep3):
        """Test processing multiple patch files"""
        # First patch - compliant
        patch1_content = ["Description: Fix bug A", "Author: Dev1", "---"]
        processed_file1 = create_test_processed_file("debian/patches/fix-a.patch", patch1_content)
        
        # Second patch - non-compliant
        patch2_content = ["# Bad patch", "---"]
        processed_file2 = create_test_processed_file("debian/patches/fix-b.patch", patch2_content)
        
        # Mock results
        mock_feedback = FeedbackItem(
            message="Missing required Description/Subject field",
            rule_id=ErrorCode.PATCH_DEP3_MISSING_DESCRIPTION,
            severity=Severity.ERROR,
            span=MagicMock()
        )
        mock_check_dep3.side_effect = [
            (True, []),  # First patch compliant
            (False, [mock_feedback])  # Second patch non-compliant
        ]
        
        self.plugin.process_file(processed_file1)
        self.plugin.process_file(processed_file2)
        
        # Should have feedback only from second patch
        self.assertEqual(len(self.plugin.feedback), 1)
        self.assertEqual(self.plugin.feedback[0], mock_feedback)
        self.assertEqual(mock_check_dep3.call_count, 2)

    def test_patch_content_combination(self):
        """Test that patch content is properly combined from added lines"""
        patch_lines = [
            "Description: Test patch",
            "Author: Test Author",
            "---",
            "--- a/file.c",
            "+++ b/file.c",
            "@@ -1,1 +1,1 @@",
            "-old",
            "+new"
        ]
        
        processed_file = create_test_processed_file("debian/patches/test.patch", patch_lines)
        
        # Mock to capture the patch content passed to check_dep3_compliance
        with patch('sru_lint.plugins.patch_format.check_dep3_compliance') as mock_check_dep3:
            mock_check_dep3.return_value = (True, [])
            
            self.plugin.process_file(processed_file)
            
            # Verify the patch content was properly combined
            expected_content = "\n".join(patch_lines)
            mock_check_dep3.assert_called_once_with(expected_content, "debian/patches/test.patch")

    def test_process_integration(self):
        """Integration test for the process method"""
        patch1_content = ["Description: Fix bug", "Author: Dev", "---"]
        patch2_content = ["# Bad patch", "---"]
        
        processed_files = [
            create_test_processed_file("debian/patches/good.patch", patch1_content),
            create_test_processed_file("debian/patches/bad.patch", patch2_content),
            create_test_processed_file("debian/patches/series", ["good.patch", "bad.patch"])  # Should be skipped
        ]
        
        with patch('sru_lint.plugins.patch_format.check_dep3_compliance') as mock_check_dep3:
            mock_feedback = FeedbackItem(
                message="Missing required Description/Subject field",
                rule_id=ErrorCode.PATCH_DEP3_MISSING_DESCRIPTION,
                severity=Severity.ERROR,
                span=MagicMock()
            )
            mock_check_dep3.side_effect = [
                (True, []),  # good.patch compliant
                (False, [mock_feedback])  # bad.patch non-compliant
                # series file should not call check_dep3_compliance
            ]
            
            result = self.plugin.process(processed_files)
            
            # Should return feedback from processing
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0], mock_feedback)
            
            # check_dep3_compliance should only be called twice (not for series file)
            self.assertEqual(mock_check_dep3.call_count, 2)


if __name__ == '__main__':
    unittest.main()