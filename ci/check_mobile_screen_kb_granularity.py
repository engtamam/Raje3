#!/usr/bin/env python3
"""Every mobile SCREEN's real components — fields, buttons, toggles, rows — each carry their own
KB anchor, never just the screen's own outer wrap. `check_mobile_kb_anchors_are_covered.py`
already guarantees a screen-level `KbAnchor` has a matching mobile_kb.json entry; this gate closes
the layer one below it, across EVERY mobile screen, no exceptions carved out by name.

WHY THIS EXISTS. The owner's own words: "كل مكون على الشاشة كل label/... لها لازم KB زي شاشة
تسجيل الدخول وتسجيل الزيارة" — every label/field on a screen needs its own KB entry, the same
granularity `auth.login`/`visit.register` already have (a phone_field, a password_field, a
submit action, each its own anchor). Found live, 2026-09-22: five real screens
(`account_screen.dart`, `shop_identity_screen.dart`, `branches_screen.dart`,
`branch_detail_screen.dart`, `billing_screen.dart`) each carried exactly ONE `KbAnchor` — the
screen's own outer wrap — while rendering several real fields and buttons the assistant could
never individually explain. The earlier anchor-coverage gate could not catch this: a screen with
only its own coarse anchor still passes that check cleanly.

HEURISTIC, NOT A FULL PARSE. A screen file that both (a) is the canonical location of a
`kind: "screen"` KB entry's anchor, AND (b) contains real interactive widgets
(TextField/TextFormField/ElevatedButton/OutlinedButton/TextButton/IconButton/Switch/
SegmentedButton/FloatingActionButton, or an InkWell/GestureDetector with `onTap:`), must carry
MORE than one `KbAnchor(...)` in that same file — the screen-level one, plus at least one per
real component. A screen legitimately built from ONE single control (rare) is named in
SCREEN_KB_GRANULARITY_EXEMPT below with a real reason, never silently skipped.

Usage:
    python ci/check_mobile_screen_kb_granularity.py

Exits 1 and prints every screen still missing granular KB coverage; exits 0 (silent) otherwise.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOBILE_LIB = ROOT / "apps" / "mobile" / "lib"
KB_FILE = ROOT / "apps" / "mobile" / "assets" / "knowledge" / "mobile_kb.json"

ANCHOR_RE = re.compile(r"KbAnchor\(\s*id:\s*'([^']+)'")
KB_ANCHOR_CALL_RE = re.compile(r"KbAnchor\(")
INTERACTIVE_WIDGET_RE = re.compile(
    r"\b(TextField|TextFormField|ElevatedButton|OutlinedButton|TextButton|IconButton|Switch|"
    r"SegmentedButton|FloatingActionButton)\b|"
    r"\b(?:InkWell|GestureDetector)\([^)]*?onTap:"
)

# Screens legitimately built from ONE real control (or none at all) — a conscious, auditable
# exception, never a silent gap. Add here ONLY with a real reason.
SCREEN_KB_GRANULARITY_EXEMPT: dict[str, str] = {}


def _strip_comment_lines(text: str) -> str:
    out_lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("///"):
            out_lines.append("")
        else:
            out_lines.append(line)
    return "\n".join(out_lines)


def main() -> int:
    kb = json.loads(KB_FILE.read_text(encoding="utf-8"))
    dart_files = list(MOBILE_LIB.rglob("*.dart"))

    # Map every screen-level KB anchor to the file that actually defines it.
    screen_anchor_ids = {eid for eid, e in kb.items() if e.get("kind") == "screen"}
    anchor_to_file: dict[str, Path] = {}
    for f in dart_files:
        text = _strip_comment_lines(f.read_text(encoding="utf-8"))
        for m in ANCHOR_RE.finditer(text):
            aid = m.group(1)
            if aid in screen_anchor_ids:
                anchor_to_file[aid] = f

    failed = False
    for anchor_id in sorted(screen_anchor_ids):
        f = anchor_to_file.get(anchor_id)
        if f is None:
            continue  # check_mobile_kb_anchors_are_covered.py already reports this case
        if anchor_id in SCREEN_KB_GRANULARITY_EXEMPT:
            continue
        text = _strip_comment_lines(f.read_text(encoding="utf-8"))
        anchor_count = len(KB_ANCHOR_CALL_RE.findall(text))
        has_interactive = bool(INTERACTIVE_WIDGET_RE.search(text))
        if has_interactive and anchor_count <= 1:
            failed = True
            rel = f.relative_to(ROOT).as_posix()
            print(f"✗ {anchor_id} ({rel}): only the screen-level KbAnchor exists — add one "
                  f"KbAnchor per real field/button/row, or add a reasoned exemption")

    if failed:
        return 1
    print(f"✔ {len(screen_anchor_ids)} screen(s) checked, every one with real components has "
          f"granular KB coverage")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
