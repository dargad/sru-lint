from sru_lint.common.doc_links import DocLinks
from sru_lint.common.errors import ErrorCode
from sru_lint.common.feedback import Severity
from sru_lint.common.launchpad_helper import LaunchpadHelper
from sru_lint.common.logging import get_logger
from sru_lint.plugins.plugin_base import Plugin, ProcessedFile


class SRUTemplate(Plugin):
    """Checks whether the public bugs mentioned have SRU template."""

    def __init__(self):
        super().__init__()
        self.logger = get_logger("plugins.sru-template")

    def register_file_patterns(self):
        """Register file patterns this plugin should process."""
        self.add_file_pattern("debian/changelog")

    def process_file(self, processed_file: ProcessedFile):
        """Process a single file and generate feedback."""

        self.logger.info(f"Processing file: {processed_file.path}")

        content = "\n".join(line.content for line in processed_file.source_span.lines_added)

        lpbugs = LaunchpadHelper.extract_lp_bugs(content)

        if len(lpbugs) == 0:
            self.logger.debug(f"No Launchpad bugs found in {processed_file.path}")
            self.create_feedback(
                message=f"No Launchpad bugs referenced in {processed_file.path}",
                rule_id=ErrorCode.SRU_NO_BUGS_REFERENCED,
                source_span=processed_file.source_span,
                severity=Severity.INFO,
                doc_url=DocLinks.PATCHING_MAKE_CHANGES
            )
        else:
            self.logger.debug(f"Found Launchpad bugs in {processed_file.path}: {lpbugs}")

            for bug in lpbugs:
                try:
                    self.logger.debug(f"Checking SRU template for bug: {bug}")
                    if not self.lp_helper.has_sru_template(bug):
                        self.logger.warning(f"SRU template not found for bug LP: #{bug}")
                        self.create_line_feedback(
                            message=f"SRU template not found for bug LP: #{bug}",
                            rule_id=ErrorCode.SRU_TEMPLATE_MISSING,
                            source_span=processed_file.source_span,
                            target_line_content=f"LP: #{bug}",
                            doc_url=DocLinks.SRU_TEMPLATE_FORMAT
                        )
                except Exception as e:
                    self.logger.error(f"Error checking SRU template for bug LP: #{bug}: {e}")
                    self.create_line_feedback(
                        message=f"Error checking SRU template for bug LP: #{bug}: {str(e)}",
                        rule_id=ErrorCode.SRU_LP_API_ERROR,
                        source_span=processed_file.source_span,
                        target_line_content=f"LP: #{bug}",
                        severity=Severity.WARNING
                    )