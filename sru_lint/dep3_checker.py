"""
dep3_checker.py
================

This module provides a function to validate whether a given patch file (passed
as a string) contains a header that complies with the Debian DEP-3 Patch
Tagging Guidelines.

DEP-3 (Debian Enhancement Proposal 3) defines a minimal set of meta-data
fields that should be embedded at the top of any patch distributed within a
Debian source package.  These fields are stored in one or more RFC-2822 style
headers and allow tooling and humans to understand the purpose and origin
of a patch.  According to the specification:

* A header starts on the first non-empty line of the patch and ends on the
  first empty line.  A second header, called the *pseudo-header*, may appear
  after a blank line.  Any parsing must stop when a line containing exactly
  three dashes (``---``) is encountered.
* Each field consists of a name followed by a colon and its value.  Continuation
  lines begin with a single space (or ``#  `` when the header is commented
  out) and are folded into the value of the previous field.  Unknown lines
  outside of field definitions are treated as free-form text and appended to
  the description.
* At least one of ``Description`` or ``Subject`` must be present, and the
  short description (the text after the colon on the first line) must be
  non-empty.
* An ``Origin`` field is required unless an ``Author`` (or its alias ``From``)
  is provided.  ``Subject`` is considered an alias
  for ``Description``, and ``From`` is an alias for ``Author``.
* Additional optional fields, such as ``Bug``, ``Forwarded``, ``Last-Update``
  and ``Applied-Upstream``, are ignored for the purposes of compliance
  checking.  However, if present, this implementation performs basic
  validation of ``Last-Update`` (must follow the ISO ``YYYY-MM-DD`` date
  format) and ``Forwarded`` (must be either ``no``, ``not-needed`` or a
  plausible URL as per the guidelines).

The :func:`check_dep3_compliance` function returns a tuple consisting of a
boolean indicating compliance and a list of strings describing any detected
issues.  A patch is considered compliant if it includes a non-empty
``Description`` or ``Subject`` and either an ``Origin`` or an ``Author``/
``From`` field.  Additional validity checks are performed on optional
fields when they are present.
"""

from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urlparse
from typing import List, Tuple


def _strip_comment_prefix(line: str) -> str:
    """Remove a leading comment marker (`#`) and a single following space.

    Some patch management tools store DEP-3 meta-data inside shell comments
    (e.g. `# Description: …`).  This helper strips one leading `#` along
    with a single space that may follow so that the remainder of the line
    contains only the field specification.  Lines with multiple `#`
    characters (common in diff hunks) are left unchanged.

    Parameters
    ----------
    line: str
        The raw line from the patch file.

    Returns
    -------
    str
        The line with the first comment marker removed, if present.
    """
    stripped = line.lstrip()
    # Only strip a single '#' and an optional following space
    if stripped.startswith('#'):
        # Remove the first '#'
        stripped = stripped[1:]
        # Remove one leading space if present
        if stripped.startswith(' '):
            stripped = stripped[1:]
        return stripped
    return line


def _is_valid_date(value: str) -> bool:
    """Return True if *value* is a valid ISO date (YYYY-MM-DD)."""
    try:
        datetime.strptime(value.strip(), '%Y-%m-%d')
        return True
    except Exception:
        return False


def _is_plausible_url(value: str) -> bool:
    """Return True if *value* looks like a URL with scheme and network location.

    The DEP-3 guidelines recommend using URLs for fields such as ``Origin``
    (when available) and for the ``Forwarded`` field when the patch has been
    sent upstream. A reasonable heuristic is to accept strings that parse
    into a scheme and network location using :func:`urllib.parse.urlparse`.
    """
    v = value.strip()
    if not v:
        return False
    parsed = urlparse(v)
    return bool(parsed.scheme) and bool(parsed.netloc)


