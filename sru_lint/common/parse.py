import re

DEBIAN_CHANGELOG = "debian/changelog"
DEBIAN_PATCHES = "debian/patches/"

REVIEW_STATES = {"New", "Unapproved"}

def parse_distributions_field(value: str) -> list[str]:
    """
    Debian changelog 'distributions' can contain multiple suites separated by
    whitespace and sometimes commas. Examples: 'jammy', 'jammy-proposed',
    'jammy jammy-proposed', 'UNRELEASED'.
    """
    if not value:
        return []
    # normalize commas to spaces, collapse whitespace
    norm = re.sub(r"[,\s]+", " ", value).strip()
    tokens = norm.split()
    # Drop non-upload suites you don't want to query (optional)
    return [t for t in tokens if t.lower() != "unreleased"]

def find_offset(lines, search_text: str) -> tuple[int, int]:
    """
    Find the line offset of a given text in a source span.
    
    Args:
        source_span: The source span to search within
        search_text: The text to find
    Returns:
        A tuple containing the line number and column offset of the found text, or (-1, -1) if not found.
    """
    for line_number, line in enumerate(lines):
        column_offset = line.content.find(search_text)
        if column_offset != -1:
            return (line_number, column_offset)
    return (-1, -1)