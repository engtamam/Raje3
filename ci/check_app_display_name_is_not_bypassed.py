#!/usr/bin/env python3
"""Every screen that touches a billing `Plan`/`Subscription` must read its owner-facing name
through `appDisplayName(plan)` — never a plan's own raw, stored `name` (or a subscription's
`plan_name` snapshot) directly.

WHY THIS GATE EXISTS, FOUND LIVE (2026-09-20). The launcher tile resolves an app's name through
apps.ts's own `AppRow` (the current, owner-facing name — renaming this costs nothing); a billing
plan's own `name` field is the STORED name from the day the row was created and stays that way on
purpose (renaming it would rewrite invoices/receipts that already reference it — a data migration,
not a copy edit; see apps.ts's own «coupons» entry for the full reasoning). The cart bar, the
auto-added-dependency notice, and the billing status pane's renewal/cascade lists all read the raw
`.name`/`.plan_name` straight off the wire instead of going through the tile's own lookup — so a
shop added «تحالف استراتيجي» to its cart and watched it show up there as «كوبونات», the same app
wearing two different names on two halves of one screen.

`appDisplayName(plan)` (billingShared.tsx) is the one lookup every surface must share now — this
gate is what keeps the NEXT screen that reads a plan's name from re-introducing the same drift.

WHY SCOPED TO PLAN/SUBSCRIPTION CONSUMERS ONLY, not every `.name` in the codebase: `.name` is an
extremely common identifier (a person's name, a file's name, a shop's own name) that has nothing
to do with this rule. Scanning only files that import `Plan`/`Subscription` from `billingShared`
keeps the check meaningful without hand-curating a screen list — a file that does not touch a
billing plan at all is simply out of scope, the same reasoning
check_operator_screen_localized.py's own header gives for its curated SCREENS list, applied here
by import graph instead of by hand.

Usage:
    python ci/check_app_display_name_is_not_bypassed.py
    python ci/check_app_display_name_is_not_bypassed.py apps/console/src/launcher/CartBar.tsx

Exits 1 and prints every offending line if a raw name-read remains; exits 0 (silent) if clean.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "apps" / "console" / "src"

# THE DEFINITION SITE AND ITS OWN TEST — the one place `plan.name` is the correct, deliberate
# read (appDisplayName's own fallback, and fixtures constructing a raw Plan to test it with).
EXEMPT_FILES = {
    SRC / "billingShared.tsx",
    SRC / "billingShared.test.ts",
}

IMPORTS_PLAN_TYPE = re.compile(r"import\s*\{[^}]*\b(?:Plan|Subscription)\b[^}]*\}\s*from\s*['\"][^'\"]*billingShared['\"]")

FORBIDDEN = [
    re.compile(r"\bplan\.name\b"),
    re.compile(r"\bp\.name\b"),
    re.compile(r"\.plan_name\b"),
    re.compile(r"\bprovider\.name\b"),
]


def _is_exempt_line(line: str) -> bool:
    stripped = line.strip()
    if stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("/*"):
        return True
    # A LINE THAT ALREADY CALLS THE REAL LOOKUP is exempt even if it ALSO reads a raw name as its
    # own defensive fallback for when a plan cannot be matched at all (BillingStatusPane's own
    # `lineDisplayName`) — the bypass this gate exists to catch is a raw read INSTEAD of the
    # lookup, never a raw read alongside it.
    if "appDisplayName(" in stripped:
        return True
    return False


def _consumes_plan_type(text: str) -> bool:
    return bool(IMPORTS_PLAN_TYPE.search(text))


def scan(path: Path) -> list[tuple[int, str]]:
    text = path.read_text(encoding="utf-8")
    if not _consumes_plan_type(text):
        return []
    hits: list[tuple[int, str]] = []
    for i, line in enumerate(text.splitlines(), start=1):
        if _is_exempt_line(line):
            continue
        if any(p.search(line) for p in FORBIDDEN):
            hits.append((i, line.strip()))
    return hits


def main(argv: list[str]) -> int:
    if argv:
        targets = [ROOT / argv[0]]
    else:
        targets = sorted(p for p in SRC.rglob("*.ts*") if p not in EXEMPT_FILES)

    failed = False
    any_checked = False
    for path in targets:
        if path.resolve() in {p.resolve() for p in EXEMPT_FILES}:
            continue
        hits = scan(path)
        if hits:
            any_checked = True
            failed = True
            print(f"✗ {path.relative_to(ROOT)}: {len(hits)} raw plan-name read(s), use appDisplayName(plan) instead")
            for lineno, line in hits:
                print(f"    {lineno}: {line}")
        elif _consumes_plan_type(path.read_text(encoding="utf-8")):
            any_checked = True
            print(f"✓ {path.relative_to(ROOT)}: clean")

    if not any_checked:
        print("no Plan/Subscription-consuming files found to check")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
