#!/usr/bin/env python3
# =============================================================================
# check_listed_apps_are_wired.py — a SOLD, LISTED app must be DISPLAYED somewhere a shop and an
# admin can actually find it.
#
# THE FAILURE THIS CATCHES, TWICE, THE SAME DAY (2026-09-08). Two apps — التقييم (feature.rating,
# 9900) and بوت خدمة العملاء الذكي (feature.whatsapp, 19900) — had their plan.json row flipped to
# `listed: true`: priced, sold, fully built and enforced. Neither one ever appeared in the
# console's app store OR the platform admin panel, because operations/app/core/apps.py's APPS
# tuple — the ONE list every "what can this shop buy/see" screen reads from — was never updated.
# The comment explaining why the row did not exist YET was left in place after the "yet" became
# "now": a plan flip and a code row are two halves of one change, and nothing compared them.
#
# check_entitlements.py does NOT catch this — by design, correctly: it verifies a sold key is
# ENFORCED somewhere real (a service that refuses without it), and apps.py is explicitly excluded
# from counting as enforcement (DISPLAY_ONLY there) because a console lock is a suggestion, never
# a gate. Both apps WERE enforced the whole time. This is a different promise: a shop that can buy
# something must be able to SEE that it exists to buy, and an admin reviewing what is sold must
# see the same list. That promise has exactly one place it can be kept — this file — and nothing
# checked it until now.
#
# THE RULE: every plan row in plans.json with `listed: true` and EXACTLY ONE `feature.*` key
# (a single-feature app or standalone product — never a bundle like الأساس/المؤسسات, which sell
# every feature key at once and are never meant to appear as one app tile) must have that key
# present in apps.py's APPS tuple.
#
# ONE DIRECTION ONLY, DELIBERATELY. The reverse — a row in APPS with no matching standalone
# listed plan — is NOT automatically a bug: feature.campaigns/feature.loyalty/
# feature.insights.engine are all granted for free inside الأساس (the base plan) and correctly
# still get a row here so the console can show/lock them, even though their own standalone plan
# rows are unlisted (superseded by bundling, not withdrawn). A gate that failed on that shape
# would be exactly the kind of false-positive noise that gets a real check muted; catch the
# failure that actually happened twice, not a plausible-sounding second one nobody has seen.
# =============================================================================
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLANS = ROOT / "deploy" / "seed" / "plans.json"
APPS_PY = ROOT / "services" / "operations" / "app" / "core" / "apps.py"

C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"


def listed_single_feature_apps() -> dict[str, str]:
    """key -> plan name, for every listed plan selling exactly one feature.* key."""
    data = json.loads(PLANS.read_text(encoding="utf-8"))
    rows = data["plans"] if isinstance(data, dict) else data
    out: dict[str, str] = {}
    for plan in rows:
        if not plan.get("listed"):
            continue
        fkeys = [k for k in (plan.get("limits") or {}) if k.startswith("feature.")]
        if len(fkeys) == 1:
            out[fkeys[0]] = str(plan.get("name") or "?")
    return out


def apps_tuple_keys() -> set[str]:
    """Parsed with `ast`, not imported — this file must run with no service's own dependencies
    installed, the same reason every other structural gate in this directory parses rather than
    imports."""
    tree = ast.parse(APPS_PY.read_text(encoding="utf-8"), filename=str(APPS_PY))
    keys: set[str] = set()
    for node in ast.walk(tree):
        # `APPS: tuple[dict[str, Any], ...] = (...)` is an AnnAssign (it carries a type
        # annotation), never a plain Assign — the first version of this parser missed every key
        # by matching only Assign, which is the exact silent-false-green shape this whole file
        # exists to prevent everywhere else; caught by actually running it before trusting it.
        is_apps = (
            (isinstance(node, ast.Assign)
             and any(isinstance(t, ast.Name) and t.id == "APPS" for t in node.targets))
            or (isinstance(node, ast.AnnAssign)
                and isinstance(node.target, ast.Name) and node.target.id == "APPS"))
        if not is_apps or node.value is None:
            continue
        for elt in node.value.elts:  # type: ignore[attr-defined]
            for k, v in zip(elt.keys, elt.values):  # type: ignore[attr-defined]
                if isinstance(k, ast.Constant) and k.value == "key" \
                        and isinstance(v, ast.Constant):
                    keys.add(v.value)
    return keys


def main() -> int:
    sold = listed_single_feature_apps()
    displayed = apps_tuple_keys()

    problems: list[str] = []
    for key, name in sorted(sold.items()):
        if key not in displayed:
            problems.append(
                f"{key!r} (plan {name!r}, listed:true, sold) has no row in apps.py's APPS "
                f"tuple — no shop and no admin can see this app exists to buy it")

    if problems:
        print(f"{C_R}  ✗ {len(problems)} listed-app wiring problem(s):{C_N}")
        for p in problems:
            print(f"    {C_R}{p}{C_N}")
        return 1

    print(f"{C_G}  ✔ every listed single-feature app has a display row, and every display row "
         f"is actually sellable{C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
