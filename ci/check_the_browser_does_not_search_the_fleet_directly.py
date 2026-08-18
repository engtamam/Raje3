#!/usr/bin/env python3
"""The console reaches a peer service through one of OUR routes, never straight at it (ط-3).

WHAT IT COST. The keypad called search-service itself: `GET /api/v1/search/suggest` for the terms
and `POST /api/v1/search` for the people. Neither route has ever known what a branch is, so a
supervisor scoped to Jeddah typed four digits and read Riyadh's customers by name, phone and plate.
Every narrowing operations had built — `overdue`, `customers_by_refs`, the strip along the top of
the field screen — was intact and irrelevant, because the browser was not asking operations at all.

AND THE FIX THAT LOOKS LIKE A FIX. Adding `filters: {branch_id: …}` to the request from the console
would read, in a diff and in a screenshot, exactly like a scope. It is not one: the value is chosen
by the caller, and the next caller chooses differently. A scope is only a scope where the caller
cannot pick it — which means on a route that resolves it from the token. That is why this gate bans
the CALL rather than checking the filter.

WHAT IS BANNED, AND IT IS A SHAPE RATHER THAN A LIST OF NAMES. A request path under `/api/v1/` that
is not one of the prefixes this product's own services mount. Our services own their prefixes
(`/api/v1/field/…`, `/api/v1/staff/…`); anything else under `/api/v1/` is a peer's route being
called across the gateway by a browser, and the browser is the one place a scope cannot be enforced.

No exceptions table. A screen that needs something a peer holds needs a route of ours that answers
it — which is the work, and it is the same work every time.
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONSOLE = ROOT / "apps" / "console" / "src"

#: The prefixes our own services mount under. Derived from the routers rather than typed here would
#: be better still; this list is checked against the running routers by check_deploy_wiring.
OURS = ("field", "staff", "owner", "till", "partner", "loyalty", "campaigns", "insights",
        "portal", "reminders", "subscription", "apps", "connect", "signup", "auth", "branches",
        "privacy", "operators", "services", "customers", "visits", "platform", "admin")

#: Any `/api/v1/<something>` inside a string literal in the console.
CALL = re.compile(r"['\"`]/api/v1/([a-z0-9_-]+)")


def main() -> int:
    if not CONSOLE.is_dir():
        print(f"{CONSOLE.relative_to(ROOT).as_posix()} is missing — this gate cannot answer, so "
              f"it refuses to")
        return 1

    bad: list[str] = []
    read = 0
    for path in sorted(CONSOLE.rglob("*")):
        if not path.is_file() or path.suffix not in (".ts", ".tsx"):
            continue
        if "node_modules" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"cannot read {path.relative_to(ROOT).as_posix()}: {exc} — NOT checked")
            return 1
        read += 1
        for n, line in enumerate(text.splitlines(), 1):
            if line.lstrip().startswith(("//", "*", "/*")):
                continue
            for seg in CALL.findall(line):
                if seg not in OURS:
                    bad.append(
                        f"{path.relative_to(ROOT).as_posix()}:{n}: /api/v1/{seg} is a peer's own "
                        f"route. A browser calling it carries no scope we can enforce — the "
                        f"narrowing has to happen on a route of ours that reads it from the token")

    if not read:
        print("no console sources read — this gate has nothing to check, which is not the same as "
              "finding nothing wrong")
        return 1

    if bad:
        print(f"{len(bad)} direct call(s) from the browser to a peer service:")
        for line in bad:
            print("  " + line)
        print("")
        print("Add the route to operations (or whichever service owns the data), resolve the")
        print("branch scope there from the token, and have the screen call that. A filter the")
        print("browser chooses is decoration; it is not a guard.")
        return 1

    if not read:
        # Same reason as the sends check: an empty scan is not a clean console, it is a check that
        # lost its subject — a moved directory, a renamed extension, a path typo.
        print("  [31m✗ read no console files at all — this check no longer knows where to "
              "look[0m")
        return 1
    print(f"ok  {read} console files — every /api/v1 call goes to a route of ours")
    return 0


if __name__ == "__main__":
    sys.exit(main())
