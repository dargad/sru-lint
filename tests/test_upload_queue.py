import unittest
from unittest.mock import MagicMock, patch
from sru_lint.plugins.upload_queue import UploadQueue
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


class TestUploadQueue(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        self.plugin = UploadQueue()
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

    @patch('sru_lint.plugins.upload_queue.changelog.Changelog')
    @patch('sru_lint.plugins.upload_queue.parse_distributions_field')
    def test_process_file_valid_changelog_no_queue(self, mock_parse_dist, mock_changelog_class):
        """Test processing a valid changelog with no uploads in queue"""
        changelog_content = [
            "package (1.0-1ubuntu1) jammy-proposed; urgency=medium",
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
        mock_entry.distributions = "jammy-proposed"
        
        mock_changelog_instance = MagicMock()
        mock_changelog_instance.__iter__.return_value = iter([mock_entry])
        mock_changelog_class.return_value = mock_changelog_instance
        
        # Mock distribution parsing
        mock_parse_dist.return_value = ["jammy-proposed"]
        
        # Mock Launchpad series and no uploads
        mock_series = MagicMock()
        mock_series.name = "jammy"
        mock_series.getPackageUploads.return_value = []
        self.mock_lp_helper.ubuntu.getSeries.return_value = mock_series
        
        self.plugin.process_file(processed_file)
        
        # Should not create any feedback for no uploads in queue
        self.assertEqual(len(self.plugin.feedback), 0)

    @patch('sru_lint.plugins.upload_queue.changelog.Changelog')
    @patch('sru_lint.plugins.upload_queue.parse_distributions_field')
    @patch('sru_lint.plugins.upload_queue.REVIEW_STATES', ['New', 'Unapproved'])
    def test_process_file_upload_in_queue(self, mock_parse_dist, mock_changelog_class):
        """Test processing changelog with upload already in queue"""
        changelog_content = [
            "package (1.0-1ubuntu1) jammy-proposed; urgency=medium",
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
        mock_entry.distributions = "jammy-proposed"
        
        mock_changelog_instance = MagicMock()
        mock_changelog_instance.__iter__.return_value = iter([mock_entry])
        mock_changelog_class.return_value = mock_changelog_instance
        
        # Mock distribution parsing
        mock_parse_dist.return_value = ["jammy-proposed"]
        
        # Mock upload in queue
        mock_upload = MagicMock()
        mock_upload.status = "New"
        mock_upload.pocket = "Proposed"
        
        mock_series = MagicMock()
        mock_series.name = "jammy"
        mock_series.getPackageUploads.return_value = [mock_upload]
        self.mock_lp_helper.ubuntu.getSeries.return_value = mock_series
        
        self.plugin.process_file(processed_file)
        
        # Should create feedback for upload in queue
        self.assertEqual(len(self.plugin.feedback), 1)
        feedback = self.plugin.feedback[0]
        self.assertEqual(feedback.rule_id, ErrorCode.UPLOAD_QUEUE_ALREADY_QUEUED)
        self.assertEqual(feedback.severity, Severity.WARNING)
        self.assertIn("already in upload queue", feedback.message)

    @patch('sru_lint.plugins.upload_queue.changelog.Changelog')
    @patch('sru_lint.plugins.upload_queue.parse_distributions_field')
    @patch('sru_lint.plugins.upload_queue.REVIEW_STATES', ['New', 'Unapproved'])
    def test_process_file_multiple_uploads_in_queue(self, mock_parse_dist, mock_changelog_class):
        """Test processing changelog with multiple uploads in queue"""
        changelog_content = [
            "package (1.0-1ubuntu1) jammy-proposed; urgency=medium",
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
        mock_entry.distributions = "jammy-proposed"
        
        mock_changelog_instance = MagicMock()
        mock_changelog_instance.__iter__.return_value = iter([mock_entry])
        mock_changelog_class.return_value = mock_changelog_instance
        
        # Mock distribution parsing
        mock_parse_dist.return_value = ["jammy-proposed"]
        
        # Mock multiple uploads in queue
        mock_upload1 = MagicMock()
        mock_upload1.status = "New"
        mock_upload1.pocket = "Proposed"
        
        mock_upload2 = MagicMock()
        mock_upload2.status = "Unapproved"
        mock_upload2.pocket = "Security"
        
        mock_series = MagicMock()
        mock_series.name = "jammy"
        mock_series.getPackageUploads.return_value = [mock_upload1, mock_upload2]
        self.mock_lp_helper.ubuntu.getSeries.return_value = mock_series
        
        self.plugin.process_file(processed_file)
        
        # Should create feedback for both uploads
        self.assertEqual(len(self.plugin.feedback), 2)

    @patch('sru_lint.plugins.upload_queue.changelog.Changelog')
    @patch('sru_lint.plugins.upload_queue.parse_distributions_field')
    @patch('sru_lint.plugins.upload_queue.REVIEW_STATES', ['New'])
    def test_process_file_upload_not_in_review_state(self, mock_parse_dist, mock_changelog_class):
        """Test processing with upload that's not in review state"""
        changelog_content = [
            "package (1.0-1ubuntu1) jammy-proposed; urgency=medium",
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
        mock_entry.distributions = "jammy-proposed"
        
        mock_changelog_instance = MagicMock()
        mock_changelog_instance.__iter__.return_value = iter([mock_entry])
        mock_changelog_class.return_value = mock_changelog_instance
        
        # Mock distribution parsing
        mock_parse_dist.return_value = ["jammy-proposed"]
        
        # Mock upload not in review state
        mock_upload = MagicMock()
        mock_upload.status = "Done"  # Not in REVIEW_STATES
        
        mock_series = MagicMock()
        mock_series.name = "jammy"
        mock_series.getPackageUploads.return_value = [mock_upload]
        self.mock_lp_helper.ubuntu.getSeries.return_value = mock_series
        
        self.plugin.process_file(processed_file)
        
        # Should not create feedback since upload is not in review state
        self.assertEqual(len(self.plugin.feedback), 0)

    @patch('sru_lint.plugins.upload_queue.changelog.Changelog')
    @patch('sru_lint.plugins.upload_queue.parse_distributions_field')
    def test_process_file_multiple_suites(self, mock_parse_dist, mock_changelog_class):
        """Test processing changelog with multiple distribution suites"""
        changelog_content = [
            "package (1.0-1ubuntu1) jammy-proposed focal-proposed; urgency=medium",
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
        mock_entry.distributions = "jammy-proposed focal-proposed"
        
        mock_changelog_instance = MagicMock()
        mock_changelog_instance.__iter__.return_value = iter([mock_entry])
        mock_changelog_class.return_value = mock_changelog_instance
        
        # Mock distribution parsing
        mock_parse_dist.return_value = ["jammy-proposed", "focal-proposed"]
        
        # Mock series calls
        def mock_get_series(name_or_version):
            mock_series = MagicMock()
            mock_series.name = name_or_version
            mock_series.getPackageUploads.return_value = []
            return mock_series
        
        self.mock_lp_helper.ubuntu.getSeries.side_effect = mock_get_series
        
        self.plugin.process_file(processed_file)
        
        # Should have called getSeries for both jammy and focal
        expected_calls = [unittest.mock.call(name_or_version="jammy"), 
                         unittest.mock.call(name_or_version="focal")]
        self.mock_lp_helper.ubuntu.getSeries.assert_has_calls(expected_calls, any_order=True)

    @patch('sru_lint.plugins.upload_queue.changelog.Changelog')
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
        self.assertEqual(feedback.rule_id, ErrorCode.UPLOAD_QUEUE_PARSE_ERROR)
        self.assertEqual(feedback.severity, Severity.WARNING)
        self.assertIn("Failed to parse changelog", feedback.message)

    def test_process_file_no_lp_helper(self):
        """Test processing when Launchpad helper is not available"""
        changelog_content = [
            "package (1.0-1ubuntu1) jammy-proposed; urgency=medium",
            "",
            "  * Fix for bug",
            "",
            " -- Author <author@example.com>  Mon, 01 Jan 2024 12:00:00 +0000"
        ]
        
        processed_file = create_test_processed_file("debian/changelog", changelog_content)
        
        # Remove lp_helper
        del self.plugin.lp_helper
        
        with patch('sru_lint.plugins.upload_queue.changelog.Changelog') as mock_changelog_class:
            with patch('sru_lint.plugins.upload_queue.parse_distributions_field') as mock_parse_dist:
                mock_entry = MagicMock()
                mock_entry.package = "package"
                mock_entry.version = "1.0-1ubuntu1"
                mock_entry.distributions = "jammy-proposed"
                
                mock_changelog_instance = MagicMock()
                mock_changelog_instance.__iter__.return_value = iter([mock_entry])
                mock_changelog_class.return_value = mock_changelog_instance
                mock_parse_dist.return_value = ["jammy-proposed"]
                
                self.plugin.process_file(processed_file)
        
        # Should not create any feedback when lp_helper is unavailable
        self.assertEqual(len(self.plugin.feedback), 0)

    @patch('sru_lint.plugins.upload_queue.changelog.Changelog')
    @patch('sru_lint.plugins.upload_queue.parse_distributions_field')
    def test_check_upload_queue_api_error(self, mock_parse_dist, mock_changelog_class):
        """Test handling of Launchpad API errors"""
        changelog_content = [
            "package (1.0-1ubuntu1) jammy-proposed; urgency=medium",
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
        mock_entry.distributions = "jammy-proposed"
        
        mock_changelog_instance = MagicMock()
        mock_changelog_instance.__iter__.return_value = iter([mock_entry])
        mock_changelog_class.return_value = mock_changelog_instance
        
        # Mock distribution parsing
        mock_parse_dist.return_value = ["jammy-proposed"]
        
        # Mock API error
        self.mock_lp_helper.ubuntu.getSeries.side_effect = Exception("API Error")
        
        self.plugin.process_file(processed_file)
        
        # Should create feedback for API error
        self.assertEqual(len(self.plugin.feedback), 1)
        feedback = self.plugin.feedback[0]
        self.assertEqual(feedback.rule_id, ErrorCode.UPLOAD_QUEUE_API_ERROR)
        self.assertEqual(feedback.severity, Severity.WARNING)
        self.assertIn("Failed to check upload queue", feedback.message)
        self.assertIn("API Error", feedback.message)

    @patch('sru_lint.plugins.upload_queue.changelog.Changelog')
    @patch('sru_lint.plugins.upload_queue.parse_distributions_field')
    def test_check_upload_queue_suite_error(self, mock_parse_dist, mock_changelog_class):
        """Test handling of suite-specific errors"""
        changelog_content = [
            "package (1.0-1ubuntu1) jammy-proposed focal-proposed; urgency=medium",
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
        mock_entry.distributions = "jammy-proposed focal-proposed"
        
        mock_changelog_instance = MagicMock()
        mock_changelog_instance.__iter__.return_value = iter([mock_entry])
        mock_changelog_class.return_value = mock_changelog_instance
        
        # Mock distribution parsing
        mock_parse_dist.return_value = ["jammy-proposed", "focal-proposed"]
        
        # Mock suite-specific error for focal
        def mock_get_series(name_or_version):
            if name_or_version == "focal":
                raise Exception("Suite error for focal")
            mock_series = MagicMock()
            mock_series.name = name_or_version
            mock_series.getPackageUploads.return_value = []
            return mock_series
        
        self.mock_lp_helper.ubuntu.getSeries.side_effect = mock_get_series
        
        self.plugin.process_file(processed_file)
        
        # Should create feedback for suite error
        self.assertEqual(len(self.plugin.feedback), 1)
        feedback = self.plugin.feedback[0]
        self.assertEqual(feedback.rule_id, ErrorCode.UPLOAD_QUEUE_API_ERROR)
        self.assertIn("focal", feedback.message)

    def test_find_version_line_span_found(self):
        """Test finding version line span when version is in content"""
        changelog_content = [
            "package (1.0-1ubuntu1) jammy-proposed; urgency=medium",
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
            "package (1.0-1ubuntu1) jammy-proposed; urgency=medium",
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
        self.assertEqual(self.plugin.__symbolic_name__, "upload-queue")

    @patch('sru_lint.plugins.upload_queue.changelog.Changelog')
    @patch('sru_lint.plugins.upload_queue.parse_distributions_field')
    def test_multiple_changelog_entries(self, mock_parse_dist, mock_changelog_class):
        """Test processing changelog with multiple entries"""
        changelog_content = [
            "package (1.0-1ubuntu2) jammy-proposed; urgency=medium",
            "",
            "  * Another fix",
            "",
            " -- Author <author@example.com>  Mon, 01 Jan 2024 12:00:00 +0000",
            "",
            "package (1.0-1ubuntu1) jammy-proposed; urgency=medium",
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
        mock_entry1.distributions = "jammy-proposed"
        
        mock_entry2 = MagicMock()
        mock_entry2.package = "package"
        mock_entry2.version = "1.0-1ubuntu1"
        mock_entry2.distributions = "jammy-proposed"
        
        mock_changelog_instance = MagicMock()
        mock_changelog_instance.__iter__.return_value = iter([mock_entry1, mock_entry2])
        mock_changelog_class.return_value = mock_changelog_instance
        
        # Mock distribution parsing
        mock_parse_dist.return_value = ["jammy-proposed"]
        
        # Mock series with no uploads
        mock_series = MagicMock()
        mock_series.name = "jammy"
        mock_series.getPackageUploads.return_value = []
        self.mock_lp_helper.ubuntu.getSeries.return_value = mock_series
        
        self.plugin.process_file(processed_file)
        
        # Should have checked both versions
        self.assertEqual(self.mock_lp_helper.ubuntu.getSeries.call_count, 2)
        self.assertEqual(len(self.plugin.feedback), 0)


if __name__ == '__main__':
    unittest.main()