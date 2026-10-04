#!/usr/bin/env python3
"""Every mobile assistant ACTION points at a real route and a real KB entry, and every
screen-level KB entry either has a real action or an explicit, reasoned exemption — the same
two-way drift discipline check_mobile_kb_anchors_are_covered.py already applies one layer down.

WHY THIS EXISTS. "الأفعال يكون سهل إضافتها وحذفها بمرونة عالية، وأي تعديل على الشاشات لازم
يلزمه تعديل على الـKB والأفعال" (the owner's own words): adding/removing an action must be as
easy as editing one JSON entry, and NO screen change may quietly leave the assistant's own
action list stale. Three checks:

  1. action.route must be a route name the router ACTUALLY defines today (RouteNames.* constant
     values, or a kNavSections id used as a GoRoute name) — an action pointing at a renamed or
     removed route is a silent dead action nobody would notice without this.
  2. action.kb_entry must be a real assets/knowledge/mobile_kb.json id — an action with no
     matching explanation is a capability the assistant can invoke but never describe.
  3. Every mobile_kb.json entry with "kind": "screen" must be covered by SOME action, unless it
     is named in SCREEN_ACTION_EXEMPT below with a real reason. Adding a new screen's KB entry
     without deciding whether it should be voice-reachable fails the build — the decision must
     be made and recorded, never silently skipped either way.

Usage:
    python ci/check_mobile_actions_are_covered.py

Exits 1 and prints every mismatch if found; exits 0 (silent) if everything lines up.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOBILE_LIB = ROOT / "apps" / "mobile" / "lib"
ACTIONS_FILE = ROOT / "apps" / "mobile" / "assets" / "knowledge" / "mobile_actions.json"
KB_FILE = ROOT / "apps" / "mobile" / "assets" / "knowledge" / "mobile_kb.json"
ROUTE_NAMES_FILE = MOBILE_LIB / "core" / "router" / "route_names.dart"
NAV_SECTIONS_FILE = MOBILE_LIB / "core" / "nav" / "nav_sections.g.dart"

# Screen-level KB entries deliberately NOT reachable by a navigate action, and why — a
# conscious, auditable decision, never a silent gap. Add here ONLY with a real reason.
SCREEN_ACTION_EXEMPT = {
    "auth.login": "pre-auth screen — the assistant itself only exists once signed in, so "
                  "there is no session that could ever ask to navigate here",
    "auth.signup": "same as auth.login — pre-auth, never a voice destination",
    "auth.verify_phone": "a mid-flow detour reached only via a real signup/login refusal, "
                          "never something a signed-in session navigates to on purpose",
    "account.shop.branches.detail": "needs a specific branchId chosen from the branches list — "
                                     "not a fixed voice destination itself, reached only by "
                                     "picking a branch from account.shop.branches",
    "customer_detail": "needs a specific customerId chosen from the customers list — not a "
                        "fixed voice destination itself, reached only by picking a customer "
                        "from customers",
}


def real_route_names() -> set[str]:
    names: set[str] = set()
    if ROUTE_NAMES_FILE.exists():
        for m in re.finditer(r"static const String \w+ = '([^']+)';", ROUTE_NAMES_FILE.read_text(encoding="utf-8")):
            names.add(m.group(1))
    if NAV_SECTIONS_FILE.exists():
        for m in re.finditer(r"id:\s*'([^']+)'", NAV_SECTIONS_FILE.read_text(encoding="utf-8")):
            names.add(m.group(1))
    return names


def main() -> int:
    actions = json.loads(ACTIONS_FILE.read_text(encoding="utf-8"))
    kb = json.loads(KB_FILE.read_text(encoding="utf-8"))
    routes = real_route_names()

    failed = False

    for action_id, action in actions.items():
        # route is only required for scope "navigation" (enforced at parse time on the Dart
        # side) — a "system"/"app" action legitimately has none, and has nothing to check here.
        route = action.get("route")
        if route is not None and route not in routes:
            failed = True
            print(f"✗ {action_id}: route '{route}' is not a route this app's router actually defines")
        kb_entry = action.get("kb_entry", "")
        if kb_entry not in kb:
            failed = True
            print(f"✗ {action_id}: kb_entry '{kb_entry}' does not exist in mobile_kb.json")

    actioned_kb_entries = {a.get("kb_entry") for a in actions.values()}
    for entry_id, entry in kb.items():
        if entry.get("kind") != "screen":
            continue
        if entry_id in actioned_kb_entries:
            continue
        if entry_id in SCREEN_ACTION_EXEMPT:
            continue
        failed = True
        print(f"✗ {entry_id}: a screen-level KB entry with no action and no exemption — "
              f"add a navigate action, or add it to SCREEN_ACTION_EXEMPT with a real reason")

    if failed:
        return 1

    print(f"✔ {len(actions)} action(s) covered, all screen-level KB entries decided (action or exempt)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
