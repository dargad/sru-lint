import re


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