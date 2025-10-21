from sru_lint.plugins.plugin_base import Plugin, ProcessedFile


class DummyPlugin(Plugin):
    """A dummy plugin for testing purposes."""

    def register_file_patterns(self):
        """Register file patterns this plugin should process."""
        self.add_file_pattern("*.txt")
        self.add_file_pattern("test_*")
        self.add_file_pattern("dummy/*")

    def process_file(self, processed_file: ProcessedFile):
        """Process a single file and generate feedback."""
        # Example: Check for some dummy pattern in the file
        for line in processed_file.source_span.content:
            if line.is_added and "TODO" in line.content:
                self.create_line_feedback(
                    message="TODO comment found in added line",
                    rule_id="DUMMY001",
                    source_span=processed_file.source_span,
                    target_line_content=line.content
                )

            if line.is_added and "FIXME" in line.content:
                self.create_line_feedback(
                    message="FIXME comment found in added line",
                    rule_id="DUMMY002",
                    source_span=processed_file.source_span,
                    target_line_content=line.content
                )

    def process(self, processed_files):
        """Legacy method for backward compatibility."""
        # Clear any existing feedback
        self.feedback.clear()

        # Process each file that matches our patterns
        for processed_file in processed_files:
            if self.matches_file(processed_file.path):
                self.process_file(processed_file)

        return self.feedback