"""High-level Technogym / mywellness client.

Verified live against a personal account (app 3.46.0):
  * ``login``          POST core/v2/enduser/authentication/Login
  * ``get_profile``    returned in the login response (userContext)
  * ``get_logbook``    GET workout/logbook — performed-workout history
  * ``list_workouts``  GET workout/v2/enduser/workout/GetUserWorkouts (saved templates)
  * ``create_workout`` / ``get_workout`` / ``delete_workout`` (writes; Phase B)

Read operations are the default. The write methods mutate the account and each
supports ``dry_run=True`` to inspect the request without sending it.
"""
from __future__ import annotations

import datetime as _dt
import logging
import os
import uuid as _uuid
from typing import Self

from .errors import ApiError, AuthenticationError
from .models import Logbook, UserProfile, WorkoutPage, WriteRequest
from .transport import Transport

log = logging.getLogger("technogym_unofficial")

DOMAIN = "com.mywellness"


def _fmt_date(d: str | _dt.date) -> str:
    """mywellness workout-history dates use the ``YYYYMMDD`` format (verified)."""
    if isinstance(d, _dt.date):
        return d.strftime("%Y%m%d")
    s = str(d)
    if "-" in s:  # accept ISO 'YYYY-MM-DD'
        return s.replace("-", "")[:8]
    return s


class TechnogymClient:
    """Read-only client for one mywellness account."""

    def __init__(
        self,
        *,
        tz_olson: str = "Europe/Istanbul",
        culture: str = "en",
        env: str = "",
        transport: Transport | None = None,
    ):
        self._t = transport or Transport(tz_olson=tz_olson, culture=culture, env=env)
        self._profile: UserProfile | None = None

    # -- lifecycle --------------------------------------------------------
    def close(self) -> None:
        self._t.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @property
    def is_authenticated(self) -> bool:
        return self._t.token is not None

    @property
    def token(self) -> str | None:
        return self._t.token

    # -- auth -------------------------------------------------------------
    def login(
        self,
        username: str | None = None,
        password: str | None = None,
        *,
        keep_logged_in: bool = True,
    ) -> UserProfile:
        """Authenticate and store the bearer token.

        Credentials default to ``TG_USERNAME`` / ``TG_PASSWORD`` from the
        environment so callers never have to hardcode them. Returns the profile.
        """
        username = username or os.environ.get("TG_USERNAME")
        password = password or os.environ.get("TG_PASSWORD")
        if not username or not password:
            raise AuthenticationError(
                "Missing credentials: pass username/password or set TG_USERNAME/TG_PASSWORD"
            )

        payload = self._t.request(
            "POST",
            "core",
            "/v2/enduser/authentication/Login",
            authed=False,
            json_body={
                "username": username,
                "password": password,
                "domain": DOMAIN,
                "keepMeLoggedIn": keep_logged_in,
            },
            safe_status=(200,),
        )
        if not isinstance(payload, dict) or "token" not in payload:
            raise AuthenticationError("Login response missing token", status=200)
        self._t.set_token(payload["token"])
        self._profile = UserProfile.from_user_context(payload.get("userContext") or {})
        log.info("Login OK for user id=%s", self._profile.id)
        return self._profile

    def logout(self) -> None:
        """Drop the local session token (no server call needed for read-only use)."""
        self._t.set_token(None)
        self._profile = None

    # -- reads ------------------------------------------------------------
    def get_profile(self) -> UserProfile:
        """Return the account profile captured at login."""
        if self._profile is None:
            raise AuthenticationError("Not authenticated: call login() first")
        return self._profile

    def list_workouts(
        self,
        date_from: str | _dt.date,
        date_to: str | _dt.date,
        *,
        extra_params: dict[str, object] | None = None,
    ) -> WorkoutPage:
        """List workout-history entries between two dates (inclusive).

        Dates accept ``datetime.date`` or ``YYYYMMDD`` / ``YYYY-MM-DD`` strings.
        Returns ``{items, total_count, ...}``; ``raw`` keeps the full payload.
        """
        params: dict[str, object] = {
            "from": _fmt_date(date_from),
            "to": _fmt_date(date_to),
        }
        if extra_params:
            params.update(extra_params)
        payload = self._t.request(
            "GET",
            "workout",
            "/v2/enduser/workout/GetUserWorkouts",
            authed=True,
            params=params,
            safe_status=(200,),
        )
        return WorkoutPage.from_response(payload if isinstance(payload, dict) else {})

    def get_logbook(self, *, desired_size: int = 50, ignore_type: str = "Lifestyle") -> Logbook:
        """Return performed-workout history (the activity logbook).

        This is the list of workouts the account actually performed (machine
        sessions etc.), newest first. ``desired_size`` caps how many entries to
        fetch; ``ignore_type`` filters out a category (the app uses
        ``"Lifestyle"``). Verified live.
        """
        payload = self._t.request(
            "GET",
            "workout",
            "/logbook",
            authed=True,
            params={"desiredSize": desired_size, "ignoreType": ignore_type},
            safe_status=(200,),
        )
        return Logbook.from_response(payload if isinstance(payload, dict) else {})

    # -- writes (Phase B; each live write mutates the account) ------------
    def create_workout(
        self,
        name: str,
        *,
        facility_id: str | None = None,
        display_workout_id: str | None = None,
        dry_run: bool = False,
    ) -> str | WriteRequest:
        """Create a new (empty) user workout and return its server id.

        ``display_workout_id`` is a client-generated UUID (defaulted if omitted);
        the server assigns and returns the real id (``U-...``). With
        ``dry_run=True`` nothing is sent — the planned request is returned so the
        caller can inspect it first. Verified live (create + delete).
        """
        body = {
            "name": name,
            "assignedInFacilityId": facility_id,
            "displayWorkoutId": display_workout_id or str(_uuid.uuid4()),
        }
        if dry_run:
            return WriteRequest("PUT", "workout", "/v2/enduser/workout", {}, body)
        payload = self._t.request(
            "PUT", "workout", "/v2/enduser/workout",
            authed=True, json_body=body, safe_status=(200,),
        )
        if isinstance(payload, dict):
            wid = payload.get("displayWorkoutId") or payload.get("id") or payload.get("workoutId")
            if wid:
                return wid
        raise ApiError("create_workout: no workout id in response", body=payload)

    def get_workout(self, workout_id: str, *, facility_id: str | None = None) -> dict:
        """Fetch one workout's overview by id."""
        params = {"facilityId": facility_id} if facility_id else {}
        payload = self._t.request(
            "GET", "workout", f"/v2/enduser/workout/{workout_id}",
            authed=True, params=params, safe_status=(200,),
        )
        return payload if isinstance(payload, dict) else {}

    def delete_workout(self, workout_id: str, *, dry_run: bool = False) -> None | WriteRequest:
        """Delete a user workout by id.

        The id goes in the request **body** (``DELETE /v2/enduser/workout`` with
        ``{"workoutId": ...}``), not in the path. Verified live.
        """
        body = {"workoutId": workout_id}
        if dry_run:
            return WriteRequest("DELETE", "workout", "/v2/enduser/workout", {}, body)
        self._t.request(
            "DELETE", "workout", "/v2/enduser/workout",
            authed=True, json_body=body, safe_status=(200,),
        )
        return None
