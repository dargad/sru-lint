from sru_lint.common.debian.changelog import DebianChangelogHeader, parse_header
from sru_lint.common.errors import ErrorCode
from sru_lint.common.feedback import FeedbackItem, Severity, SourceSpan
from sru_lint.plugins.plugin_base import Plugin
from sru_lint.common.patches import combine_added_lines

from debian import changelog
from debian.debian_support import Version


class ChangelogEntry(Plugin):
    """Checks the changelog entry."""

    def register_file_patterns(self):
        """Register that we want to check debian/changelog files."""
        self.add_file_pattern("debian/changelog")

    def process_file(self, patched_file) -> None:
        """
        Checks done in the changelog entry:
        - Check if the distribution is valid
        - Check if LP bugs are properly targeted
        """
        self.logger.info("Processing changelog entry")

        content = combine_added_lines(patched_file)
        content_with_context = combine_added_lines(patched_file, include_context=True)

        # Parse changelog headers for version ordering
        changelog_headers = []
        for k in content_with_context:
            file_content = content_with_context[k]
            for line_no, line in enumerate(file_content.splitlines(), 1):
                try:
                    header = parse_header(line)
                    changelog_headers.append(header)
                except ValueError:
                    continue

        # Check version ordering
        if len(changelog_headers) > 1:
            version_errors = self.check_version_order(patched_file, changelog_headers)

        self.logger.debug(f"Found {len(changelog_headers)} changelog headers")


        for k in content:
            cl = changelog.Changelog(content[k])

            # Check distribution validity
            if not self.check_distribution(cl.distributions):
                self.create_feedback(
                    message=f"Invalid distribution '{cl.distributions}'",
                    rule_id=ErrorCode.CHANGELOG_INVALID_DISTRIBUTION,
                    severity=Severity.ERROR,
                    patched_file=patched_file
                )
                self.logger.error(f"Invalid distribution: '{cl.distributions}'")

            # Check LP bug targeting
            lpbugs = self.lp_helper.extract_lp_bugs(str(cl))
            for lpbug in lpbugs:
                self.logger.info(f"Checking LP Bug: #{lpbug}")
                
                if not self.lp_helper.is_bug_targeted(lpbug, cl.get_package(), cl.distributions):
                    self.create_line_feedback(
                        message=f"Bug LP: #{lpbug} is not targeted at {cl.get_package()} and {cl.distributions}",
                        rule_id=ErrorCode.CHANGELOG_BUG_NOT_TARGETED,
                        severity=Severity.ERROR,
                        patched_file=patched_file,
                        target_line_content=f"LP: #{lpbug}"
                    )
                    self.logger.error(f"Bug {lpbug} not properly targeted")

    def check_distribution(self, distributions):
        """Check if the distribution field in the changelog is valid."""
        return self.lp_helper.is_valid_distribution(distributions)
    
    def check_version_order(self, patched_file, headers: list[DebianChangelogHeader]) -> list[FeedbackItem]:
        """Check that versions are in descending order."""
        
        for idx, (prev, curr) in enumerate(zip(headers, headers[1:])):
            v_prev = Version(prev.version)
            v_curr = Version(curr.version)
            if not (v_prev > v_curr):
                # Use the line number where the problematic version appears
                line_number = getattr(curr, 'line_number', None)
                
                self.create_feedback(
                    message=f"Version order error: '{prev.version}' should be greater than '{curr.version}'",
                    rule_id=ErrorCode.CHANGELOG_VERSION_ORDER,
                    severity=Severity.ERROR,
                    patched_file=patched_file,
                    line_number=line_number
                )
