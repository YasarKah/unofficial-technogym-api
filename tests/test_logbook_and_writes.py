from __future__ import annotations

import httpx
import respx

from technogym_unofficial import TechnogymClient
from technogym_unofficial.models import WriteRequest

LOGIN_URL = "https://core.mywellness.com/v2/enduser/authentication/Login"
LOGBOOK_URL = "https://workout.mywellness.com/logbook"
WORKOUT_URL = "https://workout.mywellness.com/v2/enduser/workout"


def _logged_in(login_success) -> TechnogymClient:
    respx.post(LOGIN_URL).mock(return_value=httpx.Response(200, json=login_success))
    c = TechnogymClient()
    c.login("u@example.com", "p")
    return c


@respx.mock
def test_get_logbook_parses_entries(login_success, logbook):
    route = respx.get(LOGBOOK_URL).mock(return_value=httpx.Response(200, json=logbook))
    c = _logged_in(login_success)

    lb = c.get_logbook(desired_size=50)
    assert len(lb.entries) == 2
    e = lb.entries[0]
    assert e.id_cr == 9001
    assert e.title == "Free training"
    assert e.calories == 500
    assert e.move == 400
    assert e.duration_seconds == 3000
    assert e.equipment_name == "Run Artis"
    assert e.raw["partitionDate"] == 20260601

    req = route.calls.last.request
    assert req.headers["Authorization"].startswith("Bearer ")
    assert req.url.params["desiredSize"] == "50"
    assert req.url.params["ignoreType"] == "Lifestyle"
    c.close()


def test_create_workout_dry_run_sends_nothing(login_success):
    with TechnogymClient() as c:
        c._t.set_token("tok")  # no network for a dry run
        plan = c.create_workout("[TEST] mine", dry_run=True)
    assert isinstance(plan, WriteRequest)
    assert plan.method == "PUT"
    assert plan.path == "/v2/enduser/workout"
    assert plan.body["name"] == "[TEST] mine"
    assert plan.body["displayWorkoutId"]  # defaulted uuid


@respx.mock
def test_create_workout_returns_server_id(login_success):
    route = respx.put(WORKOUT_URL).mock(
        return_value=httpx.Response(200, json={"displayWorkoutId": "U-abc123"})
    )
    c = _logged_in(login_success)
    wid = c.create_workout("[TEST] mine", facility_id=None)
    assert wid == "U-abc123"
    body = __import__("json").loads(route.calls.last.request.content)
    assert body["name"] == "[TEST] mine"
    assert body["assignedInFacilityId"] is None
    c.close()


@respx.mock
def test_delete_workout_puts_id_in_body(login_success):
    route = respx.delete(WORKOUT_URL).mock(return_value=httpx.Response(200, json={}))
    c = _logged_in(login_success)
    assert c.delete_workout("U-abc123") is None
    body = __import__("json").loads(route.calls.last.request.content)
    assert body == {"workoutId": "U-abc123"}
    c.close()


def test_delete_workout_dry_run(login_success):
    with TechnogymClient() as c:
        c._t.set_token("tok")
        plan = c.delete_workout("U-x", dry_run=True)
    assert isinstance(plan, WriteRequest)
    assert plan.method == "DELETE"
    assert plan.body == {"workoutId": "U-x"}
