from dataclasses import dataclass
from parse import parse

@dataclass(frozen=True)
class DebianChangelogHeader:
    name: str
    version: str
    series: str
    urgency: str

PATTERN = "{name} ({version}) {series}; urgency={urgency}"

def parse_header(line: str) -> DebianChangelogHeader:
    m = parse(PATTERN, line.strip())
    if not m:
        raise ValueError(f"Not a valid changelog header: {line!r}")
    return DebianChangelogHeader(
        name=m["name"].strip(),
        version=m["version"].strip(),
        series=m["series"].strip(),
        urgency=m["urgency"].strip(),
    )
