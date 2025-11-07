import unittest
from unittest.mock import MagicMock, patch
from sru_lint.plugins.publishing_history import PublishingHistory
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


class TestPublishingHistory(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        self.plugin = PublishingHistory()
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
        
        # Should not create any feedback for empty content
        self.assertEqual(len(self.plugin.feedback), 0)

    @patch('sru_lint.plugins.publishing_history.changelog.Changelog')
    def test_process_file_valid_changelog(self, mock_changelog_class):
        """Test processing a valid changelog with unpublished version"""
        changelog_content = [
            "package (1.0-1ubuntu1) focal; urgency=medium",
            "",
            "  * Fix for bug",
            "",
            " -- Author <author@example.com>  Mon, 01 Jan 2024 12:00:00 +0000"
        ]
        
        processed_file = create_test_processed_file("debian/changelog", changelog_content)
        
        # Mock changelog entry
        mock_entry = MagicMock()
        mock_entry.package = "package"
        mock_entry.version = "1.0-1ubuntu1"
        
        mock_changelog_instance = MagicMock()
        mock_changelog_instance.__iter__.return_value = iter([mock_entry])
        mock_changelog_instance.__getitem__.side_effect = [mock_entry]
        mock_changelog_class.return_value = mock_changelog_instance
        
        # Mock no publications found
        self.mock_lp_helper.archive.getPublishedSources.return_value = []
        
        self.plugin.process_file(processed_file)
        
        # Should not create any feedback for unpublished version
        self.assertEqual(len(self.plugin.feedback), 0)
        self.mock_lp_helper.archive.getPublishedSources.assert_any_call(
            source_name="package",
            exact_match=True,
            version="1.0-1ubuntu1"
        )
        self.mock_lp_helper.archive.getPublishedSources.assert_any_call(
            source_name="package",
            exact_match=True,
        )

    @patch('sru_lint.plugins.publishing_history.changelog.Changelog')
    def test_process_file_already_published_version(self, mock_changelog_class):
        """Test processing changelog with already published version"""
        changelog_content = [
            "package (1.0-1ubuntu1) focal; urgency=medium",
            "",
            "  * Fix for bug",
            "",
            " -- Author <author@example.com>  Mon, 01 Jan 2024 12:00:00 +0000"
        ]
        
        processed_file = create_test_processed_file("debian/changelog", changelog_content)
        
        # Mock changelog entry
        mock_entry = MagicMock()
        mock_entry.package = "package"
        mock_entry.version = "1.0-1ubuntu1"
        mock_entry.distributions = "focal"
        
        mock_changelog_instance = MagicMock()
        mock_changelog_instance.__iter__.return_value = iter([mock_entry])
        mock_changelog_instance.__getitem__.side_effect = [mock_entry]
        mock_changelog_class.return_value = mock_changelog_instance
        
        # Mock publication found
        mock_publication = MagicMock()
        mock_publication.source_package_version = "1.0-1ubuntu1"
        mock_publication.distro_series.name = "focal"
        mock_publication.pocket = "Release"
        mock_publication.status = "Published"
        
        self.mock_lp_helper.archive.getPublishedSources.return_value = [mock_publication]
        
        self.plugin.process_file(processed_file)
        
        # Should create feedback for already published version
        self.assertEqual(len(self.plugin.feedback), 1)
        feedback = self.plugin.feedback[0]
        self.assertEqual(feedback.rule_id, ErrorCode.PUBLISHING_HISTORY_ALREADY_PUBLISHED)
        self.assertEqual(feedback.severity, Severity.ERROR)
        self.assertIn("already published", feedback.message)
        self.assertIn("focal/Release/Published", feedback.message)

    @patch('sru_lint.plugins.publishing_history.changelog.Changelog')
    def test_process_file_multiple_publications(self, mock_changelog_class):
        """Test processing changelog with version published in multiple places"""
        changelog_content = [
            "package (1.0-1ubuntu1) focal; urgency=medium",
            "",
            "  * Fix for bug",
            "",
            " -- Author <author@example.com>  Mon, 01 Jan 2024 12:00:00 +0000"
        ]
        
        processed_file = create_test_processed_file("debian/changelog", changelog_content)
        
        # Mock changelog entry
        mock_entry = MagicMock()
        mock_entry.package = "package"
        mock_entry.version = "1.0-1ubuntu1"
        mock_entry.distributions = "focal"
        
        mock_changelog_instance = MagicMock()
        mock_changelog_instance.__iter__.return_value = iter([mock_entry])
        mock_changelog_instance.__getitem__.side_effect = [mock_entry]
        mock_changelog_class.return_value = mock_changelog_instance
        
        # Mock multiple publications found
        mock_pub1 = MagicMock()
        mock_pub1.source_package_version = "1.0-1ubuntu1"
        mock_pub1.distro_series.name = "focal"
        mock_pub1.pocket = "Release"
        mock_pub1.status = "Published"
        
        mock_pub2 = MagicMock()
        mock_pub2.source_package_version = "1.0-1ubuntu1"
        mock_pub2.distro_series.name = "focal"
        mock_pub2.pocket = "Security"
        mock_pub2.status = "Published"
        
        self.mock_lp_helper.archive.getPublishedSources.return_value = [mock_pub1, mock_pub2]
        
        self.plugin.process_file(processed_file)
        
        # Should create feedback mentioning both publications
        self.assertEqual(len(self.plugin.feedback), 1)
        feedback = self.plugin.feedback[0]
        self.assertIn("focal/Release/Published", feedback.message)
        self.assertIn("focal/Security/Published", feedback.message)

    @patch('sru_lint.plugins.publishing_history.changelog.Changelog')
    def test_process_file_multiple_entries(self, mock_changelog_class):
        """Test processing changelog with multiple entries"""
        changelog_content = [
            "package (1.0-1ubuntu2) focal; urgency=medium",
            "",
            "  * Another fix",
            "",
            " -- Author <author@example.com>  Mon, 01 Jan 2024 12:00:00 +0000",
            "",
            "package (1.0-1ubuntu1) focal; urgency=medium",
            "",
            "  * Fix for bug",
            "",
            " -- Author <author@example.com>  Sun, 31 Dec 2023 12:00:00 +0000"
        ]
        
        processed_file = create_test_processed_file("debian/changelog", changelog_content)
        
        # Mock changelog entries
        mock_entry1 = MagicMock()
        mock_entry1.package = "package"
        mock_entry1.version = "1.0-1ubuntu2"
        mock_entry1.distributions = "focal"
        
        mock_entry2 = MagicMock()
        mock_entry2.package = "package"
        mock_entry2.version = "1.0-1ubuntu1"
        mock_entry2.distributions = "focal"
        
        mock_changelog_instance = MagicMock()
        mock_changelog_instance.__iter__.return_value = iter([mock_entry1, mock_entry2])
        mock_changelog_class.return_value = mock_changelog_instance
        
        # Mock publication of second version only
        mock_publication = MagicMock()
        mock_publication.source_package_version = "1.0-1ubuntu1"
        mock_publication.distro_series.name = "focal"
        mock_publication.pocket = "Release"
        mock_publication.status = "Published"
        
        self.mock_lp_helper.archive.getPublishedSources.return_value = [mock_publication]
        
        self.plugin.process_file(processed_file)
        
        # Should create feedback only for the published version
        self.assertEqual(len(self.plugin.feedback), 1)
        feedback = self.plugin.feedback[0]
        self.assertNotIn("1.0-1ubuntu2", feedback.message)

    @patch('sru_lint.plugins.publishing_history.changelog.Changelog')
    def test_process_file_changelog_parse_error(self, mock_changelog_class):
        """Test processing file with malformed changelog"""
        changelog_content = [
            "malformed changelog entry",
            "not a valid format"
        ]
        
        processed_file = create_test_processed_file("debian/changelog", changelog_content)
        
        # Mock changelog parsing error
        mock_changelog_class.side_effect = Exception("Parse error")
        
        self.plugin.process_file(processed_file)
        
        # Should create feedback for parsing error
        self.assertEqual(len(self.plugin.feedback), 1)
        feedback = self.plugin.feedback[0]
        self.assertEqual(feedback.rule_id, ErrorCode.PUBLISHING_HISTORY_PARSE_ERROR)
        self.assertEqual(feedback.severity, Severity.WARNING)
        self.assertIn("Failed to parse changelog", feedback.message)

    def test_process_file_no_lp_helper(self):
        """Test processing when Launchpad helper is not available"""
        changelog_content = [
            "package (1.0-1ubuntu1) focal; urgency=medium",
            "",
            "  * Fix for bug",
            "",
            " -- Author <author@example.com>  Mon, 01 Jan 2024 12:00:00 +0000"
        ]
        
        processed_file = create_test_processed_file("debian/changelog", changelog_content)
        
        # Remove lp_helper
        del self.plugin.lp_helper

        with patch('sru_lint.plugins.publishing_history.changelog.Changelog') as mock_changelog_class:
            mock_entry = MagicMock()
            mock_entry.package = "package"
            mock_entry.version = "1.0-1ubuntu1"
            
            mock_changelog_instance = MagicMock()
            mock_changelog_instance.__iter__.return_value = iter([mock_entry])
            mock_changelog_class.return_value = mock_changelog_instance
            
            self.plugin.process_file(processed_file)
        
        # Should not create any feedback when lp_helper is unavailable
        self.assertEqual(len(self.plugin.feedback), 0)

    @patch('sru_lint.plugins.publishing_history.changelog.Changelog')
    def test_check_version_publishing_api_error(self, mock_changelog_class):
        """Test handling of Launchpad API errors"""
        changelog_content = [
            "package (1.0-1ubuntu1) focal; urgency=medium",
            "",
            "  * Fix for bug",
            "",
            " -- Author <author@example.com>  Mon, 01 Jan 2024 12:00:00 +0000"
        ]
        
        processed_file = create_test_processed_file("debian/changelog", changelog_content)
        
        # Mock changelog entry
        mock_entry = MagicMock()
        mock_entry.package = "package"
        mock_entry.version = "1.0-1ubuntu1"
        
        mock_changelog_instance = MagicMock()
        mock_changelog_instance.__iter__.return_value = iter([mock_entry])
        mock_changelog_class.return_value = mock_changelog_instance
        
        # Mock API error
        self.mock_lp_helper.archive.getPublishedSources.side_effect = Exception("API Error")
        
        self.plugin.process_file(processed_file)
        
        # Should create feedback for API error
        self.assertEqual(len(self.plugin.feedback), 1)
        feedback = self.plugin.feedback[0]
        self.assertEqual(feedback.rule_id, ErrorCode.PUBLISHING_HISTORY_API_ERROR)
        self.assertEqual(feedback.severity, Severity.WARNING)
        self.assertIn("Failed to check publishing history", feedback.message)
        self.assertIn("API Error", feedback.message)

    def test_find_version_line_span_found(self):
        """Test finding version line span when version is in content"""
        changelog_content = [
            "package (1.0-1ubuntu1) focal; urgency=medium",
            "",
            "  * Fix for bug"
        ]
        
        processed_file = create_test_processed_file("debian/changelog", changelog_content)
        
        span = self.plugin.find_version_line_span(processed_file, "1.0-1ubuntu1")
        
        # Should find the version on line 1
        self.assertEqual(span.start_line, 1)
        self.assertEqual(span.end_line, 1)
        self.assertEqual(span.path, "debian/changelog")

    def test_find_version_line_span_not_found(self):
        """Test finding version line span when version is not in content"""
        changelog_content = [
            "package (1.0-1ubuntu1) focal; urgency=medium",
            "",
            "  * Fix for bug"
        ]
        
        processed_file = create_test_processed_file("debian/changelog", changelog_content)
        
        span = self.plugin.find_version_line_span(processed_file, "2.0-1ubuntu1")
        
        # Should fallback to line 1
        self.assertEqual(span.start_line, 1)
        self.assertEqual(span.end_line, 1)
        self.assertEqual(span.path, "debian/changelog")

    def test_symbolic_name(self):
        """Test that plugin has correct symbolic name"""
        self.assertEqual(self.plugin.__symbolic_name__, "publishing-history")

    def test_feedback_management(self):
        """Test that plugin manages feedback correctly"""
        # Initially empty
        self.assertEqual(len(self.plugin.feedback), 0)
        
        # Create some feedback through parsing error
        processed_file = create_test_processed_file("debian/changelog", ["invalid content"])

        with patch('sru_lint.plugins.publishing_history.changelog.Changelog', side_effect=Exception("Test error")):
            self.plugin.process_file(processed_file)
        
        # Should have feedback now
        self.assertGreater(len(self.plugin.feedback), 0)

    @patch('sru_lint.plugins.publishing_history.changelog.Changelog')
    def test_integration_test(self, mock_changelog_class):
        """Integration test combining multiple scenarios"""
        changelog_content = [
            "package (1.0-1ubuntu2) focal; urgency=medium",
            "",
            "  * New fix",
            "",
            " -- Author <author@example.com>  Mon, 01 Jan 2024 12:00:00 +0000",
            "",
            "package (1.0-1ubuntu1) focal; urgency=medium",
            "",
            "  * Original fix",
            "",
            " -- Author <author@example.com>  Sun, 31 Dec 2023 12:00:00 +0000"
        ]
        
        processed_file = create_test_processed_file("debian/changelog", changelog_content)
        
        # Mock changelog entries
        mock_entry1 = MagicMock()
        mock_entry1.package = "package"
        mock_entry1.version = "1.0-1ubuntu2"
        mock_entry1.distributions = "focal"
        
        mock_entry2 = MagicMock()
        mock_entry2.package = "package"
        mock_entry2.version = "1.0-1ubuntu1"
        mock_entry2.distributions = "focal"
        
        mock_changelog_instance = MagicMock()
        mock_changelog_instance.__getitem__.side_effect = [mock_entry1]
        mock_changelog_instance.__iter__.return_value = iter([mock_entry1, mock_entry2])
        mock_changelog_class.return_value = mock_changelog_instance
        
        mock_pub2 = MagicMock()
        mock_pub2.source_package_version = "1.0-1ubuntu2"
        mock_pub2.distro_series.name = "focal"
        mock_pub2.pocket = "Updates"
        mock_pub2.status = "Published"
        mock_pub2.package = "package"
        
        self.mock_lp_helper.archive.getPublishedSources.return_value = [mock_pub2]
        
        self.plugin.process_file(processed_file)
        
        # Should create feedback only for the latest version
        self.assertEqual(len(self.plugin.feedback), 1)
        
        messages = [f.message for f in self.plugin.feedback]
        self.assertTrue(any("1.0-1ubuntu2" in msg for msg in messages))


if __name__ == '__main__':
    unittest.main()