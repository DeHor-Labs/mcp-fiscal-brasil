"""Structured logging helpers for the MCP Fiscal Brasil package."""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Mapping
from typing import Final, cast

import structlog
from structlog.typing import Processor

__all__ = ["get_logger"]

_ENV_VAR: Final = "MCP_FISCAL_ENV"
_PRODUCTION_ENV: Final = "production"
_LOG_LEVEL_VAR: Final = "MCP_FISCAL_LOG_LEVEL"
_DEFAULT_LOG_LEVEL: Final = "INFO"
_LOG_LEVELS: Final[Mapping[str, int]] = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
    "NOTSET": logging.NOTSET,
}


def _is_production() -> bool:
    return os.getenv(_ENV_VAR, "").strip().lower() == _PRODUCTION_ENV


def _log_level() -> int:
    configured = os.getenv(_LOG_LEVEL_VAR, _DEFAULT_LOG_LEVEL).strip().upper()
    return _LOG_LEVELS.get(configured, logging.INFO)


def _processors(json_output: bool) -> list[Processor]:
    renderer: Processor
    if json_output:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=False)

    return [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        renderer,
    ]


def _configure_structlog() -> None:
    json_output = _is_production()
    structlog.configure(
        processors=_processors(json_output),
        context_class=dict,
        logger_factory=structlog.WriteLoggerFactory(file=sys.stderr),
        wrapper_class=structlog.make_filtering_bound_logger(_log_level()),
        cache_logger_on_first_use=False,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Return a configured structlog logger for the current runtime environment."""
    _configure_structlog()
    return cast(structlog.BoundLogger, structlog.get_logger().bind(logger=name))
