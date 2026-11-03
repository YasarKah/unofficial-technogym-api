from __future__ import annotations

import httpx
import pytest
import respx

from technogym_unofficial import AuthenticationError, TechnogymClient
from technogym_unofficial.transport import APP_ID, CLIENT, CLIENT_VERSION

LOGIN_URL = "https://core.mywellness.com/v2/enduser/authentication/Login"


@respx.mock
def test_login_sends_exact_request_and_stores_token(login_success):
    route = respx.post(LOGIN_URL).mock(return_value=httpx.Response(200, json=login_success))
    with TechnogymClient() as c:
        profile = c.login("testuser@example.com", "secret")

    assert c.is_authenticated
    assert c.token == login_success["token"]
    assert profile.id == "00000000-0000-0000-0000-000000000000"
    assert profile.username == "testuser@example.com"

    req = route.calls.last.request
    # required app-identity headers must be exact (empty 401 otherwise, verified live)
    assert req.headers["x-mwapps-appid"] == APP_ID
    assert req.headers["x-mwapps-client"] == CLIENT
    assert req.headers["x-mwapps-clientversion"] == CLIENT_VERSION
    assert req.headers["x-mwapps-pdate"].isdigit() and len(req.headers["x-mwapps-pdate"]) == 8
    assert "Authorization" not in req.headers  # login is unauthenticated
    assert req.url.params["_c"] == "en"

    import json as _json
    body = _json.loads(req.content)
    assert body == {
        "username": "testuser@example.com",
        "password": "secret",
        "domain": "com.mywellness",
        "keepMeLoggedIn": True,
    }


@respx.mock
def test_login_bad_credentials_raises(login_success):
    respx.post(LOGIN_URL).mock(
        return_value=httpx.Response(401, json={"result": "UsernameOrPasswordNotValid"})
    )
    with TechnogymClient() as c, pytest.raises(Exception) as exc:
        c.login("x@example.com", "wrong")
    assert "UsernameOrPasswordNotValid" in str(exc.value)
    assert not c.is_authenticated


def test_missing_credentials_raises(monkeypatch):
    monkeypatch.delenv("TG_USERNAME", raising=False)
    monkeypatch.delenv("TG_PASSWORD", raising=False)
    with TechnogymClient() as c, pytest.raises(AuthenticationError):
        c.login()


def test_reads_require_login():
    with TechnogymClient() as c:
        with pytest.raises(AuthenticationError):
            c.get_profile()
        with pytest.raises(AuthenticationError):
            c.list_workouts("20260101", "20261231")
