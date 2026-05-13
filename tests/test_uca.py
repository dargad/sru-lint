import unittest
from unittest.mock import MagicMock

from sru_lint.common.errors import ErrorCode
from sru_lint.common.feedback import Severity, SourceLine, SourceSpan
from sru_lint.plugins.plugin_base import ProcessedFile
from sru_lint.plugins.uca import UCAPlugin


def create_test_source_span(path, lines_content, lines_added_indices=None, start_line=1):
    if lines_added_indices is None:
        lines_added_indices = list(range(len(lines_content)))

    lines_with_context = []
    for i, content in enumerate(lines_content):
        line_number = start_line + i
        is_added = i in lines_added_indices
        lines_with_context.append(
            SourceLine(content=content, line_number=line_number, is_added=is_added)
        )

    content = [line for line in lines_with_context if line.is_added]

    return SourceSpan(
        path=path,
        start_line=start_line,
        start_col=1,
        end_line=start_line + len(lines_content) - 1,
        end_col=1,
        content=content,
        content_with_context=lines_with_context,
    )


def create_test_processed_file(path, lines_content, lines_added_indices=None, start_line=1):
    source_span = create_test_source_span(path, lines_content, lines_added_indices, start_line)
    return ProcessedFile(path=path, source_span=source_span)


def make_changelog(version: str, distribution: str) -> list[str]:
    return [
        f"package ({version}) {distribution}; urgency=medium",
        "",
        "  * Some change",
        "",
        " -- Author <author@example.com>  Mon, 01 Jan 2024 12:00:00 +0000",
    ]


