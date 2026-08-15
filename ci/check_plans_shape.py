#!/usr/bin/env python3
# =============================================================================
# check_plans_shape.py — the price list is a BASE plus APPS, and it stays that way.
#
# WHY A GUARD FOR A DATA FILE. Because entitlements MERGE across every live subscription and
# numbers SUM, the shape of this file is load-bearing in a way a reader would not guess:
#
#   TWO ROWS CARRYING -1 FOR ONE KEY  a shop holding both gets -1 + -1 = -2. `messages.monthly`
#                                     stops meaning «unlimited» and starts meaning nothing. The
#                                     failure appears months later as a refused message, or as a
#                                     meter that never catches our own runaway loop.
#
#   AN APP REPEATING A CAPACITY KEY   `staff.seats` on an app row adds its number to the base's
#                                     every time somebody buys that app. Nobody would notice a
#                                     shop quietly gaining five seats; the invoice does not change.
#
#   A BASE THAT GRANTS NO feature.base  the purchase rules in operations decide «has this shop got
#                                     a base?» from that key, because billing has no route that
#                                     lists a tenant's subscriptions. A base without it can be
#                                     bought twice, and apps can be bought with no base at all.
#
# Every one of these is silent. Nothing errors, nothing logs, and the price list still looks right.
#
# Run:  python ci/check_plans_shape.py
# =============================================================================
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLANS = ROOT / "deploy" / "seed" / "plans.json"

BASE_KEY = "feature.base"
# Keys that describe CAPACITY rather than a feature. They sum by design — that is how a seat pack
# works — which is exactly why an app must never mention one.
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

    bases = [p for p in rows if limit_of((p.get("limits") or {}).get(BASE_KEY, 0))]
    apps = [p for p in rows if p not in bases]

    if not bases:
        problems.append(f"no plan grants {BASE_KEY} — every purchase rule that asks «has this shop "
                        f"got a base?» would answer no, so nothing could ever be bought")

    # ── a value of -1 belongs to exactly one row a shop can hold at a time ────────────────────
    #
    # BASES ARE EXEMPT FROM EACH OTHER, and only because `may_add` in operations refuses a second
    # base — الأساس and المؤسسات are alternatives, never a pair, so both may carry -1. That is a
    # dependency between a data file and a rule in code, and it is stated here so the day somebody
    # relaxes that rule this line is what tells them what else it was holding up.
    unlimited: dict[str, list[str]] = {}
    for plan in rows:
        if plan in bases:
            continue
        for key, value in (plan.get("limits") or {}).items():
            if limit_of(value) == -1:
                unlimited.setdefault(key, []).append(plan["name"])
    # An app row carrying -1 for a key a base also grants is the pair that CAN be held together.
    base_unlimited = {k for p in bases for k, v in (p.get("limits") or {}).items()
                      if limit_of(v) == -1}
    for key in sorted(base_unlimited & set(unlimited)):
        unlimited[key] = unlimited[key] + ["a base"]
    for key, names in sorted(unlimited.items()):
        if len(names) > 1:
            problems.append(f"{key} is -1 in {len(names)} rows ({', '.join(names)}) — a shop "
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

    # ── every base carries every feature key, so 0 means DENY rather than silence ─────────────
    sold = {k for p in rows for k in (p.get("limits") or {}) if k.startswith("feature.")}
    for plan in bases:
        missing = sorted(sold - set(plan.get("limits") or {}))
        if missing:
            problems.append(f"{plan['name']}: does not carry {missing[0]} even as 0 — a key missing "
                            f"everywhere answers NOT_ENTITLED with no reason to show, so the "
                            f"console cannot tell 'not bought' from 'never heard of it'")

    for p in problems:
        print(f"{C_R}  ✗ {p}{C_N}")
    if problems:
        print(f"\n{C_R}  ✗ {len(problems)} problem(s) in the price list's shape{C_N}")
        return 1
    print(f"{C_G}  ✔ {len(bases)} base(s) and {len(apps)} app(s): nothing sums twice, and every "
          f"base answers for every key{C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
