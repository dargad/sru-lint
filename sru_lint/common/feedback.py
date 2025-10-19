from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, List, Dict
import json
import uuid


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class SourceSpan:
    """
    Pinpoints where an issue occurs. Ranges are inclusive of start and exclusive of end.
    Both line/column and byte offsets are stored for robust rendering.
    """
    path: str                               # absolute or repo-relative path to the file
    start_line: int                          # 1-based
    start_col: int                           # 1-based, count of Unicode columns
    end_line: int                            # 1-based
    end_col: int                             # 1-based
    start_offset: int                        # 0-based byte (or char) offset from file start
    end_offset: int                          # 0-based

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class FixIt:
    """
    Optional machine-applicable fix or suggestion.
    If 'replacement' is None, treat as a non-automatic suggestion.
    """
    description: str
    span: Optional[SourceSpan] = None        # where the fix applies (defaults to issue span)
    replacement: Optional[str] = None        # text replacement to apply to span

    def to_dict(self) -> Dict:
        d = asdict(self)
        if self.span:
            d["span"] = self.span.to_dict()
        return d


@dataclass
class FeedbackItem:
    """
    One issue found by a rule.
    """
    message: str                              # human-readable description
    span: SourceSpan                          # where it happened
    rule_id: str                              # stable identifier, e.g., "FMT001"
    severity: Severity = Severity.ERROR
    doc_url: Optional[str] = None             # link to more info (optional)
    hint: Optional[str] = None                # short nudge for quick fixes (optional)
    code_sample: Optional[str] = None         # small extracted snippet to show in UIs
    tags: List[str] = field(default_factory=list)
    fixits: List[FixIt] = field(default_factory=list)
    meta: Dict[str, str] = field(default_factory=dict)  # freeform extras (e.g., parser context)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))  # unique per finding

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "rule_id": self.rule_id,
            "severity": self.severity.value,
            "message": self.message,
            "span": self.span.to_dict(),
            "doc_url": self.doc_url,
            "hint": self.hint,
            "code_sample": self.code_sample,
            "tags": list(self.tags),
            "fixits": [f.to_dict() for f in self.fixits],
            "meta": dict(self.meta),
        }


@dataclass
class FeedbackReport:
    """
    A container for all issues from a single run (possibly across multiple files).
    """
    tool_name: str
    tool_version: str
    items: List[FeedbackItem] = field(default_factory=list)
    summary: Dict[str, int] = field(default_factory=dict)  # you can fill counts per severity, rule, etc.

    def add(self, item: FeedbackItem) -> None:
        self.items.append(item)

    def to_json(self, *, indent: Optional[int] = None) -> str:
        payload = {
            "tool_name": self.tool_name,
            "tool_version": self.tool_version,
            "summary": self.summary,
            "items": [i.to_dict() for i in self.items],
        }
        return json.dumps(payload, ensure_ascii=False, indent=indent)

def create_source_span(patched_file, ) -> SourceSpan:
    """
    Create a SourceSpan for the entire patched file.
    """
    # Calculate the total number of lines and columns
    total_lines = 0
    total_cols = 0
    for hunk in patched_file:
        for line in hunk:
            total_lines += 1
            total_cols = max(total_cols, len(line.value))

    return SourceSpan(
        path=patched_file.path,
        start_line=1,
        start_col=1,
        end_line=total_lines + 1,
        end_col=total_cols + 1,
        start_offset=0,
        end_offset=sum(len(line.value) + 1 for hunk in patched_file for line in hunk)  # +1 for newlines
    )

from dataclasses import dataclass
from typing import List, Optional
from enum import Enum


class Severity(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class SourceLine:
    """Represents a single line in the source with context information."""
    content: str
    line_number: Optional[int]  # Target line number from patch
    is_added: bool = False
    is_removed: bool = False
    is_context: bool = False


@dataclass
class SourceSpan:
    """Represents a span in source code with content and location information."""
    path: str
    start_line: int
    start_col: int
    end_line: int
    end_col: int
    start_offset: int = 0
    end_offset: int = 0
    
    # Content information from patch
    content: List[SourceLine] = None  # Only added lines
    content_with_context: List[SourceLine] = None  # Added lines + context
    
    def __post_init__(self):
        """Initialize content lists if not provided."""
        if self.content is None:
            self.content = []
        if self.content_with_context is None:
            self.content_with_context = []
    
    @property
    def lines_added(self) -> List[SourceLine]:
        """Get only the added lines from content_with_context."""
        return [line for line in self.content_with_context if line.is_added]
    
    @property
    def lines_with_context(self) -> List[SourceLine]:
        """Get only the context lines from content_with_context."""
        return [line for line in self.content_with_context if line.is_added or line.is_context]
    
    def get_line_content(self, line_number: int) -> Optional[str]:
        """Get content of a specific line number."""
        for line in self.content_with_context:
            if line.line_number == line_number:
                return line.content
        return None


@dataclass
class FeedbackItem:
    """Represents a single piece of feedback from a plugin."""
    message: str
    span: SourceSpan
    rule_id: str
    severity: Severity = Severity.ERROR
    
    def __str__(self) -> str:
        """String representation of the feedback item."""
        location = f"{self.span.path}:{self.span.start_line}:{self.span.start_col}"
        return f"{location}: {self.severity.value}: [{self.rule_id}] {self.message}"


def create_source_span_from_patch(patched_file, include_context: bool = True) -> SourceSpan:
    """
    Create a SourceSpan from a unidiff PatchedFile.
    
    Args:
        patched_file: PatchedFile object from unidiff
        include_context: Whether to include context lines
        
    Returns:
        SourceSpan with content extracted from the patch
    """
    content = []  # Only added lines
    content_with_context = []  # Added lines + context
    
    # Extract lines from all hunks
    for hunk in patched_file:
        for line in hunk:
            source_line = SourceLine(
                content=line.value.rstrip('\n'),
                line_number=line.target_line_no,
                is_added=line.is_added,
                is_removed=line.is_removed,
                is_context=line.is_context
            )
            
            # Add to content if it's an added line
            if line.is_added:
                content.append(source_line)
            
            # Add to content_with_context if it's added or (context and we want context)
            if line.is_added or (include_context and line.is_context):
                content_with_context.append(source_line)
    
    # Determine start and end lines
    start_line = 1
    end_line = 1
    if content_with_context:
        line_numbers = [line.line_number for line in content_with_context if line.line_number]
        if line_numbers:
            start_line = min(line_numbers)
            end_line = max(line_numbers)
    
    return SourceSpan(
        path=patched_file.path,
        start_line=start_line,
        start_col=1,
        end_line=end_line,
        end_col=1,
        content=content,
        content_with_context=content_with_context
    )