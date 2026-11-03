"""Typed models for Technogym / mywellness responses.

Each model keeps the parsed ``raw`` payload so no source field is lost when a
typed attribute does not cover it. Field shapes are derived from observed live
responses (app 3.46.0); unknown or absent fields stay ``None``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class UserProfile:
    """Account profile, taken from the ``userContext`` of the login response."""

    id: str | None
    username: str | None
    first_name: str | None
    last_name: str | None
    nick_name: str | None
    email: str | None
    gender: str | None
    birth_date: str | None  # YYYYMMDD as returned
    measurement_system: str | None
    default_culture: str | None
    time_zone_windows_id: str | None
    created_on: str | None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_user_context(cls, uc: dict[str, Any]) -> UserProfile:
        return cls(
            id=uc.get("id"),
            username=uc.get("accountUsername"),
            first_name=uc.get("firstName"),
            last_name=uc.get("lastName"),
            nick_name=uc.get("nickName"),
            email=uc.get("email"),
            gender=uc.get("gender"),
            birth_date=uc.get("birthDate"),
            measurement_system=uc.get("measurementSystem"),
            default_culture=uc.get("defaultCulture"),
            time_zone_windows_id=uc.get("timeZoneWindowsId"),
            created_on=uc.get("createdOn"),
            raw=uc,
        )


@dataclass(slots=True)
class WorkoutSummary:
    """One entry from the workout-history list.

    The mywellness item shape varies by workout type; typed fields cover the
    common summary keys and ``raw`` preserves everything else.
    """

    id: str | None
    name: str | None
    performed_date: str | None
    session_type: str | None
    duration_seconds: int | None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_item(cls, it: dict[str, Any]) -> WorkoutSummary:
        return cls(
            id=it.get("id") or it.get("idCr") or it.get("physicalActivityId"),
            name=it.get("name") or it.get("title"),
            performed_date=it.get("performedDate") or it.get("performedOn") or it.get("date"),
            session_type=it.get("sessionType") or it.get("type"),
            duration_seconds=it.get("duration") or it.get("durationSeconds"),
            raw=it,
        )


@dataclass(slots=True)
class WorkoutPage:
    """A page of workout-history results: ``{from, to, items, totalCount}``."""

    items: list[WorkoutSummary]
    total_count: int | None
    date_from: str | None
    date_to: str | None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_response(cls, payload: dict[str, Any]) -> WorkoutPage:
        items = [WorkoutSummary.from_item(i) for i in (payload.get("items") or [])]
        return cls(
            items=items,
            total_count=payload.get("totalCount"),
            date_from=payload.get("from"),
            date_to=payload.get("to"),
            raw=payload,
        )


@dataclass(slots=True)
class LogbookEntry:
    """A performed-workout history entry from ``/logbook`` (verified live).

    Fields come from the real response; ``raw`` preserves the full item.
    """

    id: str | None
    id_cr: int | None
    title: str | None
    type: str | None
    performed_on: str | None  # e.g. "2026-10-30 19:55:48 +03:00"
    partition_date: int | None  # YYYYMMDD
    calories: int | None
    move: int | None
    duration_seconds: int | None
    exercises_done: int | None
    equipment_name: str | None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_item(cls, it: dict[str, Any]) -> LogbookEntry:
        return cls(
            id=it.get("id"),
            id_cr=it.get("idCr"),
            title=it.get("title"),
            type=it.get("type"),
            performed_on=it.get("performedOn"),
            partition_date=it.get("partitionDate"),
            calories=it.get("calories"),
            move=it.get("move"),
            duration_seconds=it.get("duration"),
            exercises_done=it.get("totalExeDone"),
            equipment_name=it.get("equipmentName"),
            raw=it,
        )


@dataclass(slots=True)
class Logbook:
    """Performed-workout history: ``{data: {logbooks: [...]}}`` (verified live)."""

    entries: list[LogbookEntry]
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_response(cls, payload: dict[str, Any]) -> Logbook:
        data = payload.get("data") or {}
        rows = data.get("logbooks") if isinstance(data, dict) else None
        return cls(entries=[LogbookEntry.from_item(i) for i in (rows or [])], raw=payload)


@dataclass(slots=True)
class WriteRequest:
    """Describes a write request produced by a ``dry_run`` call (nothing sent)."""

    method: str
    service: str
    path: str
    params: dict[str, Any]
    body: Any
