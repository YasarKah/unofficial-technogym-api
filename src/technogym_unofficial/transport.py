"""HTTP transport: host/header construction, auth, redaction, bounded retry.

All values here are observed from the real app (3.46.0) and verified live.
Per-service host is ``{service}.mywellness.com`` (prod). The ``x-mwapps-*``
headers and the ``_c`` culture query parameter are required; the app id and the
client-version *format* in particular must be exact or the server returns an
empty 401 before it even checks credentials.
"""
from __future__ import annotations

import datetime as _dt
import logging
import time
from typing import Any, Self

import httpx

from .errors import ApiError, AuthenticationError, RateLimitError

log = logging.getLogger("technogym_unofficial")

# --- app identity (verified live, app 3.46.0) --------------------------------
APP_ID = "EC1D38D7-D359-48D0-A60C-D8C0B8FB9DF9"
CLIENT = "tgappandroidcoach"
CLIENT_VERSION = "3.46.0.3444,tgappandroidcoach"  # <versionName>.<versionCode>,<client>
USER_AGENT = "Dart/3.11 (dart:io)"
DEFAULT_ENV = ""  # prod -> "{service}.mywellness.com"; dev/test/beta use "-dev." etc.

_SECRET_HEADERS = {"authorization", "x-mwapps-eqtoken", "cookie", "set-cookie"}
_SECRET_BODY_KEYS = {"password", "token", "accesstoken", "refreshtoken", "ssoauthtoken", "mfacode"}


def host_for(service: str, env: str = DEFAULT_ENV) -> str:
    """``core`` -> ``core.mywellness.com`` (prod) or ``core-dev.mywellness.com``."""
    suffix = f"{env}.mywellness.com" if env else ".mywellness.com"
    return f"{service}{suffix}"


def _redact_headers(headers: dict[str, str]) -> dict[str, str]:
    return {k: ("<redacted>" if k.lower() in _SECRET_HEADERS else v) for k, v in headers.items()}


def redact_body(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {
            k: ("<redacted>" if k.lower() in _SECRET_BODY_KEYS else redact_body(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [redact_body(v) for v in obj]
    return obj


class Transport:
    """Thin wrapper over an ``httpx.Client`` that applies mywellness conventions."""

    def __init__(
        self,
        *,
        tz_olson: str = "Europe/Istanbul",
        culture: str = "en",
        env: str = DEFAULT_ENV,
        timeout: float = 30.0,
        max_retries: int = 2,
        client: httpx.Client | None = None,
    ):
        self.tz_olson = tz_olson
        self.culture = culture
        self.env = env
        self.max_retries = max_retries
        self._token: str | None = None
        self._client = client or httpx.Client(timeout=timeout, follow_redirects=False)

    # -- session ----------------------------------------------------------
    @property
    def token(self) -> str | None:
        return self._token

    def set_token(self, token: str | None) -> None:
        self._token = token

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- headers ----------------------------------------------------------
    def _headers(self, *, authed: bool) -> dict[str, str]:
        h = {
            "Content-Type": "application/json",
            "Accept-Encoding": "gzip",
            "User-Agent": USER_AGENT,
            "x-mwapps-client": CLIENT,
            "x-mwapps-appid": APP_ID,
            "x-mwapps-clientversion": CLIENT_VERSION,
            "x-mwapps-pdate": _dt.datetime.now().strftime("%Y%m%d"),
            "x-mwapps-tz-olson": self.tz_olson,
        }
        if authed:
            if not self._token:
                raise AuthenticationError("Not authenticated: call login() first")
            h["Authorization"] = f"Bearer {self._token}"
        return h

    # -- request ----------------------------------------------------------
    def request(
        self,
        method: str,
        service: str,
        path: str,
        *,
        authed: bool = True,
        params: dict[str, Any] | None = None,
        json_body: Any | None = None,
        safe_status: tuple[int, ...] = (200,),
    ) -> Any:
        """Perform a request and return the parsed JSON payload.

        ``_c`` (culture) is always added. 429 is retried with bounded backoff for
        idempotent methods only. A non-``safe_status`` response raises ``ApiError``.
        """
        url = f"https://{host_for(service, self.env)}/{path.lstrip('/')}"
        q = {"_c": self.culture, **(params or {})}
        idempotent = method.upper() in ("GET", "HEAD")

        attempt = 0
        while True:
            attempt += 1
            headers = self._headers(authed=authed)
            log.debug(
                "%s %s params=%s headers=%s body=%s",
                method, url, q, _redact_headers(headers),
                redact_body(json_body) if json_body is not None else None,
            )
            resp = self._client.request(
                method, url, params=q, json=json_body, headers=headers
            )
            if resp.status_code == 429 and idempotent and attempt <= self.max_retries + 1:
                retry_after = _parse_retry_after(resp)
                time.sleep(retry_after if retry_after is not None else min(2 ** attempt, 30))
                continue
            return self._handle(resp, safe_status)

    def _handle(self, resp: httpx.Response, safe_status: tuple[int, ...]) -> Any:
        try:
            payload: Any = resp.json() if resp.content else None
        except ValueError:
            payload = None

        if resp.status_code == 429:
            raise RateLimitError(
                "Rate limited", status=429, body=payload, retry_after=_parse_retry_after(resp)
            )
        if resp.status_code not in safe_status:
            # app-level result string, when present, is safe to surface
            result = payload.get("result") if isinstance(payload, dict) else None
            raise ApiError(
                f"Unexpected status {resp.status_code}"
                + (f" ({result})" if result else ""),
                status=resp.status_code,
                body=payload,
            )
        # A 200 can still carry an application-level failure.
        if isinstance(payload, dict):
            result = payload.get("result")
            if result is not None and str(result).lower() not in ("success", "ok"):
                raise ApiError(f"Application error: {result}", status=resp.status_code, body=payload)
        return payload


def _parse_retry_after(resp: httpx.Response) -> float | None:
    ra = resp.headers.get("Retry-After")
    if not ra:
        return None
    try:
        return float(ra)
    except ValueError:
        return None
