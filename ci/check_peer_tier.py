"""A SERVICE MUST NOT REACH A PEER THROUGH A DOOR BUILT FOR A PERSON.

THE DEFECT THIS WAS WRITTEN FOR. portal read and wrote the customer's five switches through
reminders' `/api/v1/prefs/{ref}`, which carries `Depends(rate_limit)`. portal presents no bearer
token — only X-Internal-Token — so the limiter had no subject to key on and fell back to the IP it
could see: the PORTAL POD'S. Every customer page view of every establishment on the fleet spent one
unit of ONE shared bucket. Past it, reminders answers 429 — the switches section reads «تعذّرت
القراءة» for customers who did nothing, and a customer tapping the one-tap unsubscribe gets no
confirmation that his stop was recorded. The comment three files away says what he does next: he
blocks the shop's number.

WHY IT IS A GATE AND NOT A FIX. The shape is not "portal and prefs". It is: a `*_PATH` setting that
names a route on a tier whose limits are counted per CALLER, dereferenced by a service whose caller
is a pod. Nothing about that is visible at either end — the config file sees a string, the route
sees a request — so it survives every review that reads one file at a time.

WHAT IT DOES NOT SEE, stated rather than implied:
  · A path built by string concatenation instead of a `*_PATH` setting. It reads settings only.
  · A peer of the PLATFORM (`platform/`), which is read-only to us: those are reported as an
    ESCALATION line, never as a pass, because we cannot add an internal route there ourselves.
  · Whether the route is rate limited by a middleware rather than a route dependency.

IT MUST NEVER PASS BY WARNING. A path it cannot resolve to a route is a FAILURE, not a shrug: an
unresolvable path is exactly what a renamed route looks like.
"""
from __future__ import annotations

import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVICES = ROOT / "services"

# The suffix a peer path setting carries by convention across every service here.
PATH_SETTING = re.compile(r"^[A-Z0-9_]+_PATH$")

# Which service serves a prefix. `/internal/...` is the tier this gate is defending; anything
# under `/api/` is the user tier, where a limiter keys on a person.
USER_TIER = "/api/"


def _service_configs() -> list[pathlib.Path]:
    return sorted(p for p in SERVICES.glob("*/app/config.py"))


def _peer_paths(config: pathlib.Path) -> list[tuple[str, str]]:
    """Every `*_PATH = "..."` string default declared in this service's settings."""
    tree = ast.parse(config.read_text(encoding="utf-8"))
    out: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.AnnAssign) or not isinstance(node.target, ast.Name):
            continue
        name = node.target.id
        if not PATH_SETTING.match(name):
            continue
        value = node.value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            out.append((name, value.value))
    return out


def _limited_user_routes() -> set[tuple[str, str]]:
    """(method, full path) for every user-tier route that carries a per-caller rate limit."""
    found: set[tuple[str, str]] = set()
    for api in SERVICES.glob("*/app/api/v1/*.py"):
        src = api.read_text(encoding="utf-8")
        tree = ast.parse(src)
        prefix = ""
        for node in ast.walk(tree):
            if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)
                    and getattr(node.value.func, "id", "") == "APIRouter"):
                for kw in node.value.keywords:
                    if kw.arg == "prefix" and isinstance(kw.value, ast.Constant):
                        prefix = str(kw.value.value)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for dec in node.decorator_list:
                if not isinstance(dec, ast.Call):
                    continue
                fn = dec.func
                if not isinstance(fn, ast.Attribute) or getattr(fn.value, "id", "") != "router":
                    continue
                method = fn.attr.upper()
                route = ""
                if dec.args and isinstance(dec.args[0], ast.Constant):
                    route = str(dec.args[0].value)
                limited = "rate_limit" in ast.dump(dec)
                if limited:
                    found.add((method, f"/api/v1{prefix}{route}"))
    return found


def main() -> int:
    limited = _limited_user_routes()
    problems: list[str] = []
    escalations: list[str] = []

    for config in _service_configs():
        service = config.parents[1].name
        for name, value in _peer_paths(config):
            if not value.startswith(USER_TIER):
                continue
            # `{ref}` in a setting is `{ref}` in the route — the same placeholder both sides.
            matches = [r for m, r in limited if r == value]
            if matches:
                problems.append(
                    f"{service}: {name} = {value} names a rate-limited USER-tier route. "
                    f"A pod has no subject, so the limiter keys on the pod's IP and every "
                    f"customer of every shop shares one bucket — past it the caller gets 429 "
                    f"and renders a failure the customer caused nothing of.")
                continue
            # Not one of ours — the platform serves it, and we cannot add an internal route there.
            escalations.append(
                f"{service}: {name} = {value} is a user-tier path served OUTSIDE this repo "
                f"(platform/). Cannot be fixed here; needs an internal-tier route upstream.")

    for line in escalations:
        print(f"  ~ ESCALATION: {line}")

    if problems:
        print(f"  x {len(problems)} peer call(s) on a person's door:")
        for line in problems:
            print(f"    {line}")
        return 1

    print("  + every peer path this repo controls is on the internal tier — "
          "no pod spends a person's rate limit")
    return 0


if __name__ == "__main__":
    sys.exit(main())
