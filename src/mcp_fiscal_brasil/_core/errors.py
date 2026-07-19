"""Shared fiscal error types."""

from __future__ import annotations

from typing import Any


class FiscalError(Exception):
    """Base exception for fiscal domain failures."""

    def __init__(self, message: str, detail: Any | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail

    def __str__(self) -> str:
        return self.message

    def __repr__(self) -> str:
        return self._format_repr()

    def _repr_fields(self) -> dict[str, Any]:
        return {
            "message": self.message,
            "detail": self.detail,
        }

    def _format_repr(self) -> str:
        fields = ", ".join(f"{name}={value!r}" for name, value in self._repr_fields().items())
        return f"{self.__class__.__name__}({fields})"


class FiscalHTTPError(FiscalError):
    """Exception raised for HTTP failures from external fiscal services."""

    def __init__(
        self,
        message: str,
        status_code: int,
        url: str,
        detail: Any | None = None,
    ) -> None:
        super().__init__(message, detail=detail)
        self.status_code = status_code
        self.url = url

    def _repr_fields(self) -> dict[str, Any]:
        fields = super()._repr_fields()
        fields.update(
            {
                "status_code": self.status_code,
                "url": self.url,
            }
        )
        return fields


class FiscalRateLimitError(FiscalError):
    """Exception raised when a fiscal service rate limit is reached."""

    def __init__(
        self,
        message: str,
        retry_after: float | None = None,
        detail: Any | None = None,
    ) -> None:
        super().__init__(message, detail=detail)
        self.retry_after = retry_after

    def _repr_fields(self) -> dict[str, Any]:
        fields = super()._repr_fields()
        fields["retry_after"] = self.retry_after
        return fields


class FiscalValidationError(FiscalError):
    """Exception raised when an input value fails fiscal validation."""

    def __init__(
        self,
        message: str,
        field: str,
        value: Any,
        detail: Any | None = None,
    ) -> None:
        super().__init__(message, detail=detail)
        self.field = field
        self.value = value

    def _repr_fields(self) -> dict[str, Any]:
        fields = super()._repr_fields()
        fields.update(
            {
                "field": self.field,
                "value": self.value,
            }
        )
        return fields


class FiscalNotFoundError(FiscalError):
    """Exception raised when a requested fiscal resource is not found."""

    def __init__(
        self,
        message: str,
        resource_type: str,
        identifier: str,
        detail: Any | None = None,
    ) -> None:
        super().__init__(message, detail=detail)
        self.resource_type = resource_type
        self.identifier = identifier

    def _repr_fields(self) -> dict[str, Any]:
        fields = super()._repr_fields()
        fields.update(
            {
                "resource_type": self.resource_type,
                "identifier": self.identifier,
            }
        )
        return fields


class FiscalConfigurationError(FiscalError):
    """Exception raised when a required fiscal integration is not configured.

    Distinct from FiscalValidationError (bad input) and FiscalHTTPError
    (upstream reachable but failed): this means the deployment itself is
    missing a prerequisite (e.g. no A1 certificate configured), not a
    request-level or upstream failure.
    """


__all__ = [
    "FiscalConfigurationError",
    "FiscalError",
    "FiscalHTTPError",
    "FiscalNotFoundError",
    "FiscalRateLimitError",
    "FiscalValidationError",
]
