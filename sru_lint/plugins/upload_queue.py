import re
from os.path import expanduser
from debian import changelog

from sru_lint.common.doc_links import DocLinks
from sru_lint.common.launchpad_helper import LaunchpadHelper
from sru_lint.common.patches import combine_added_lines, make_end_filename_matcher, match_hunks
from sru_lint.common.parse import REVIEW_STATES, UNRELEASED_DISTRIBUTION, parse_distributions_field
from sru_lint.plugins.plugin_base import Plugin
from sru_lint.common.feedback import Severity, SourceSpan, SourceLine
from sru_lint.common.errors import ErrorCode
from sru_lint.common.logging import get_logger


class UploadQueue(Plugin):
    """Checks if the version in debian/changelog is already in the upload queue for review."""

    def __init__(self):
        super().__init__()
        self.logger = get_logger("plugins.upload-queue")

    def register_file_patterns(self):
        """Register that we want to check debian/changelog files."""
        self.add_file_pattern("debian/changelog")

    def process_file(self, processed_file):
        """Process a debian/changelog file to check upload queue status."""
        self.logger.info(f"Processing changelog file: {processed_file.path}")

        # Get the added content from the changelog file
        added_lines = processed_file.source_span.content
        if not added_lines:
            self.logger.debug(f"No added lines in {processed_file.path}")
            return

        # Combine the added lines into changelog content
        changelog_content = "\n".join([line.content for line in added_lines])

        self.logger.debug(f"Checking upload queue for changelog: {processed_file.path}")
        self.check_changelog_upload_queue(processed_file, changelog_content)

    def check_changelog_upload_queue(self, processed_file, changelog_content):
        """Check if versions in the changelog are already in the upload queue."""
        try:
            # Parse the changelog
            cl = changelog.Changelog(changelog_content)

            # Check each version in the changelog
            for entry in cl:
                package_name = entry.package
                version_to_check = entry.version
                suites = parse_distributions_field(str(entry.distributions))

                self.logger.debug(
                    f"Checking upload queue for {package_name} {version_to_check} in {suites}"
                )
                self.check_upload_queue(processed_file, package_name, suites, str(version_to_check))

        except Exception as e:
            self.logger.error(f"Error parsing changelog {processed_file.path}: {e}")
            # Create feedback for parsing errors
            source_span = SourceSpan(
                path=processed_file.path,
                start_line=1,
                start_col=1,
                end_line=1,
                end_col=1,
                content=processed_file.source_span.content,
                content_with_context=processed_file.source_span.content_with_context,
            )

            self.create_feedback(
                message=f"Failed to parse changelog for upload queue check: {str(e)}",
                rule_id=ErrorCode.UPLOAD_QUEUE_PARSE_ERROR,
                severity=Severity.WARNING,
                source_span=source_span,
                doc_url=DocLinks.CHANGELOG_FORMAT,
            )

    def check_upload_queue(
        self, processed_file, package_name: str, suites: list[str], version_to_check: str
    ):
        """Check if a specific package version is in the upload queue for given suites."""
        self.logger.debug(
            f"Checking upload queue for {package_name} {version_to_check} in suites: {suites}"
        )

        try:
            # Check if we have a Launchpad helper available
            if not hasattr(self, "lp_helper") or not self.lp_helper:
                self.logger.warning("Launchpad helper not available for upload queue check")
                return

            for suite in suites:
                self.logger.debug(f"Checking suite: {suite}")

                # Extract base distribution name (e.g., 'jammy-proposed' -> 'jammy')
                base = suite.split("-", 1)[0]

                if base == UNRELEASED_DISTRIBUTION:
                    self.create_line_feedback(
                        message=f"Cannot check upload queue for UNRELEASED distribution for package '{package_name}' version '{version_to_check}'",
                        rule_id=ErrorCode.UPLOAD_QUEUE_UNRELEASED,
                        severity=Severity.WARNING,
                        source_span=processed_file.source_span,
                        target_line_content=base,
                        doc_url=DocLinks.LIST_OF_UBUNTU_RELEASES,
                    )
                    continue

                try:
                    # Get the distribution series
                    ds = self.lp_helper.ubuntu.getSeries(name_or_version=base)

                    # Get package uploads for this series
                    uploads = ds.getPackageUploads(
                        archive=self.lp_helper.archive,
                        name=package_name,
                        exact_match=True,
                    )

                    # Filter uploads that are waiting for review
                    waiting = [u for u in uploads if getattr(u, "status", None) in REVIEW_STATES]

                    if waiting:
                        # Found uploads in review queue
                        for upload in waiting:
                            self.logger.info(
                                f"Found {package_name} in upload queue: {ds.name}/{upload.pocket}/{upload.status}"
                            )

                            self.create_line_feedback(
                                message=f"Package '{package_name}' version '{version_to_check}' is already in upload queue for {ds.name}/{upload.pocket} with status '{upload.status}'",
                                rule_id=ErrorCode.UPLOAD_QUEUE_ALREADY_QUEUED,
                                severity=Severity.WARNING,  # Could be ERROR depending on policy
                                source_span=processed_file.source_span,
                                target_line_content=version_to_check,
                                doc_url=LaunchpadHelper.get_upload_queue_url(package_name, suite),
                            )
                    else:
                        self.logger.info(
                            f"✅ No review-queue uploads for {package_name} in {ds.name} (good for new uploads)"
                        )

                except Exception as suite_error:
                    self.logger.error(
                        f"Error checking suite {suite} for {package_name}: {suite_error}"
                    )

                    # Create feedback for suite-specific errors
                    source_span = self.find_version_line_span(processed_file, version_to_check)

                    self.create_feedback(
                        message=f"Failed to check upload queue for {package_name} in suite {suite}: {str(suite_error)}",
                        rule_id=ErrorCode.UPLOAD_QUEUE_API_ERROR,
                        severity=Severity.WARNING,
                        source_span=source_span,
                        doc_url=LaunchpadHelper.get_upload_queue_url(package_name, suite),
                    )

        except Exception as e:
            self.logger.error(
                f"Error checking upload queue for {package_name} {version_to_check}: {e}"
            )

            # Create feedback for general API errors
            source_span = self.find_version_line_span(processed_file, version_to_check)

            self.create_feedback(
                message=f"Failed to check upload queue for {package_name} {version_to_check}: {str(e)}",
                rule_id=ErrorCode.UPLOAD_QUEUE_API_ERROR,
                severity=Severity.WARNING,
                source_span=source_span,
            )

    def find_version_line_span(self, processed_file, version_to_check):
        """Find the source span for a specific version in the changelog."""
        # Look for the version string in the added lines
        self.logger.debug(
            f"Finding line span for version {version_to_check} in {processed_file.path}"
        )
        for line in processed_file.source_span.content:
            if version_to_check in line.content:
                # Create a source span for this line
                source_line = SourceLine(
                    content=line.content, line_number=line.line_number, is_added=line.is_added
                )

                start_col = line.content.find(version_to_check) + 1  # +1 for 1-based index
                self.logger.debug(
                    f"Found version {version_to_check} at line {line.line_number}, column {start_col}"
                )
                return SourceSpan(
                    path=processed_file.path,
                    start_line=line.line_number,
                    start_col=start_col,
                    end_line=line.line_number,
                    end_col=len(line.content),
                    content=[source_line],
                    content_with_context=[source_line],
                )

        print(f"Fallback to first line for version {version_to_check} in {processed_file.path}")
        # Fallback to first line if version not found in specific line
        return SourceSpan(
            path=processed_file.path,
            start_line=1,
            start_col=1,
            end_line=1,
            end_col=1,
            content=processed_file.source_span.content,
            content_with_context=processed_file.source_span.content_with_context,
        )
