#!/usr/bin/env python3
# =============================================================================
# check_no_filled_tan_controls.py — catch a control filled with the sunken surface tone instead
# of the "hollow" one (white/surface-1 + a border), so this class of bug is never rediscovered by
# a screenshot again.
#
# THE BUG THIS CATCHES, EXACTLY AS IT HAPPENED (2026-09-14). `surface-2` was widened for real
# contrast against the page background (theme.config.ts) — correct, and necessary, since it had
# sat only ~9% darker than the page and every "sunken" surface built on it (an unselected chip, a
# search box, a raw input) was invisible. But every ad-hoc control across the console that used
# `bg-surface-2` as its OWN base fill (not the page's sunken backdrop — a search box, a date/hour/
# amount input, an unselected multi-select chip) suddenly read as "a solid tan block on a tan
# page" once that token deepened — the exact complaint. `Launch.tsx` was fixed by hand, once, by
# grep. `WeekdayPicker.tsx`, a SEPARATE shared component `Launch.tsx` itself calls, carried the
# identical bug and was invisible to that one-file grep. `PackagesTab.tsx` and others still do.
#
# THE FIX IS A CONVENTION, NOT A TOKEN VALUE: a "control" (an input, a chip's UNSELECTED state, a
# button's rest state) is HOLLOW — `bg-surface-1` (white) plus `border border-border-subtle` — the
# same convention `design-system/Field.tsx` already used before any of this. `bg-surface-2` stays
# legitimate for what it always meant elsewhere: a genuinely SUNKEN backdrop a filled/hollow shape
# sits ON TOP of (a Segmented track, a KpiCard icon tile, a dropdown's hover highlight) — never a
# control's own persistent fill. This file does not try to tell the two apart by parsing intent;
# it flags every bare `bg-surface-2` outside the allowlist below and a human decides, the same
# posture check_meta_rules.py already takes for a template row it cannot fully judge alone.
#
# THE SELECTED-STATE COLOUR IS DELIBERATELY NOT THIS FILE'S BUSINESS. `bg-text-primary` (an ink
# inversion) for "this is chosen" is an intentional, previously-reasoned choice
# (rj-ui/Segmented.tsx's own 2026-09-07 docstring: purple stays reserved for "press this button",
# never repeated for "this is selected") — reversing THAT is a design call, not a token bug, and
# this check must never flag it.
#
# Run it after touching any screen or shared component:  python3 ci/check_no_filled_tan_controls.py
# =============================================================================
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TREES = [ROOT / "apps" / "console" / "src", ROOT / "ui" / "packages" / "ui" / "src"]

# A BARE `bg-surface-2`, NEVER `hover:bg-surface-2` (a hover tint is not a persistent fill) and
# never `bg-surface-2/NN` (an opacity-modified track — see the allowlist note below for why those
# still need a human look, just not THIS blunt a match).
_BARE = re.compile(r'(?<!hover:)(?<!focus:)bg-surface-2\b(?!/)')

# FILES WHOSE OWN `bg-surface-2` IS A REASONED, DOCUMENTED CHOICE — a recessed TRACK a filled
# shape sits on top of, not a control's own fill. Read that file's own comment before adding to
# this list; it must name why, the same discipline SLEEPING carries in check_template_fills.py.
ALLOWLIST = {
    # rj-ui/Segmented.tsx's own docstring: "a visibly recessed track" the ACTIVE pill (a real
    # fill, real elevation) sits on; an inactive segment carries no fill of its own at all.
    "apps/console/src/rj-ui/Segmented.tsx",
    # KpiCard's icon tile is a static tinted chip beside a number, never a control a person picks
    # between — the same role a Badge's soft background already plays.
    "ui/packages/ui/src/design-system/KpiCard.tsx",
    # A dropdown/listbox HOVER-HIGHLIGHT and its own trigger's hover state — a transient
    # "you're pointing at this row" tint over an already-white listbox, not a persistent fill on
    # the page itself the way an unselected chip sitting directly on the page is.
    "apps/console/src/rj-ui/FilterMenu.tsx",
    # Skeleton/Toast/Drawer/Modal/EmptyState/ErrorState/Tabs/Badge/Button: a placeholder shimmer,
    # a toast's icon chip, or a transient overlay backdrop — none of them a control at rest on
    # the page a viewer compares against the page colour the way a chip group or a text field is.
    "ui/packages/ui/src/design-system/Skeleton.tsx",
    "ui/packages/ui/src/design-system/Toast.tsx",
    "ui/packages/ui/src/design-system/Drawer.tsx",
    "ui/packages/ui/src/design-system/Modal.tsx",
    "ui/packages/ui/src/design-system/EmptyState.tsx",
    "ui/packages/ui/src/design-system/ErrorState.tsx",
    "ui/packages/ui/src/design-system/Tabs.tsx",
    "ui/packages/ui/src/design-system/Badge.tsx",
    "ui/packages/ui/src/design-system/Button.tsx",
}


def _rel(p: Path) -> str:
    return str(p.relative_to(ROOT)).replace("\\", "/")


def main() -> int:
    hits: list[tuple[str, int, str]] = []
    for tree in TREES:
        for path in sorted(tree.rglob("*.tsx")):
            rel = _rel(path)
            if rel.endswith(".test.tsx") or rel in ALLOWLIST:
                continue
            for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if _BARE.search(line):
                    hits.append((rel, i, line.strip()))

    if not hits:
        print("\033[32m  ✔ no control fills bg-surface-2 outside the allowlisted, "
              "reasoned exceptions\033[0m")
        return 0

    by_file: dict[str, int] = {}
    for rel, _, _ in hits:
        by_file[rel] = by_file.get(rel, 0) + 1
    print(f"\033[31m  ✗ {len(hits)} bare bg-surface-2 fill(s) across {len(by_file)} "
          f"file(s) — a control filled tan on a tan page, not a hollow white+border one:\033[0m")
    for rel, count in sorted(by_file.items(), key=lambda kv: -kv[1]):
        print(f"    {rel}: {count}")
    print("\n  Each one is either: (a) a control that should be "
          "`bg-surface-1 border border-border-subtle` instead, or (b) a genuinely sunken track a "
          "human should add to ALLOWLIST above with the SAME reasoning rj-ui/Segmented.tsx's own "
          "comment gives — never silenced without one.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
