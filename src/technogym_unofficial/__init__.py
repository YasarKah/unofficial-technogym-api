"""Unofficial, personal-use client for the Technogym / mywellness API.

Not affiliated with Technogym S.p.A. Use with your own account.
"""
from __future__ import annotations

from .client import TechnogymClient
from .errors import (
    ApiError,
    AuthenticationError,
    RateLimitError,
    TechnogymError,
)
from .models import (
    Logbook,
    LogbookEntry,
    UserProfile,
    WorkoutPage,
    WorkoutSummary,
    WriteRequest,
)

__version__ = "0.1.0"

__all__ = [
    "ApiError",
    "AuthenticationError",
    "Logbook",
    "LogbookEntry",
    "RateLimitError",
    "TechnogymClient",
    "TechnogymError",
    "UserProfile",
    "WorkoutPage",
    "WorkoutSummary",
    "WriteRequest",
    "__version__",
]
