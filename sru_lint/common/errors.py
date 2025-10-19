from enum import Enum

class ErrorCode(Enum):
    """Enumeration of error codes used in the SRU Lint tool."""

    CHANGELOG_INVALID_DISTRIBUTION = "CHANGELOG001"
    CHANGELOG_BUG_NOT_TARGETED = "CHANGELOG002"
    CHANGELOG_VERSION_ORDER = "CHANGELOG003"