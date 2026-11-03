from __future__ import annotations

import datetime

import httpx
import respx

from technogym_unofficial import TechnogymClient

LOGIN_URL = "https://core.mywellness.com/v2/enduser/authentication/Login"
WORKOUTS_URL = "https://workout.mywellness.com/v2/enduser/workout/GetUserWorkouts"


def _logged_in(login_success) -> TechnogymClient:
    respx.post(LOGIN_URL).mock(return_value=httpx.Response(200, json=login_success))
    c = TechnogymClient()
    c.login("u@example.com", "p")
    return c


@respx.mock
def test_list_workouts_parses_items_and_attaches_bearer(login_success, workouts_page):
    route = respx.get(WORKOUTS_URL).mock(return_value=httpx.Response(200, json=workouts_page))
    c = _logged_in(login_success)

    page = c.list_workouts("20260101", "20261231")
    assert page.total_count == 2
    assert len(page.items) == 2
    assert page.items[0].name == "Full Body"
    assert page.items[0].session_type == "Strength"
    assert page.items[0].duration_seconds == 3600
    assert page.items[0].raw["performedDate"] == "20261102"  # raw preserved

    req = route.calls.last.request
    assert req.headers["Authorization"] == f"Bearer {login_success['token']}"
    assert req.url.params["from"] == "20260101"
    assert req.url.params["to"] == "20261231"
    assert req.url.params["_c"] == "en"
    c.close()


@respx.mock
def test_list_workouts_accepts_date_objects_and_iso(login_success, workouts_page):
    route = respx.get(WORKOUTS_URL).mock(return_value=httpx.Response(200, json=workouts_page))
    c = _logged_in(login_success)

    c.list_workouts(datetime.date(2026, 1, 1), "2026-12-31")
    req = route.calls.last.request
    assert req.url.params["from"] == "20260101"  # date -> YYYYMMDD
    assert req.url.params["to"] == "20261231"    # ISO -> YYYYMMDD
    c.close()


@respx.mock
def test_empty_items_is_ok(login_success):
    empty = {"from": "20260101", "to": "20261231", "totalCount": 0, "items": []}
    respx.get(WORKOUTS_URL).mock(return_value=httpx.Response(200, json=empty))
    c = _logged_in(login_success)
    page = c.list_workouts("20260101", "20261231")
    assert page.total_count == 0
    assert page.items == []
    c.close()