class TestUCAPlugin(unittest.TestCase):
    def setUp(self):
        self.plugin = UCAPlugin()
        self.mock_lp_helper = MagicMock()
        # Default: no LP bugs in the changelog and valid bug targeting if asked.
        self.mock_lp_helper.extract_lp_bugs.return_value = []
        self.mock_lp_helper.get_uca_bug_targeting.return_value = (True, True)
        self.plugin.lp_helper = self.mock_lp_helper
        self.plugin.feedback = []

    def test_register_file_patterns(self):
        self.assertTrue(self.plugin.matches_file("debian/changelog"))
        self.assertTrue(self.plugin.matches_file("package/debian/changelog"))
        self.assertFalse(self.plugin.matches_file("debian/control"))

    def test_symbolic_name(self):
        self.assertEqual(self.plugin.__symbolic_name__, "uca-plugin")

    def test_non_uca_changelog_ignored(self):
        """A regular SRU entry (no ~cloud suffix) must not be touched."""
        processed_file = create_test_processed_file(
            "debian/changelog", make_changelog("1.0-1ubuntu1", "jammy")
        )
        self.plugin.process_file(processed_file)
        self.mock_lp_helper.is_valid_uca_distribution.assert_not_called()
        self.assertEqual(len(self.plugin.feedback), 0)

    def test_valid_uca_entry(self):
        """A well-formed UCA entry produces no feedback."""
        self.mock_lp_helper.is_valid_uca_distribution.return_value = (True, None)
        processed_file = create_test_processed_file(
            "debian/changelog", make_changelog("1.0-1ubuntu1~cloud0", "jammy-caracal")
        )
        self.plugin.process_file(processed_file)
        self.mock_lp_helper.is_valid_uca_distribution.assert_called_once_with("jammy-caracal")
        self.assertEqual(len(self.plugin.feedback), 0)

    def test_valid_uca_entry_higher_cloud_number(self):
        """~cloudN with N > 0 is accepted."""
        self.mock_lp_helper.is_valid_uca_distribution.return_value = (True, None)
        processed_file = create_test_processed_file(
            "debian/changelog",
            make_changelog("1.0-1ubuntu1.1~cloud3", "noble-epoxy"),
        )
        self.plugin.process_file(processed_file)
        self.assertEqual(len(self.plugin.feedback), 0)

    def test_invalid_pairing(self):
        """jammy-epoxy: both halves known, not paired."""
        self.mock_lp_helper.is_valid_uca_distribution.return_value = (
            False,
            ErrorCode.UCA_INVALID_PAIRING,
        )
        processed_file = create_test_processed_file(
            "debian/changelog", make_changelog("1.0-1ubuntu1~cloud0", "jammy-epoxy")
        )
        self.plugin.process_file(processed_file)
        self.assertEqual(len(self.plugin.feedback), 1)
        feedback = self.plugin.feedback[0]
        self.assertEqual(feedback.rule_id, ErrorCode.UCA_INVALID_PAIRING)
        self.assertEqual(feedback.severity, Severity.ERROR)
        self.assertIn("jammy-epoxy", feedback.message)

    def test_unknown_openstack_release(self):
        self.mock_lp_helper.is_valid_uca_distribution.return_value = (
            False,
            ErrorCode.UCA_UNKNOWN_OPENSTACK_RELEASE,
        )
        processed_file = create_test_processed_file(
            "debian/changelog",
            make_changelog("1.0-1ubuntu1~cloud0", "jammy-notarelease"),
        )
        self.plugin.process_file(processed_file)
        self.assertEqual(len(self.plugin.feedback), 1)
        feedback = self.plugin.feedback[0]
        self.assertEqual(feedback.rule_id, ErrorCode.UCA_UNKNOWN_OPENSTACK_RELEASE)

    def test_invalid_distribution_shape(self):
        """A distribution missing the dash is rejected as UCA_INVALID_DISTRIBUTION."""
        self.mock_lp_helper.is_valid_uca_distribution.return_value = (
            False,
            ErrorCode.UCA_INVALID_DISTRIBUTION,
        )
        processed_file = create_test_processed_file(
            "debian/changelog", make_changelog("1.0-1ubuntu1~cloud0", "jammy")
        )
        self.plugin.process_file(processed_file)
        self.assertEqual(len(self.plugin.feedback), 1)
        self.assertEqual(self.plugin.feedback[0].rule_id, ErrorCode.UCA_INVALID_DISTRIBUTION)

    def test_malformed_cloud_suffix(self):
        """A version with '~cloud' but no trailing digits fails the suffix check."""
        self.mock_lp_helper.is_valid_uca_distribution.return_value = (True, None)
        processed_file = create_test_processed_file(
            "debian/changelog",
            make_changelog("1.0-1ubuntu1~cloudX", "jammy-caracal"),
        )
        self.plugin.process_file(processed_file)
        suffix_errors = [
            f for f in self.plugin.feedback if f.rule_id == ErrorCode.UCA_INVALID_VERSION_SUFFIX
        ]
        self.assertEqual(len(suffix_errors), 1)

    def test_empty_added_content(self):
        processed_file = create_test_processed_file(
            "debian/changelog", ["# comment"], lines_added_indices=[]
        )
        self.plugin.process_file(processed_file)
        self.assertEqual(len(self.plugin.feedback), 0)
        self.mock_lp_helper.is_valid_uca_distribution.assert_not_called()

    def test_bug_targeting_valid(self):
        """Bug targeted at cloud-archive/<openstack> produces no feedback."""
        self.mock_lp_helper.is_valid_uca_distribution.return_value = (True, None)
        self.mock_lp_helper.extract_lp_bugs.return_value = [2141119]
        self.mock_lp_helper.get_uca_bug_targeting.return_value = (True, True)
        processed_file = create_test_processed_file(
            "debian/changelog",
            make_changelog("1.0-1ubuntu1~cloud0", "noble-epoxy"),
        )
        self.plugin.process_file(processed_file)
        self.mock_lp_helper.get_uca_bug_targeting.assert_called_once_with(2141119, "epoxy")
        self.assertEqual(len(self.plugin.feedback), 0)

    def test_bug_not_targeted_at_cloud_archive(self):
        """No task on cloud-archive at all -> UCA_BUG_NOT_TARGETED."""
        self.mock_lp_helper.is_valid_uca_distribution.return_value = (True, None)
        self.mock_lp_helper.extract_lp_bugs.return_value = [2141119]
        self.mock_lp_helper.get_uca_bug_targeting.return_value = (False, False)
        processed_file = create_test_processed_file(
            "debian/changelog",
            make_changelog("1.0-1ubuntu1~cloud0", "noble-epoxy"),
        )
        self.plugin.process_file(processed_file)
        self.assertEqual(len(self.plugin.feedback), 1)
        feedback = self.plugin.feedback[0]
        self.assertEqual(feedback.rule_id, ErrorCode.UCA_BUG_NOT_TARGETED)
        self.assertEqual(feedback.severity, Severity.WARNING)
        self.assertIn("2141119", feedback.message)

    def test_bug_targeted_but_series_missing(self):
        """Project task exists but not for the series -> UCA_BUG_SERIES_NOT_TARGETED."""
        self.mock_lp_helper.is_valid_uca_distribution.return_value = (True, None)
        self.mock_lp_helper.extract_lp_bugs.return_value = [2141119]
        self.mock_lp_helper.get_uca_bug_targeting.return_value = (True, False)
        processed_file = create_test_processed_file(
            "debian/changelog",
            make_changelog("1.0-1ubuntu1~cloud0", "noble-epoxy"),
        )
        self.plugin.process_file(processed_file)
        self.assertEqual(len(self.plugin.feedback), 1)
        feedback = self.plugin.feedback[0]
        self.assertEqual(feedback.rule_id, ErrorCode.UCA_BUG_SERIES_NOT_TARGETED)
        self.assertEqual(feedback.severity, Severity.WARNING)
        self.assertIn("cloud-archive/epoxy", feedback.message)


if __name__ == "__main__":
    unittest.main()
