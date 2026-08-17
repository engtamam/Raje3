#!/usr/bin/env python3
"""A TIME BOUND CROSSING INTO `platform/` IS FORMATTED, NEVER HANDED OVER AS AN EPOCH.

THE BUG THIS EXISTS FOR PAID PARTNERS ZERO RIYALS EVERY MONTH, SILENTLY.

`operations` reads billing-service's cross-tenant invoice list to learn what each shop actually
paid, and passes the period as `since` / `until`. It sent `calendar.timegm(...)` — an integer.
`billing_service.browse_platform` filters with `created > until` and `created < since`, where
`created` is an ISO-8601 string. Comparing "2026-06-15T09:00:00Z" against "1780272000" is a
LEXICOGRAPHIC comparison that decides on the first character — `'2' > '1'` — so every genuine
invoice read as newer than the window and was skipped. Not a subset. All of them.

WHAT MADE IT INVISIBLE. Both sides are correct in isolation: an epoch is a fine way to name an
instant, and comparing ISO strings is a fine way to order them. Nothing raised, nothing logged,
nothing was empty in a way that looked wrong — `for_period` simply returned `{}`, every partner
settled at `0`, and a statement for 0.00 SAR is indistinguishable from an honest statement for a
partner who earned nothing. The only detector was a partner disputing their own payout.

THE RULE, AND IT NEEDS NO EXCEPTIONS TABLE. In any of OUR modules that build a request to a
platform service, a time-named parameter is passed through a named converter — never a bare
integer, and never an inline `strftime` at the call site. One converter, one place that knows the
format, and the reason written where it is read.

WHY NOT «just fix the call site». Because there will be a second one. Somebody will add a report,
reach for the same admin route, and pass the epoch they already have in hand — and the failure
they get is not an error, it is a plausible zero. A defect whose symptom is a believable number
must be made unwritable, not merely corrected once.

SCOPE. Only files that actually address a platform service — a module holding a billing/identity
admin base URL. Our own services speak epochs to each other on purpose, and narrowing the scope is
how this gate holds without a list of blessed exceptions.
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVICES = ROOT / "services"

C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"

# A module that talks to a platform ADMIN route: it names one in a request path. This is what keeps
# the gate off the dozens of peer adapters that speak epoch to our own services quite correctly.
ADDRESSES_PLATFORM = re.compile(r"/api/v1/(billing|identity|tenancy|authz)/admin/")

# `"since": <value>` / `"until": <value>` inside a dict literal being built for a request.
A_TIME_BOUND = re.compile(r'"(since|until|from_|to_|start|end)"\s*:\s*([^,}\n]+)')

# What a formatted bound looks like: a call, not a name and not a literal number. `platform_instant(
# x)`, `_iso(x)`, `x.isoformat()` all pass; `since`, `period_start`, `123` do not.
IS_CONVERTED = re.compile(r"\w+\s*\(|\.isoformat\s*\(|\.strftime\s*\(")

# An inline strftime at the call site is the OTHER half of the rule: it works today and puts the
# format in a place the next person will not find when billing changes it.
INLINE_FORMAT = re.compile(r'"(since|until)"\s*:\s*[^,}\n]*\.(strftime|isoformat)\s*\(')


def main() -> int:
    bad: list[str] = []
    checked = 0
    guarded = 0

    files = sorted(SERVICES.rglob("*.py"))
    if not files:
        print(f"{C_R}no service modules found — this gate checked nothing, which is not the same "
              f"as finding nothing wrong{C_N}")
        return 1

    for path in files:
        if "test" in path.parts or path.name.startswith("test_"):
            continue
        rel = path.relative_to(ROOT).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, ValueError, UnicodeDecodeError) as exc:
            bad.append(f"{rel}: cannot read it — {exc}")
            continue
        if not ADDRESSES_PLATFORM.search(text):
            continue
        checked += 1

        for n, line in enumerate(text.splitlines(), 1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            if INLINE_FORMAT.search(line):
                bad.append(f"{rel}:{n}: the format is written at the call site. Put it in a named "
                           f"converter — the next call site will be written by somebody who never "
                           f"reads this line, and billing's format is not ours to scatter")
                continue
            m = A_TIME_BOUND.search(line)
            if not m:
                continue
            key, value = m.group(1), m.group(2).strip()
            if IS_CONVERTED.search(value):
                guarded += 1
                continue
            bad.append(f"{rel}:{n}: `{key}` is sent as `{value}` — a bare value to a platform "
                       f"route that compares ISO-8601 STRINGS. An epoch here does not error: it "
                       f"compares lexicographically, skips every real row, and returns a plausible "
                       f"zero. Pass it through the converter")

    if bad:
        print(f"{C_R}a time bound crosses into the platform unformatted{C_N}")
        for line in bad:
            print(f"  {line}")
        print("\n  See services/operations/app/adapters/settlements.py: `platform_instant`.")
        return 1

    if checked == 0:
        print(f"{C_R}no module addresses a platform admin route — either the route moved or this "
              f"gate no longer matches it, and silence is not agreement{C_N}")
        return 1

    print(f"{C_G}ok{C_N}  {guarded} time bounds across {checked} platform-facing modules, "
          f"every one formatted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
