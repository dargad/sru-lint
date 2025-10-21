from sru_lint.common.errors import ErrorCode
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

        self.logger.debug(f"Processing file: {processed_file.source_span}")

        content = "\n".join(line.content for line in processed_file.source_span.lines_added)

        lpbugs = self.lp_helper.extract_lp_bugs(content)
        self.logger.debug(f"Found LP bugs: {lpbugs}")

        for bug in lpbugs:
            if not self.lp_helper.has_sru_template(bug):
                self.create_line_feedback(
                    message="SRU template not found for bug",
                    rule_id=ErrorCode.SRU_TEMPLATE_MISSING,
                    source_span=processed_file.source_span,
                    target_line_content=f"LP: #{bug}"
                )