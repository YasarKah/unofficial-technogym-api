from __future__ import annotations

import httpx
import pytest
import respx

from technogym_unofficial import ApiError, RateLimitError, TechnogymClient
from technogym_unofficial.transport import Transport, host_for, redact_body

LOGIN_URL = "https://core.mywellness.com/v2/enduser/authentication/Login"


def test_host_for():
    assert host_for("core") == "core.mywellness.com"
    assert host_for("workout") == "workout.mywellness.com"
    assert host_for("training", env="-dev") == "training-dev.mywellness.com"


def test_redact_body_hides_secrets():
    red = redact_body({"username": "a", "password": "p", "token": "t", "keepMeLoggedIn": True})
    assert red["username"] == "a"
    assert red["password"] == "<redacted>"
    assert red["token"] == "<redacted>"
    assert red["keepMeLoggedIn"] is True


@respx.mock
def test_empty_401_raises_apierror_without_leaking():
    # Wrong app identity -> empty 401 (the real failure mode we fixed)
    respx.post(LOGIN_URL).mock(return_value=httpx.Response(401))
    with TechnogymClient() as c, pytest.raises(Exception) as exc:
        c.login("u@example.com", "secretpw")
    assert "secretpw" not in str(exc.value)


@respx.mock
def test_200_with_app_error_is_failure():
    respx.post(LOGIN_URL).mock(return_value=httpx.Response(200, json={"result": "SomethingWrong"}))
    with TechnogymClient() as c, pytest.raises(ApiError):
        c.login("u@example.com", "p")


@respx.mock
def test_429_retried_for_get_then_succeeds(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)
    t = Transport(max_retries=2)
    t.set_token("tok")
    route = respx.get("https://workout.mywellness.com/v2/enduser/workout/GetUserWorkouts")
    route.side_effect = [
        httpx.Response(429, headers={"Retry-After": "0"}),
        httpx.Response(200, json={"items": [], "totalCount": 0}),
    ]
    payload = t.request("GET", "workout", "/v2/enduser/workout/GetUserWorkouts")
    assert payload == {"items": [], "totalCount": 0}
    assert route.call_count == 2
    t.close()


@respx.mock
def test_429_not_retried_for_post(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)
    t = Transport(max_retries=3)
    respx.post(LOGIN_URL).mock(return_value=httpx.Response(429))
    with pytest.raises(RateLimitError):
        t.request(
            "POST", "core", "/v2/enduser/authentication/Login",
            authed=False, json_body={"username": "u", "password": "p"},
        )
    assert respx.calls.call_count == 1  # no retry on non-idempotent
    t.close()
