"""Command-line interface: ``technogym <command>``.

Credentials come from the environment (``TG_USERNAME`` / ``TG_PASSWORD``) or an
interactive secure prompt. The password is never echoed, logged, or stored.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import getpass
import json
import os
import sys

from . import __version__
from .client import TechnogymClient
from .errors import TechnogymError


def _load_dotenv(path: str = ".env") -> None:
    """Minimal .env loader (no dependency); existing env vars win."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            v = v.strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                v = v[1:-1]
            os.environ.setdefault(k.strip(), v)


def _credentials(args: argparse.Namespace) -> tuple[str, str]:
    user = os.environ.get("TG_USERNAME")
    pw = os.environ.get("TG_PASSWORD")
    if not user:
        user = input("Email: ").strip()
    if not pw:
        pw = getpass.getpass("Password: ")
    return user, pw


def _client(args: argparse.Namespace) -> TechnogymClient:
    return TechnogymClient(tz_olson=args.tz, culture=args.culture, env=args.env)


def _print(obj: object) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False, default=str))


def cmd_me(args: argparse.Namespace) -> int:
    user, pw = _credentials(args)
    with _client(args) as c:
        c.login(user, pw)
        p = c.get_profile()
        _print(
            {
                "id": p.id,
                "username": p.username,
                "firstName": p.first_name,
                "lastName": p.last_name,
                "gender": p.gender,
                "measurementSystem": p.measurement_system,
                "culture": p.default_culture,
            }
        )
    return 0


def cmd_auth_status(args: argparse.Namespace) -> int:
    user, pw = _credentials(args)
    with _client(args) as c:
        try:
            c.login(user, pw)
            print("authenticated: yes")
            print(f"user id: {c.get_profile().id}")
            return 0
        except TechnogymError as e:
            print(f"authenticated: no ({e})")
            return 1


def cmd_workouts_list(args: argparse.Namespace) -> int:
    user, pw = _credentials(args)
    with _client(args) as c:
        c.login(user, pw)
        page = c.list_workouts(args.date_from, args.date_to)
        out = {
            "from": page.date_from,
            "to": page.date_to,
            "totalCount": page.total_count,
            "items": [w.raw for w in page.items],
        }
        _print(out)
    return 0


def cmd_workouts_log(args: argparse.Namespace) -> int:
    user, pw = _credentials(args)
    with _client(args) as c:
        c.login(user, pw)
        lb = c.get_logbook(desired_size=args.size)
        _print(
            [
                {
                    "idCr": e.id_cr,
                    "performedOn": e.performed_on,
                    "title": e.title,
                    "type": e.type,
                    "equipment": e.equipment_name,
                    "durationSec": e.duration_seconds,
                    "calories": e.calories,
                    "move": e.move,
                    "exercises": e.exercises_done,
                }
                for e in lb.entries
            ]
        )
    return 0


def cmd_workouts_create(args: argparse.Namespace) -> int:
    with _client(args) as c:
        if args.dry_run:
            # No login needed to show the planned request.
            c._t.set_token("DRY-RUN")
            plan = c.create_workout(args.name, dry_run=True)
            _print({"method": plan.method, "path": plan.path, "body": plan.body})
            return 0
        user, pw = _credentials(args)
        c.login(user, pw)
        wid = c.create_workout(args.name)
        _print({"created": True, "workoutId": wid, "name": args.name})
    return 0


def cmd_workouts_delete(args: argparse.Namespace) -> int:
    with _client(args) as c:
        if args.dry_run:
            c._t.set_token("DRY-RUN")
            plan = c.delete_workout(args.workout_id, dry_run=True)
            _print({"method": plan.method, "path": plan.path, "body": plan.body})
            return 0
        user, pw = _credentials(args)
        c.login(user, pw)
        c.delete_workout(args.workout_id)
        _print({"deleted": True, "workoutId": args.workout_id})
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="technogym", description=__doc__)
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("--tz", default=os.environ.get("TG_TZ", "Europe/Istanbul"), help="Olson timezone")
    p.add_argument("--culture", default="en", help="UI culture code (_c)")
    p.add_argument("--env", default="", help="API environment: '' (prod), '-dev', '-test', '-beta'")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("me", help="show the account profile").set_defaults(func=cmd_me)

    auth = sub.add_parser("auth", help="authentication").add_subparsers(dest="sub", required=True)
    auth.add_parser("status", help="check login works").set_defaults(func=cmd_auth_status)

    w = sub.add_parser("workouts", help="workouts and history").add_subparsers(dest="sub", required=True)
    today = _dt.date.today()

    wlog = w.add_parser("log", help="performed-workout history (logbook)")
    wlog.add_argument("--size", type=int, default=50, help="max entries to fetch")
    wlog.set_defaults(func=cmd_workouts_log)

    wl = w.add_parser("list", help="saved workout templates between two dates")
    wl.add_argument("--from", dest="date_from", default=(today - _dt.timedelta(days=30)).isoformat())
    wl.add_argument("--to", dest="date_to", default=today.isoformat())
    wl.set_defaults(func=cmd_workouts_list)

    wc = w.add_parser("create", help="create a new (empty) workout [write]")
    wc.add_argument("name", help="workout name")
    wc.add_argument("--dry-run", action="store_true", help="print the request without sending")
    wc.set_defaults(func=cmd_workouts_create)

    wd = w.add_parser("delete", help="delete a workout by id [write]")
    wd.add_argument("workout_id", help="server workout id, e.g. U-...")
    wd.add_argument("--dry-run", action="store_true", help="print the request without sending")
    wd.set_defaults(func=cmd_workouts_delete)
    return p


def main(argv: list[str] | None = None) -> int:
    _load_dotenv()
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except TechnogymError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
