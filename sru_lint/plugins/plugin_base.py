from abc import ABC, abstractmethod
import re
from typing import List, Set, Callable
import fnmatch


class Plugin(ABC):
    """Base class for plugins that process patches (parsed by unidiff)."""

    __symbolic_name__: str = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Only fill in if not explicitly provided or empty
        if not getattr(cls, "__symbolic_name__", None):
            cls.__symbolic_name__ = cls._generate_symbolic_name(cls.__name__)

    def __init__(self):
        """Initialize the plugin with its file patterns."""
        self._file_patterns: Set[str] = set()
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

    def add_file_patterns(self, patterns: List[str]):
        """
        Add multiple file patterns to check.
        
        Args:
            patterns: List of file patterns
        """
        self._file_patterns.update(patterns)

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
                return True
        return False

    def process(self, patches):
        """
        Process the given patches and perform plugin-specific actions.
        
        This method iterates through all patches and calls process_file()
        for each file that matches the registered patterns.
        
        Args:
            patches: PatchSet object from unidiff containing all patches
            
        Returns:
            List of FeedbackItem objects from all processed files
        """
        feedback = []
        
        for patched_file in patches:
            filepath = patched_file.path
            
            # Check if this plugin handles this file
            if self.matches_file(filepath):
                file_feedback = self.process_file(patched_file)
                feedback.extend(file_feedback)
        
        return feedback

    @abstractmethod
    def process_file(self, patched_file):
        """
        Process a single file that matches the plugin's registered patterns.
        
        This is the callback method that subclasses must implement to perform
        their specific checks on the file.
        
        Args:
            patched_file: A PatchedFile object from unidiff representing the file
                         with all its hunks and changes
        """
        raise NotImplementedError("Subclasses must implement process_file()")