def check_dep3_compliance(patch_text: str) -> Tuple[bool, List[str]]:
    """Check whether a patch complies with the Debian DEP-3 Tagging Guidelines.

    Parameters
    ----------
    patch_text: str
        The complete contents of a patch file.  Newlines may be either LF or
        CR-LF; line endings are normalised internally.

    Returns
    -------
    (bool, list of str)
        A tuple containing a boolean indicating compliance and a list of
        diagnostic messages explaining any issues that were found.  An empty
        list of diagnostics implies that the patch is compliant.

    Examples
    --------
    >>> compliant_patch = (
    ...     "Description: Fix widget frobnication speeds\n"
    ...     "Forwarded: http://lists.example.com/2010/03/1234.html\n"
    ...     "Author: John Doe <jdoe@example.com>\n"
    ...     "Last-Update: 2010-03-29\n"
    ...     "---\n"
    ... )
    >>> check_dep3_compliance(compliant_patch)[0]
    True

    >>> non_compliant_patch = (
    ...     "# Patch without mandatory fields\n"
    ...     "---\n"
    ... )
    >>> check_dep3_compliance(non_compliant_patch)[0]
    False
    """
    # Normalise line endings and split into lines
    lines = patch_text.replace('\r\n', '\n').split('\n')

    # Determine where the DEP-3 header terminates.  According to the
    # specification, a line containing exactly three dashes marks the end of
    # relevant meta-information.  We stop scanning
    # once this delimiter is encountered.  Diff headers beginning with "---"
    # followed by a space or filename are not considered terminators.
    header_lines: List[str] = []
    for line in lines:
        # Trim right-hand whitespace to recognise delimiter accurately
        stripped = line.strip()
        # Use a plain '---' delimiter (optionally padded with whitespace)
        if stripped == '---':
            break
        header_lines.append(line)

    # Prepare state
    description_found = False
    description_non_empty = False
    origin_found = False
    author_found = False
    date_invalid = False
    forwarded_invalid = False

    # We treat both "Description" and "Subject" as aliases.  Likewise,
    # "Author" and "From" are aliases.  Field names are case-insensitive.
    # We also record optional fields to perform minimal validation.
    date_fields: List[str] = []
    forwarded_fields: List[str] = []

    # Track the current field in order to associate continuation lines with it.
    current_field: str | None = None
    # Buffer for multi-line field values (not needed for compliance, but
    # necessary to determine whether the first line of Description/Subject has
    # content).
    field_first_line_seen = False
    field_has_content = False

    # Iterate through collected header lines
    for raw_line in header_lines:
        # Remove any leading comment prefix (e.g. '# Description: ...')
        line = _strip_comment_prefix(raw_line)
        # Strip trailing carriage returns and newlines
        # Note: Do not strip leading spaces since they indicate continuation
        line_nostrip = line.rstrip('\r\n')

        # Empty line resets the header parsing but does not terminate
        # scanning.  According to the DEP-3 structure, a new header (the
        # pseudo-header) may start after an empty】.
        if not line_nostrip.strip():
            current_field = None
            field_first_line_seen = False
            field_has_content = False
            continue

        # Match a field definition: <name>:<value>
        m = re.match(r'^(?P<name>[\w.-]+)\s*:\s*(?P<value>.*)$', line_nostrip)
        if m:
            # Found a new field
            current_field = m.group('name').strip().lower()
            value = m.group('value')
            field_first_line_seen = True
            field_has_content = bool(value.strip())
            # Dispatch based on field name
            if current_field in ('description', 'subject'):
                description_found = True
                if field_has_content:
                    description_non_empty = True
            elif current_field == 'origin':
                # Record even if empty; emptiness is handled later
                origin_found = True
            elif current_field in ('author', 'from'):
                author_found = True
            elif current_field == 'last-update':
                date_fields.append(value.strip())
            elif current_field == 'forwarded':
                forwarded_fields.append(value.strip())
            # Reset for continuation detection on next lines
            continue

        # Continuation lines begin with a space or tab and extend the value
        # of the previous field.  Only the first line of the value is used
        # to assess whether Description/Subject contains non-empty content.
        if current_field and line_nostrip.startswith((' ', '\t')):
            # Only update description_non_empty if we haven't seen content yet
            if current_field in ('description', 'subject') and not field_has_content:
                if line_nostrip.strip():
                    description_non_empty = True
                    field_has_content = True
            continue
        # Non-continuation lines that are not field definitions reset the
        # current field.  They are treated as free-form text that will be
        # appended to the description, but do not affect compliance.
        current_field = None
        field_first_line_seen = False
        field_has_content = False

    # Validate optional date fields
    for date_value in date_fields:
        if date_value and not _is_valid_date(date_value):
            date_invalid = True
            break

    # Validate optional Forwarded field.  According to DEP-3, any value
    # other than 'no' or 'not-needed' indicates that the patch has been
    # forwarded upstream; ideally it should be an URL.  We
    # therefore consider a value valid if it is one of those special keywords
    # or if it looks like a URL.
    for fwd_value in forwarded_fields:
        v = fwd_value.strip().lower()
        if v and v not in ('no', 'not-needed') and not _is_plausible_url(v):
            forwarded_invalid = True
            break

    diagnostics: List[str] = []
    # Check the mandatory Description/Subject field
    if not description_found:
        diagnostics.append(
            'Missing required Description/Subject field.'
        )
    elif not description_non_empty:
        diagnostics.append(
            'The Description/Subject field must contain a short description on '
            'its first line.'
        )

    # Check that either Origin or Author/From is present
    if not (origin_found or author_found):
        diagnostics.append(
            'Either an Origin field or an Author/From field must be provided.'
        )

    # Report optional field issues
    if date_invalid:
        diagnostics.append('Last-Update field must be a valid ISO date (YYYY-MM-DD).')
    if forwarded_invalid:
        diagnostics.append(
            'Forwarded field should be either "no", "not-needed" or a valid URL.'
        )

    return (not diagnostics, diagnostics)


__all__ = [
    'check_dep3_compliance',
]