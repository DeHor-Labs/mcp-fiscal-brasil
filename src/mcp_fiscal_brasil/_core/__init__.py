"""Core public API for mcp-fiscal-brasil."""

from .config import Settings, settings
from .errors import (
    FiscalConfigurationError,
    FiscalError,
    FiscalHTTPError,
    FiscalNotFoundError,
    FiscalRateLimitError,
    FiscalValidationError,
)
from .http import HTTPClient
from .logging import get_logger

__all__ = [
    "FiscalConfigurationError",
    "FiscalError",
    "FiscalHTTPError",
    "FiscalNotFoundError",
    "FiscalRateLimitError",
    "FiscalValidationError",
    "HTTPClient",
    "Settings",
    "get_logger",
    "settings",
]
