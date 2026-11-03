"""Exceptions for the Technogym unofficial client.

Error messages never include credentials or tokens.
"""
from __future__ import annotations


class TechnogymError(Exception):
    """Base class for all client errors."""


class AuthenticationError(TechnogymError):
    """Login failed or the session is not authenticated.

    ``result`` carries the server's application-level result string when
    available (e.g. ``"UsernameOrPasswordNotValid"``), never the password.
    """

    def __init__(self, message: str, *, status: int | None = None, result: str | None = None):
        super().__init__(message)
        self.status = status
        self.result = result


class ApiError(TechnogymError):
    """The API returned an unexpected status or an application-level error.

    A 200 response that carries an application error is still an ``ApiError``.
    """

    def __init__(self, message: str, *, status: int | None = None, body: object | None = None):
        super().__init__(message)
        self.status = status
        # body is the parsed response payload (already free of secrets); kept for callers.
        self.body = body


class RateLimitError(ApiError):
    """HTTP 429. ``retry_after`` is seconds to wait when the server provided it."""

    def __init__(self, message: str, *, retry_after: float | None = None, **kwargs):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after
