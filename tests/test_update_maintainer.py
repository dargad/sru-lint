import unittest
from unittest.mock import MagicMock, patch
from sru_lint.plugins.update_maintainer import UpdateMaintainer
from sru_lint.plugins.plugin_base import ProcessedFile
from sru_lint.common.feedback import SourceSpan, SourceLine, Severity
from sru_lint.common.debian.changelog import DebianChangelogHeader, parse_header
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


class TestUpdateMaintainer(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        self.plugin = UpdateMaintainer()
        self.plugin.feedback = []
        # Reset instance variables
        self.plugin.control_checked = False
        self.plugin.expect_control = False

    def test_register_file_patterns(self):
        """Test that the plugin registers debian/changelog and debian/control patterns"""
        self.plugin.register_file_patterns()
        
        # Check that both patterns are registered
        self.assertTrue(self.plugin.matches_file("debian/changelog"))
        self.assertTrue(self.plugin.matches_file("debian/control"))
        self.assertTrue(self.plugin.matches_file("package/debian/changelog"))
        self.assertTrue(self.plugin.matches_file("package/debian/control"))
        self.assertFalse(self.plugin.matches_file("debian/rules"))
        self.assertFalse(self.plugin.matches_file("changelog"))

    def test_is_ubuntu_version_true(self):
        """Test is_ubuntu_version returns True for Ubuntu versions"""
        # Mock header with Ubuntu version
        header = MagicMock()
        header.version = "1.0-1ubuntu1"
        
        result = self.plugin.is_ubuntu_version(header)
        self.assertTrue(result)

    def test_is_ubuntu_version_false(self):
        """Test is_ubuntu_version returns False for non-Ubuntu versions"""
        # Mock header with Debian version
        header = MagicMock()
        header.version = "1.0-1"
        
        result = self.plugin.is_ubuntu_version(header)
        self.assertFalse(result)

    def test_is_ubuntu_version_invalid_version(self):
        """Test is_ubuntu_version handles invalid version gracefully"""
        header = MagicMock()
        header.version = "invalid-version"
        
        with patch.object(self.plugin.logger, 'error') as mock_error:
            result = self.plugin.is_ubuntu_version(header)
            self.assertFalse(result)

    def test_is_update_maintainer_needed_true(self):
        """Test is_update_maintainer_needed returns True when update is needed"""
        # Mock headers: current is Ubuntu, previous is Debian
        current_header = MagicMock()
        current_header.version = "1.0-2ubuntu1"
        
        previous_header = MagicMock()
        previous_header.version = "1.0-1"
        
        headers = [current_header, previous_header]
        
        result = self.plugin.is_update_maintainer_needed(headers)
        self.assertTrue(result)

    def test_is_update_maintainer_needed_false_both_ubuntu(self):
        """Test is_update_maintainer_needed returns False when both versions are Ubuntu"""
        # Mock headers: both are Ubuntu versions
        current_header = MagicMock()
        current_header.version = "1.0-2ubuntu1"
        
        previous_header = MagicMock()
        previous_header.version = "1.0-1ubuntu1"
        
        headers = [current_header, previous_header]
        
        result = self.plugin.is_update_maintainer_needed(headers)
        self.assertFalse(result)

    def test_is_update_maintainer_needed_false_both_debian(self):
        """Test is_update_maintainer_needed returns False when both versions are Debian"""
        # Mock headers: both are Debian versions
        current_header = MagicMock()
        current_header.version = "1.0-2"
        
        previous_header = MagicMock()
        previous_header.version = "1.0-1"
        
        headers = [current_header, previous_header]
        
        result = self.plugin.is_update_maintainer_needed(headers)
        self.assertFalse(result)

    def test_is_update_maintainer_needed_insufficient_headers(self):
        """Test is_update_maintainer_needed returns False with insufficient headers"""
        # Test with empty headers
        result = self.plugin.is_update_maintainer_needed([])
        self.assertFalse(result)
        
        # Test with single header
        header = MagicMock()
        header.version = "1.0-1ubuntu1"
        result = self.plugin.is_update_maintainer_needed([header])
        self.assertFalse(result)

    @patch('sru_lint.plugins.update_maintainer.parse_header')
    def test_find_changelog_headers(self, mock_parse_header):
        """Test find_changelog_headers extracts headers from changelog content"""
        changelog_content = [
            "package (1.0-2ubuntu1) focal; urgency=medium",
            "",
            "  * Some changes",
            "",
            " -- Author <author@example.com>  Mon, 01 Jan 2024 12:00:00 +0000",
            "",
            "package (1.0-1) focal; urgency=medium",
            "",
            "  * Previous changes",
            "",
            " -- Author <author@example.com>  Sun, 31 Dec 2023 12:00:00 +0000"
        ]
        
        processed_file = create_test_processed_file("debian/control", changelog_content)
        
        # Mock parse_header to return headers for first and seventh lines
        def mock_parse_side_effect(line_content):
            if line_content.startswith("package (1.0-2ubuntu1)"):
                header = MagicMock()
                header.version = "1.0-2ubuntu1"
                return header
            elif line_content.startswith("package (1.0-1)"):
                header = MagicMock()
                header.version = "1.0-1"
                return header
            return None
        
        mock_parse_header.side_effect = mock_parse_side_effect
        
        headers = self.plugin.find_changelog_headers(processed_file)
        
        self.assertEqual(len(headers), 2)
        self.assertEqual(headers[0].version, "1.0-2ubuntu1")
        self.assertEqual(headers[1].version, "1.0-1")

    @patch('sru_lint.plugins.update_maintainer.parse_header')
    def test_find_changelog_headers_parse_error(self, mock_parse_header):
        """Test find_changelog_headers handles parse errors gracefully"""
        changelog_content = ["invalid changelog line"]
        processed_file = create_test_processed_file("debian/control", changelog_content)
        
        mock_parse_header.side_effect = Exception("Parse error")
        
        with patch.object(self.plugin.logger, 'debug') as mock_debug:
            headers = self.plugin.find_changelog_headers(processed_file)
            self.assertEqual(len(headers), 0)
            mock_debug.assert_called()

    def test_process_file_changelog_update_needed(self):
        """Test processing changelog file when maintainer update is needed"""
        changelog_content = [
            "package (1.0-2ubuntu1) focal; urgency=medium",
            "",
            "  * Some changes",
            "",
            " -- Author <author@example.com>  Mon, 01 Jan 2024 12:00:00 +0000"
        ]
        
        processed_file = create_test_processed_file("debian/changelog", changelog_content)
        
        # Mock find_changelog_headers to return headers indicating update needed
        with patch.object(self.plugin, 'find_changelog_headers') as mock_find:
            with patch.object(self.plugin, 'is_update_maintainer_needed') as mock_needed:
                mock_find.return_value = [
                    parse_header("package (1.0-2ubuntu1) focal; urgency=medium"),
                    parse_header("package (1.0-1) focal; urgency=medium")
                ]
                mock_needed.return_value = True
                
                self.plugin.process_file(processed_file)
                
                self.assertTrue(self.plugin.expect_control)

    def test_process_file_changelog_update_not_needed(self):
        """Test processing changelog file when maintainer update is not needed"""
        changelog_content = [
            "package (1.0-2ubuntu1) focal; urgency=medium",
            "",
            "  * Some changes",
            "",
            " -- Author <author@example.com>  Mon, 01 Jan 2024 12:00:00 +0000"
        ]
        
        processed_file = create_test_processed_file("debian/changelog", changelog_content)
        
        # Mock find_changelog_headers to return headers indicating update not needed
        with patch.object(self.plugin, 'find_changelog_headers') as mock_find:
            with patch.object(self.plugin, 'is_update_maintainer_needed') as mock_needed:
                mock_find.return_value = ["header1", "header2"]
                mock_needed.return_value = False
                
                self.plugin.process_file(processed_file)
                
                self.assertFalse(hasattr(self.plugin, 'expect_control') and self.plugin.expect_control)

    @patch('sru_lint.plugins.update_maintainer.Deb822')
    def test_process_file_control_maintainer_updated_correctly(self, mock_deb822):
        """Test processing control file with correctly updated maintainer"""
        control_content = [
            "Source: package",
            "Section: misc",
            "Priority: optional",
            f"Maintainer: {UpdateMaintainer.MAINTAINER_EXPECTED}",
            "XSBC-Original-Maintainer: Original Maintainer <orig@example.com>",
            "",
            "Package: package"
        ]
        
        processed_file = create_test_processed_file("debian/control", control_content)
        
        # Mock Deb822 parsing
        mock_control_data = {
            UpdateMaintainer.MAINTAINER_FIELD: UpdateMaintainer.MAINTAINER_EXPECTED,
            UpdateMaintainer.ORIGINAL_MAINTAINER_FIELD: "Original Maintainer <orig@example.com>"
        }
        mock_deb822.return_value = mock_control_data
        
        self.plugin.process_file(processed_file)
        
        self.assertTrue(self.plugin.control_checked)

    @patch('sru_lint.plugins.update_maintainer.Deb822')
    def test_process_file_control_maintainer_not_updated(self, mock_deb822):
        """Test processing control file with maintainer not updated"""
        control_content = [
            "Source: package",
            "Section: misc",
            "Priority: optional",
            "Maintainer: Original Maintainer <orig@example.com>",
            "",
            "Package: package"
        ]
        
        processed_file = create_test_processed_file("debian/control", control_content)
        
        # Mock Deb822 parsing - maintainer not updated
        mock_control_data = {
            UpdateMaintainer.MAINTAINER_FIELD: "Original Maintainer <orig@example.com>"
        }
        mock_deb822.return_value = mock_control_data
        
        self.plugin.process_file(processed_file)
        
        self.assertFalse(self.plugin.control_checked)

    @patch('sru_lint.plugins.update_maintainer.Deb822')
    def test_process_file_control_no_maintainer_field(self, mock_deb822):
        """Test processing control file with no maintainer field"""
        control_content = [
            "Source: package",
            "Section: misc",
            "Priority: optional",
            "",
            "Package: package"
        ]
        
        processed_file = create_test_processed_file("debian/control", control_content)
        
        # Mock Deb822 parsing - no maintainer field
        mock_control_data = {}
        mock_deb822.return_value = mock_control_data
        
        self.plugin.process_file(processed_file)
        
        self.assertFalse(self.plugin.control_checked)

    def test_post_process_control_missing_warning(self):
        """Test post_process creates warning when control file is expected but missing"""
        # Set up scenario where control is expected but not checked
        changelog_content = [
            "package (1.0-2ubuntu1) focal; urgency=medium",
            "",
            "  * Some changes",
            "",
            " -- Author <author@example.com>  Mon, 01 Jan 2024 12:00:00 +0000"
        ]
        processed_file = create_test_processed_file("debian/changelog", changelog_content)

        self.plugin.expect_control = True
        self.plugin.control_checked = False
        self.plugin.changelog = processed_file
        self.plugin.version = "2ubuntu1"

        with patch.object(self.plugin, 'create_line_feedback') as mock_create_line_feedback:
            self.plugin.post_process()

            mock_create_line_feedback.assert_called_once_with(
                message="Version number suggests Ubuntu changes, but Maintainer: does not have Ubuntu address.",
                rule_id=ErrorCode.CONTROL_MAINTAINER_NOT_UPDATED,
                severity=Severity.WARNING,
                source_span=self.plugin.changelog.source_span,
                doc_url="https://documentation.ubuntu.com/project/how-ubuntu-is-made/concepts/debian-directory/#the-control-file",
                target_line_content=self.plugin.version
            )

    def test_post_process_control_not_expected(self):
        """Test post_process does nothing when control file is not expected"""
        # Set up scenario where control is not expected
        self.plugin.expect_control = False
        self.plugin.control_checked = False
        
        with patch.object(self.plugin, 'create_feedback') as mock_create_feedback:
            self.plugin.post_process()
            
            mock_create_feedback.assert_not_called()

    def test_post_process_control_checked(self):
        """Test post_process does nothing when control file was already checked"""
        # Set up scenario where control was expected and checked
        self.plugin.expect_control = True
        self.plugin.control_checked = True
        
        with patch.object(self.plugin, 'create_feedback') as mock_create_feedback:
            self.plugin.post_process()
            
            mock_create_feedback.assert_not_called()

    def test_symbolic_name_generation(self):
        """Test that the plugin generates correct symbolic name"""
        self.assertEqual(UpdateMaintainer.__symbolic_name__, "update-maintainer")

    def test_maintainer_constants(self):
        """Test that the plugin defines expected constants"""
        self.assertEqual(UpdateMaintainer.MAINTAINER_FIELD, "Maintainer")
        self.assertEqual(UpdateMaintainer.MAINTAINER_EXPECTED, "Ubuntu Developers <ubuntu-devel-discuss@lists.ubuntu.com>")
        self.assertEqual(UpdateMaintainer.ORIGINAL_MAINTAINER_FIELD, "XSBC-Original-Maintainer")
        self.assertEqual(UpdateMaintainer.UBUNTU_IN_DEBIAN_REVISION, "ubuntu")

    def test_integration_scenario_maintainer_update_needed(self):
        """Integration test: full scenario where maintainer update is needed"""
        # Process changelog first
        changelog_content = [
            "package (1.0-2ubuntu1) focal; urgency=medium",
            "",
            "  * Ubuntu changes",
            "",
            " -- Ubuntu Developer <dev@ubuntu.com>  Mon, 01 Jan 2024 12:00:00 +0000",
            "",
            "package (1.0-1) focal; urgency=medium",
            "",
            "  * Original Debian changes",
            "",
            " -- Debian Developer <dev@debian.org>  Sun, 31 Dec 2023 12:00:00 +0000"
        ]
        
        changelog_file = create_test_processed_file("debian/changelog", changelog_content)
        
        # Mock changelog parsing
        with patch.object(self.plugin, 'find_changelog_headers') as mock_find:
            ubuntu_header = MagicMock()
            ubuntu_header.version = "1.0-2ubuntu1"
            debian_header = MagicMock()
            debian_header.version = "1.0-1"
            mock_find.return_value = [ubuntu_header, debian_header]
            
            self.plugin.process_file(changelog_file)
            
            # Should expect control file
            self.assertTrue(self.plugin.expect_control)
        
        # Now process control file with correct maintainer update
        control_content = [
            "Source: package",
            f"Maintainer: {UpdateMaintainer.MAINTAINER_EXPECTED}",
            "XSBC-Original-Maintainer: Debian Developer <dev@debian.org>"
        ]
        
        control_file = create_test_processed_file("debian/control", control_content)
        
        with patch('sru_lint.plugins.update_maintainer.Deb822') as mock_deb822:
            mock_control_data = {
                UpdateMaintainer.MAINTAINER_FIELD: UpdateMaintainer.MAINTAINER_EXPECTED,
                UpdateMaintainer.ORIGINAL_MAINTAINER_FIELD: "Debian Developer <dev@debian.org>"
            }
            mock_deb822.return_value = mock_control_data
            
            self.plugin.process_file(control_file)
            
            # Should mark control as checked
            self.assertTrue(self.plugin.control_checked)
        
        # Post-process should not create any warnings
        with patch.object(self.plugin, 'create_feedback') as mock_create_feedback:
            self.plugin.post_process()
            mock_create_feedback.assert_not_called()


if __name__ == '__main__':
    unittest.main()
