"""
Logging configuration for sru-lint.
Provides a centralized logger that can be used across all modules.
"""
import logging
import sys
from typing import Optional


class ColoredFormatter(logging.Formatter):
    """Formatter that adds colors to log levels."""
    
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record):
        if hasattr(record, 'levelname') and record.levelname in self.COLORS:
            original_levelname = record.levelname
            record.levelname = f"{self.COLORS[original_levelname]}{original_levelname}{self.RESET}"
            formatted = super().format(record)
            record.levelname = original_levelname  # Restore original
            return formatted
        return super().format(record)


def setup_logger(name: str = "sru-lint", level: int = logging.INFO) -> logging.Logger:
    """
    Set up the application logger.
    
    Args:
        name: Logger name
        level: Logging level (default: INFO)
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Avoid adding multiple handlers if called multiple times
    if logger.handlers:
        logger.setLevel(level)
        for handler in logger.handlers:
            handler.setLevel(level)
        return logger
    
    logger.setLevel(level)
    
    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    
    # Create formatter
    formatter = ColoredFormatter(
        fmt='%(levelname)-8s %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    
    logger.addHandler(handler)
    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a logger instance.
    
    Args:
        name: Optional logger name. If None, uses the root sru-lint logger.
        
    Returns:
        Logger instance
    """
    if name is None:
        return logging.getLogger("sru-lint")
    return logging.getLogger(f"sru-lint.{name}")


def set_log_level(level: int):
    """
    Update the log level for all existing loggers.
    
    Args:
        level: New logging level
    """
    root_logger = logging.getLogger("sru-lint")
    root_logger.setLevel(level)
    for handler in root_logger.handlers:
        handler.setLevel(level)


# Initialize the main logger
_main_logger = setup_logger()