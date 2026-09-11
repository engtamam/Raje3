#!/usr/bin/env python3
# =============================================================================
# check_plans_shape.py — the price list is APPS, standalone, and it stays that way.
#
# NO BASE EXISTS ANY MORE — retired twice over: الأساس (2026-09-10, "apps only" decision) and
# المؤسسات (2026-09-11, the enterprise-shop shape rejected outright — "غير مناسب لوضعنا ولا طريقة
# عملينا"). Every plan left is bought on its own, and `messages.monthly` — the OLD marker that once
# made a row "a base" (operations' `core/subscribe.py::is_base` read it that way off a
# subscription's own snapshot) — is granted by NOTHING here now, and that is not a gap to close:
# billing's `consume()` never gates a send on this key regardless of what it resolves to
# (services/reminders/app/core/quota.py's own header). This gate used to require at least one
# base row to exist; it no longer does, because the product it was guarding no longer exists.
#
# WHY A GUARD FOR A DATA FILE STILL, THEN. Because entitlements MERGE across every live
# subscription and numbers SUM, the shape of this file is still load-bearing in ways a reader
# would not guess:
#
#   TWO ROWS CARRYING -1 FOR THE SAME KEY  a shop holding both gets -1 + -1 = -2, and a value
#                                          meant to read «unlimited» starts meaning nothing.
#
#   AN APP ROW REPEATING A CAPACITY KEY    `staff.seats`/`branches` sum by design (that is how the
#                                          capacity add-ons work) — a FEATURE row must never also
#                                          carry one, or buying that feature quietly adds seats.
#
# Every one of these is silent. Nothing errors, nothing logs, and the price list still looks right.
#
# Run:  python ci/check_plans_shape.py
# =============================================================================
from __future__ import annotations

import json
import sys
from pathlib import Path

#: billing-service's own sentinel (platform/.../entitlement_merge.py). Ours must be the same word.
UNLIMITED = "unlimited"

ROOT = Path(__file__).resolve().parent.parent
PLANS = ROOT / "deploy" / "seed" / "plans.json"

# Keys that describe CAPACITY rather than a feature. They sum by design — that is how a seat pack
# works — which is exactly why a feature row must never mention one.
CAPACITY = ("staff.seats", "branches")

C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"


def limit_of(value) -> int | None:
    raw = value.get("limit") if isinstance(value, dict) else value
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def main() -> int:
    data = json.loads(PLANS.read_text(encoding="utf-8"))
    rows = [p for p in data["plans"] if isinstance(p, dict) and p.get("name")]
    problems: list[str] = []

    # EVERY ROW IS AN APP NOW — no base concept survives (see this file's own header). A "base"
    # variable stays out of this function entirely rather than an always-empty list some later
    # line might start branching on again by habit.
    apps = rows

    # ── a value of -1 belongs to exactly one row a shop can hold at a time ────────────────────
    #
    # THE SENTINEL IS billing'S OWN WORD, AND THIS CHECK WENT BLIND THE DAY WE ADOPTED IT.
    #
    # It hunted `-1`, which is what we used to seed. billing's merge does not know that number: it
    # SUMS it, so «المؤسسات» plus a capacity pack came out at 9 seats and two bases at -2 messages,
    # which refuses every send. The value is now the word `unlimited`, which its merge treats as
    # beating every arithmetic — and a check still looking for -1 would pass a file full of them.
    #
    # Both are recognised: the word, because it is what we write, and -1, because a row seeded
    # before the change is still a row a shop can hold, and it must not slip through unpaired.
    def is_unlimited(value: object) -> bool:
        return limit_of(value) in (-1, UNLIMITED)

    # AND -1 IS REFUSED OUTRIGHT, wherever it appears. It is not a smaller unlimited; it is a
    # number that billing will add to another number.
    for plan in rows:
        for key, value in (plan.get("limits") or {}).items():
            if limit_of(value) == -1:
                problems.append(f"{plan['name']}: {key} is -1 — billing has no such sentinel and "
                                f"SUMS it. Write the word {UNLIMITED!r}, which its merge treats as "
                                f"beating every arithmetic")

    unlimited: dict[str, list[str]] = {}
    for plan in rows:
        for key, value in (plan.get("limits") or {}).items():
            if is_unlimited(value):
                unlimited.setdefault(key, []).append(plan["name"])
    for key, names in sorted(unlimited.items()):
        if len(names) > 1:
            problems.append(f"{key} is unlimited in {len(names)} rows ({', '.join(names)}) — a shop "
                            f"holding two of them sums to -2, and 'unlimited' becomes a number "
                            f"that means nothing")

    # ── an app row grants ONE feature and nothing else that adds up ───────────────────────────
    for plan in apps:
        limits = plan.get("limits") or {}
        features = [k for k in limits if k.startswith("feature.") and limit_of(limits[k])]
        capacity = [k for k in limits if k in CAPACITY]
        if features and capacity:
            problems.append(f"{plan['name']}: grants a feature AND {capacity[0]} — the capacity "
                            f"number is ADDED to the base's every time this row is bought, and "
                            f"nothing anywhere reports the drift")
        if len(features) > 1:
            problems.append(f"{plan['name']}: grants {len(features)} features ({', '.join(features)})"
                            f" — an app is one thing bought once, and the purchase rule that "
                            f"refuses a second copy keys on exactly one")
        if not features and not capacity:
            problems.append(f"{plan['name']}: grants nothing at all — it can be bought and changes "
                            f"nothing about what the shop may do")

    for p in problems:
        print(f"{C_R}  ✗ {p}{C_N}")
    if problems:
        print(f"\n{C_R}  ✗ {len(problems)} problem(s) in the price list's shape{C_N}")
        return 1
    print(f"{C_G}  ✔ {len(apps)} plan(s), every one standalone: nothing sums twice{C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
