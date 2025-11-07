from sru_lint.common.debian.dep3 import check_dep3_compliance
from sru_lint.plugins.plugin_base import Plugin
from sru_lint.common.feedback import FeedbackItem, Severity, SourceSpan
from sru_lint.common.errors import ErrorCode
from sru_lint.common.logging import get_logger


class PatchFormat(Plugin):
    """Checks the compliance of the patches in debian/patches to the DEP-3."""

    def __init__(self):
        super().__init__()
        self.logger = get_logger("plugins.patch-format")

    def register_file_patterns(self):
        """Register that we want to check debian/patches files."""
        self.add_file_pattern("debian/patches/*")

    def process_file(self, processed_file):
        """Process a single patch file for DEP-3 compliance."""
        self.logger.info(f"Processing patch file: {processed_file.path}")

        # Skip the series file
        if processed_file.path.endswith("/series"):
            self.logger.debug(f"Skipping series file: {processed_file.path}")
            return

        # Get the added content from the patch file
        added_lines = processed_file.source_span.content
        if not added_lines:
            self.logger.debug(f"No added lines in {processed_file.path}")
            return

        # Combine the added lines into patch content
        patch_content = "\n".join([line.content for line in added_lines])

        self.logger.info(f"Checking DEP-3 compliance for patch: {processed_file.path}")
        self.check_dep3_format(processed_file, patch_content)

    def check_dep3_format(self, processed_file, patch_content):
        """Check DEP-3 compliance for a patch file."""
        self.logger.debug(f"Checking DEP-3 format of patch: {processed_file.path}")

        try:
            # Check DEP-3 compliance - returns (is_compliant: bool, list[FeedbackItem])
            is_compliant, feedback_items = check_dep3_compliance(patch_content, processed_file.path)

            self.logger.debug(
                f"DEP-3 compliance result for {processed_file.path}: compliant={is_compliant}, issues={len(feedback_items)}"
            )

            # Add all feedback items to our feedback list
            self.feedback.extend(feedback_items)

            self.logger.debug(f"DEP-3 compliance check completed for {processed_file.path}")

        except Exception as e:
            self.logger.error(f"Error checking DEP-3 compliance for {processed_file.path}: {e}")
            # Create feedback for parsing errors using the existing source span
            source_span = SourceSpan(
                path=processed_file.path,
                start_line=1,
                start_col=1,
                end_line=1,
                end_col=1,
                content=processed_file.source_span.content,
                content_with_context=processed_file.source_span.content_with_context,
            )

            feedback = FeedbackItem(
                message=f"Failed to parse patch for DEP-3 compliance: {str(e)}",
                rule_id=ErrorCode.PATCH_DEP3_FORMAT,
                severity=Severity.WARNING,
                span=source_span,
            )

            self.feedback.append(feedback)
