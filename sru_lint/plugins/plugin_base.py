from abc import ABC, abstractmethod
import re
from typing import List, Set, Callable, Optional
import fnmatch

from sru_lint.common.feedback import FeedbackItem, Severity, SourceSpan
from sru_lint.common.logging import get_logger


class Plugin(ABC):
    """Base class for plugins that process patches (parsed by unidiff)."""

    __symbolic_name__: str = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Only fill in if not explicitly provided or empty
        if not getattr(cls, "__symbolic_name__", None):
            cls.__symbolic_name__ = cls._generate_symbolic_name(cls.__name__)

    def __init__(self):
        """Initialize the plugin with its file patterns and Launchpad helper."""
        from sru_lint.common.launchpad_helper import get_launchpad_helper
        
        self._file_patterns: Set[str] = set()
        self.feedback: List[FeedbackItem] = []  # List to collect feedback items
        self.lp_helper = get_launchpad_helper()
        self.logger = get_logger(f"plugins.{self.__symbolic_name__}")
        self.register_file_patterns()

    @staticmethod
    def _generate_symbolic_name(name: str) -> str:
        # strip leading underscores, split Camel/PascalCase (keeps acronyms), include digits
        name = name.lstrip("_")
        parts = re.findall(r"[A-Z]+(?=[A-Z][a-z]|$)|[A-Z]?[a-z]+|\d+", name)
        return "-".join(p.lower() for p in parts)

    def register_file_patterns(self):
        """
        Register file patterns that this plugin wants to check.
        
        Subclasses should override this method to register their file patterns
        using add_file_pattern() or add_file_patterns().
        
        Example:
            def register_file_patterns(self):
                self.add_file_pattern("debian/changelog")
                self.add_file_patterns(["*.py", "*.pyx"])
        """
        pass

    def add_file_pattern(self, pattern: str):
        """
        Add a single file pattern to check.
        
        Args:
            pattern: A file pattern (supports wildcards like *, ?, [seq])
                    Examples: "debian/changelog", "*.py", "src/**/*.c"
        """
        self._file_patterns.add(pattern)
        self.logger.debug(f"Added file pattern: {pattern}")

    def add_file_patterns(self, patterns: List[str]):
        """
        Add multiple file patterns to check.
        
        Args:
            patterns: List of file patterns
        """
        self._file_patterns.update(patterns)
        self.logger.debug(f"Added file patterns: {patterns}")

    def matches_file(self, filepath: str) -> bool:
        """
        Check if a file path matches any of the registered patterns.
        
        Args:
            filepath: The file path to check
            
        Returns:
            True if the file matches any registered pattern, False otherwise
        """
        for pattern in self._file_patterns:
            if fnmatch.fnmatch(filepath, pattern) or fnmatch.fnmatch(filepath, f"*/{pattern}"):
                self.logger.debug(f"File {filepath} matches pattern {pattern}")
                return True
        self.logger.debug(f"File {filepath} does not match any patterns: {self._file_patterns}")
        return False

    def process(self, patches) -> List[FeedbackItem]:
        """
        Process the given patches and perform plugin-specific actions.
        
        This method iterates through all patches and calls process_file()
        for each file that matches the registered patterns.
        
        Args:
            patches: PatchSet object from unidiff containing all patches
            
        Returns:
            List of FeedbackItem objects from all processed files
        """
        # Clear previous feedback
        self.feedback.clear()
        self.logger.info(f"Starting processing with plugin {self.__symbolic_name__}")
        
        processed_files = 0
        for patched_file in patches:
            filepath = patched_file.path
            
            # Check if this plugin handles this file
            if self.matches_file(filepath):
                self.logger.info(f"Processing file: {filepath}")
                self.process_file(patched_file)
                processed_files += 1
        
        self.logger.info(f"Processed {processed_files} files, found {len(self.feedback)} issues")
        return self.feedback

    @abstractmethod
    def process_file(self, patched_file) -> None:
        """
        Process a single file that matches the plugin's registered patterns.
        
        This is the callback method that subclasses must implement to perform
        their specific checks on the file. Implementations should add any
        discovered issues to self.feedback using add_feedback() or the
        create_feedback() helper methods.
        
        Args:
            patched_file: A PatchedFile object from unidiff representing the file
                         with all its hunks and changes
        """
        raise NotImplementedError("Subclasses must implement process_file()")

    def add_feedback(self, feedback_item: FeedbackItem) -> None:
        """
        Add a feedback item to the collection.
        
        Args:
            feedback_item: The FeedbackItem to add
        """
        self.feedback.append(feedback_item)
        self.logger.debug(f"Added feedback: {feedback_item.severity.value} - {feedback_item.message}")

    def create_feedback(
        self, 
        message: str, 
        rule_id: str, 
        severity: Severity = Severity.ERROR,
        patched_file = None,
        line_number: Optional[int] = None,
        col_start: int = 1,
        col_end: Optional[int] = None
    ) -> FeedbackItem:
        """
        Create a FeedbackItem with proper span information.
        
        Args:
            message: The feedback message
            rule_id: The rule identifier
            severity: The severity level
            patched_file: The PatchedFile object (optional)
            line_number: Specific line number (optional)
            col_start: Column start position
            col_end: Column end position (optional)
            
        Returns:
            The created FeedbackItem (also automatically added to self.feedback)
        """
        if patched_file:
            path = patched_file.path
            # Try to get reasonable line numbers from the patch
            if line_number is None and patched_file:
                # Use the first modified line as default
                for hunk in patched_file:
                    for line in hunk:
                        if line.is_added or line.is_removed:
                            line_number = line.target_line_no or line.source_line_no or 1
                            break
                    if line_number:
                        break
        else:
            path = "unknown"
        
        line_number = line_number or 1
        col_end = col_end or col_start
        
        feedback_item = FeedbackItem(
            message=message,
            span=SourceSpan(
                path=path,
                start_line=line_number,
                start_col=col_start,
                end_line=line_number,
                end_col=col_end,
                start_offset=0,  # Could be calculated if needed
                end_offset=0
            ),
            rule_id=rule_id,
            severity=severity
        )
        
        # Log the feedback creation based on severity
        if severity == Severity.ERROR:
            self.logger.error(f"[{rule_id}] {message} at {path}:{line_number}")
        elif severity == Severity.WARNING:
            self.logger.warning(f"[{rule_id}] {message} at {path}:{line_number}")
        else:
            self.logger.info(f"[{rule_id}] {message} at {path}:{line_number}")
        
        self.add_feedback(feedback_item)
        return feedback_item

    def create_line_feedback(
        self,
        message: str,
        rule_id: str,
        patched_file,
        target_line_content: str,
        severity: Severity = Severity.ERROR
    ) -> FeedbackItem:
        """
        Create feedback for a specific line content found in the patch.
        
        This method searches through the patch to find the exact line number
        where the content appears.
        
        Args:
            message: The feedback message
            rule_id: The rule identifier
            patched_file: The PatchedFile object
            target_line_content: The line content to search for
            severity: The severity level
            
        Returns:
            The created FeedbackItem (also automatically added to self.feedback)
        """
        line_number = 1
        col_start = 1
        col_end = len(target_line_content)
        
        self.logger.debug(f"Searching for line content: '{target_line_content}' in {patched_file.path}")
        
        # Search for the line in the patch
        found = False
        for hunk in patched_file:
            for line in hunk:
                if target_line_content in line.value:
                    line_number = line.target_line_no or line.source_line_no or 1
                    # Find column position of the content
                    col_start = line.value.find(target_line_content) + 1
                    col_end = col_start + len(target_line_content)
                    found = True
                    self.logger.debug(f"Found target content at line {line_number}, col {col_start}-{col_end}")
                    break
            if found:
                break
        
        if not found:
            self.logger.warning(f"Target line content '{target_line_content}' not found in patch, using defaults")
        
        feedback_item = FeedbackItem(
            message=message,
            span=SourceSpan(
                path=patched_file.path,
                start_line=line_number,
                start_col=col_start,
                end_line=line_number,
                end_col=col_end,
                start_offset=0,
                end_offset=0
            ),
            rule_id=rule_id,
            severity=severity
        )
        
        # Log the feedback creation based on severity
        if severity == Severity.ERROR:
            self.logger.error(f"[{rule_id}] {message} at {patched_file.path}:{line_number}")
        elif severity == Severity.WARNING:
            self.logger.warning(f"[{rule_id}] {message} at {patched_file.path}:{line_number}")
        else:
            self.logger.info(f"[{rule_id}] {message} at {patched_file.path}:{line_number}")
        
        self.add_feedback(feedback_item)
        return feedback_item
