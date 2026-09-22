#!/usr/bin/env python3
"""No mobile screen may use the `_ios_`-suffixed directional icon family, and every directional
chevron must actually flip with the reading direction — the exact regression class the owner
caught live, twice: a back/forward arrow silently pointing the wrong way.

WHY THIS EXISTS. `Icons.arrow_back_ios_new_rounded`/`Icons.arrow_forward_ios_rounded` were found
live (2026-09-22, this session) to render IDENTICALLY in this app's web build regardless of which
literal the code names — a genuine rendering bug in this environment, not a logic error. The fix
(`AppBackButton`, `account_screen.dart`'s own `_Row` trailing chevron) switched to
`chevron_left_rounded`/`chevron_right_rounded`, chosen on `Directionality.of(context) ==
TextDirection.rtl`. `home_screen.dart` had a THIRD, separate arrow that was never migrated and
still used the broken `_ios_` family — found again live the same day, after the first two were
already fixed. This gate exists so a fourth one is caught automatically instead of live, again.

TWO CHECKS:
  1. The `_ios_` directional family (`arrow_back_ios`, `arrow_back_ios_new`,
     `arrow_back_ios_new_rounded`, `arrow_forward_ios`, `arrow_forward_ios_rounded`) is BANNED
     everywhere in apps/mobile/lib — no exceptions list, because the bug is the glyph family
     itself, not any one screen's use of it.
  2. Every `chevron_left_rounded`/`chevron_right_rounded` pair must appear inside the same
     `Icon(...)` call, close enough together to plausibly be one `Directionality`-driven ternary —
     a lone chevron literal with no sibling is a hardcoded direction that never flips for RTL.

Usage:
    python ci/check_mobile_no_broken_directional_icons.py

Exits 1 and prints every violation if found; exits 0 (silent) if none.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOBILE_LIB = ROOT / "apps" / "mobile" / "lib"

BANNED_ICONS = [
    "arrow_back_ios_new_rounded",
    "arrow_back_ios_new",
    "arrow_back_ios",
    "arrow_forward_ios_rounded",
    "arrow_forward_ios",
]
BANNED_RE = re.compile(r"Icons\.(" + "|".join(BANNED_ICONS) + r")\b")

# One `Icon(...)` call's worth of lookaround — generous enough to span a multi-line ternary,
# tight enough that two unrelated chevrons elsewhere in the same file don't false-pair.
WINDOW = 400


def main() -> int:
    failed = False

    for f in MOBILE_LIB.rglob("*.dart"):
        text = f.read_text(encoding="utf-8")
        rel = f.relative_to(ROOT).as_posix()

        for m in BANNED_RE.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            failed = True
            print(f"✗ {rel}:{line}: Icons.{m.group(1)} is the proven-broken directional icon "
                  f"family (renders identically regardless of which literal is named, found "
                  f"live 2026-09-22) — use chevron_left_rounded/chevron_right_rounded switched "
                  f"on Directionality.of(context) instead, same as AppBackButton")

        for kind in ("chevron_left_rounded", "chevron_right_rounded"):
            other = "chevron_right_rounded" if kind == "chevron_left_rounded" else "chevron_left_rounded"
            for m in re.finditer(rf"Icons\.{kind}\b", text):
                start = max(0, m.start() - WINDOW)
                end = min(len(text), m.end() + WINDOW)
                if other not in text[start:end]:
                    line = text.count("\n", 0, m.start()) + 1
                    failed = True
                    print(f"✗ {rel}:{line}: Icons.{kind} used with no {other} nearby — a "
                          f"hardcoded direction that never flips for RTL; pair it with a "
                          f"Directionality.of(context) == TextDirection.rtl ternary")

    if failed:
        return 1
    print("✔ no broken _ios_ directional icons, every chevron pair present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
