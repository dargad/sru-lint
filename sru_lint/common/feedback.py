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