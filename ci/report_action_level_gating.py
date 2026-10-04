#!/usr/bin/env python3
"""PHASE 2 of the permission-gate effort (2026-09-24) — a REPORT, not a CI gate. Never wired
into guards.yml, never exits 1 for a "bad" result — see the module docstring below for why, and
see [[mobile-permission-gate-effort]] in project memory for the full plan this belongs to.

WHAT THIS ANSWERS. Phase 1 built the reusable primitive (`Can`/`CapabilityGate`) both apps now
have for gating one button by one capability. This script answers the question that motivated
building it in the first place: "of the screens that already exist, which ones gate their write
buttons per-action (the `customers_screen.dart`/`Services.tsx` pattern — `catalog.hasAll(...)` /
`action(catalog, id)` checked near real interactive controls) and which ones only gate at the
whole-screen level (the `services_screen.dart`-BEFORE-this-effort pattern — reachable at all, or
not, with no per-button check once inside)?"

WHY A COVERAGE COUNT, NOT A PER-BUTTON VERDICT. The KB-anchor gate this file's structure borrows
from (`check_mobile_screen_actions_are_anchored.py`) can decide "is THIS SPECIFIC button wrapped"
with certainty, because `KbAnchor(...)` is real, trackable Dart syntax with a matching close
paren around the widget it explains. Whether a button's `onPressed`/`onClick` ultimately performs
a WRITE is not something static text scanning can know with the same certainty — the mutation
usually happens several calls deep, inside a `*Service` class method in another file entirely
(`customersService.rename(...)`, not an inline `dio.post(...)`). Pretending to answer that
precisely would produce either false positives that get ignored, or false negatives that hide a
real gap — worse than an honest, coarser signal. So this script counts, per screen file: how many
real interactive controls (`TextButton(`, `ElevatedButton(`, etc. / `onClick=`) it has, and how
many times that same file consults the catalogue at all (`.hasAll(`, `CapabilityGate(`,
`action(catalog,` / `<Can `). A screen with real controls and ZERO catalogue consultations is a
CONFIRMED full gap (that ratio cannot lie); anything else is reported as a ratio for a human to
judge, never auto-failed.

PHASE 3 (not this file) works the confirmed-gap list top to bottom, screen by screen, same "حبة
حبة" discipline this project already used for the mobile CI-gate rollout. PHASE 4 (also not this
file) is the point a stricter, per-button-precise gate — once every real screen is clean — gets
wired into guards.yml as an actual blocker.

Usage:
    python ci/report_action_level_gating.py            # both apps
    python ci/report_action_level_gating.py --mobile    # apps/mobile only
    python ci/report_action_level_gating.py --console   # apps/console only

Always exits 0 — this is a report, read it, it never blocks anything.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOBILE_DIR = ROOT / "apps" / "mobile" / "lib" / "features"
CONSOLE_DIR = ROOT / "apps" / "console" / "src" / "screens"

# Same interactive-control list check_mobile_screen_actions_are_anchored.py already uses —
# TextField/TextFormField excluded on purpose here: a field DISPLAYS/COLLECTS data, a button
# TRIGGERS an action, and this report is about actions specifically.
MOBILE_CONTROLS = (
    "ElevatedButton(", "TextButton(", "OutlinedButton(", "FilledButton(", "IconButton(",
)
MOBILE_GATE_SIGNS = (".hasAll(", "CapabilityGate(")

CONSOLE_GATE_SIGNS = ("action(catalog,", "action(catalog, ", "<Can ")


def _count(text: str, needles: tuple[str, ...]) -> int:
    return sum(text.count(n) for n in needles)


def scan_mobile() -> list[tuple[str, int, int]]:
    """(relative path, control count, gate-sign count) for every mobile screen file that has at
    least one real interactive control."""
    out: list[tuple[str, int, int]] = []
    if not MOBILE_DIR.exists():
        return out
    for path in sorted(MOBILE_DIR.rglob("*.dart")):
        text = path.read_text(encoding="utf-8")
        controls = _count(text, MOBILE_CONTROLS)
        if controls == 0:
            continue
        gates = _count(text, MOBILE_GATE_SIGNS)
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        out.append((rel, controls, gates))
    return out


def scan_console() -> list[tuple[str, int, int]]:
    """Same shape for console screens — `onClick=` as the control signal (JSX has no single
    widget-constructor list the way Dart does)."""
    out: list[tuple[str, int, int]] = []
    if not CONSOLE_DIR.exists():
        return out
    for path in sorted(CONSOLE_DIR.glob("*.tsx")):
        if path.name.endswith(".test.tsx"):
            continue
        text = path.read_text(encoding="utf-8")
        controls = len(re.findall(r"onClick=", text))
        if controls == 0:
            continue
        gates = _count(text, CONSOLE_GATE_SIGNS)
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        out.append((rel, controls, gates))
    return out


def _print_report(title: str, rows: list[tuple[str, int, int]]) -> None:
    print(f"\n▸ {title}")
    if not rows:
        print("  (no screen files with interactive controls found)")
        return
    confirmed_gaps = [r for r in rows if r[2] == 0]
    others = [r for r in rows if r[2] > 0]
    if confirmed_gaps:
        print(f"  ✗ {len(confirmed_gaps)} screen(s) with a CONFIRMED full gap — real controls, "
              f"zero catalogue checks anywhere in the file:")
        for rel, controls, _ in confirmed_gaps:
            print(f"      {rel}  ({controls} control(s), 0 catalogue checks)")
    else:
        print("  ✔ no confirmed full gaps — every screen with real controls checks the "
              "catalogue at least once")
    print(f"  ─ coverage ratio for the other {len(others)} screen(s) (controls : catalogue "
          f"checks — a human call, not an auto-verdict):")
    for rel, controls, gates in sorted(others, key=lambda r: r[2] / r[1]):
        print(f"      {rel}: {controls} control(s), {gates} catalogue check(s)")


def main(argv: list[str]) -> int:
    do_mobile = "--console" not in argv
    do_console = "--mobile" not in argv

    if do_mobile:
        _print_report("mobile (apps/mobile/lib/features/**/*.dart)", scan_mobile())
    if do_console:
        _print_report("console (apps/console/src/screens/*.tsx)", scan_console())

    print("\nThis is PHASE 2 of the permission-gate effort — a report only. Nothing here fails "
          "a build. See project memory [[mobile-permission-gate-effort]] for phase 3/4.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
