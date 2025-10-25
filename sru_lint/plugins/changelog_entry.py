from sru_lint.common.debian.changelog import DebianChangelogHeader, parse_header
from sru_lint.common.doc_links import DocLinks
from sru_lint.common.errors import ErrorCode
from sru_lint.common.feedback import FeedbackItem, Severity, SourceSpan, create_source_span
from sru_lint.common.parse import find_offset
from sru_lint.common.ui.snippet import render_snippet
from sru_lint.plugins.plugin_base import Plugin
from sru_lint.common.patches import combine_added_lines

from debian import changelog
from debian.debian_support import Version


class ChangelogEntry(Plugin):
    """Checks the changelog entry."""

    def register_file_patterns(self):
        """Register that we want to check debian/changelog files."""
        self.add_file_pattern("debian/changelog")

    def process_file(self, processed_file) -> None:
        """
        Process a changelog file using the decoupled source span structure.
        """
        self.logger.info("Processing changelog entry")
        
        source_span = processed_file.source_span

        self.check_changelog_headers(processed_file, source_span)

        # Get content from the source span (only added lines)
        added_content = "\n".join(line.content for line in source_span.lines_added)
        
        # Parse changelog from added content
        if added_content.strip():
            try:
                cl = changelog.Changelog(added_content)
                
                # Check distribution validity
                if not self.check_distribution(cl.distributions):
                    self.create_line_feedback(
                        message=f"Invalid distribution '{cl.distributions}'",
                        rule_id="CHANGELOG001",
                        severity=Severity.ERROR,
                        source_span=source_span,
                        target_line_content=str(cl.distributions),
                        doc_url=DocLinks.LIST_OF_UBUNTU_RELEASES
                    )
                
                # Check LP bugs
                lpbugs = self.lp_helper.extract_lp_bugs(str(cl))
                for lpbug in lpbugs:
                    if not self.lp_helper.is_bug_targeted(lpbug, cl.get_package(), cl.distributions):
                        self.create_line_feedback(
                            message=f"Bug LP: #{lpbug} is not targeted at {cl.get_package()} and {cl.distributions}",
                            rule_id="CHANGELOG002",
                            severity=Severity.WARNING,
                            source_span=source_span,
                            target_line_content=f"LP: #{lpbug}",
                        )
                        
            except Exception as e:
                self.logger.error(f"Failed to parse changelog: {e}")

    def check_changelog_headers(self, processed_file, source_span):
        headers = []
        for line in source_span.lines_with_context:
            try:
                header = parse_header(line.content)
                if header:
                    headers.append(header)
            except Exception as e:
                continue
        if len(headers) > 1:
            self.check_version_order(processed_file, headers)

    def check_distribution(self, distributions):
        """Check if the distribution field in the changelog is valid."""
        return self.lp_helper.is_valid_distribution(distributions)
    
    def check_version_order(self, processed_file, headers: list[DebianChangelogHeader]) -> list[FeedbackItem]:
        """Check that versions are in descending order."""
        
        self.logger.debug("Checking changelog version order")
        errors_found = False

        for idx, (prev, curr) in enumerate(zip(headers, headers[1:])):
            v_prev = Version(prev.version)
            v_curr = Version(curr.version)
            if not (v_prev > v_curr):
                # Use the line number where the problematic version appears
                line_number = getattr(curr, 'line_number', None)
                self.create_line_feedback(
                    message=f"Version order error: '{prev.version}' should be greater than '{curr.version}'",
                    rule_id=ErrorCode.CHANGELOG_VERSION_ORDER,
                    severity=Severity.ERROR,
                    source_span=processed_file.source_span,
                    target_line_content=prev.version,
                    doc_url=DocLinks.VERSION_STRING_FORMAT
                )
                errors_found = True

        if not errors_found:
            self.logger.info("Changelog versions are in correct order")

        
