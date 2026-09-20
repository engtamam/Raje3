#!/usr/bin/env python3
"""Every mobile KB anchor used in code has a KB entry, and every KB entry's anchor is still
used somewhere in code — drift caught in BOTH directions, the same shape
check_app_display_name_is_not_bypassed.py already polices for plan display names.

WHY BOTH DIRECTIONS. A widget wired to `KbAnchor(id: '...')`/`KbHintButton(anchor: '...')` with
no matching mobile_kb.json entry means a real button or field the assistant (and the "؟" icon)
cannot explain — the exact gap the owner asked this gate to close. A KB entry whose anchor no
widget references any more means a screen changed shape and nobody removed its now-stale
explanation — the KB quietly describing something that no longer exists.

Usage:
    python ci/check_mobile_kb_anchors_are_covered.py

Exits 1 and prints every mismatch if found; exits 0 (silent) if the two sides agree exactly.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOBILE_LIB = ROOT / "apps" / "mobile" / "lib"
KB_FILE = ROOT / "apps" / "mobile" / "assets" / "knowledge" / "mobile_kb.json"

ANCHOR_PATTERNS = [
    re.compile(r"KbAnchor\(\s*id:\s*'([^']+)'"),
    re.compile(r"KbHintButton\(anchor:\s*'([^']+)'"),
]


def _strip_comment_lines(text: str) -> str:
    """Blank out `//`/`*`-led comment lines while keeping every other line's position —
    KbAnchor(...) spans a couple of real lines, so this must stay whole-file text, not
    per-line matching, or the id: on the line after `KbAnchor(` would never be seen."""
    return "\n".join(
        "" if line.strip().startswith(("//", "*")) else line for line in text.splitlines()
    )


def code_anchors() -> dict[str, list[str]]:
    """anchor -> list of files it's referenced from. Comment lines are blanked first — a doc
    comment illustrating the pattern (this file's own KbAnchor/kb_hint_button.dart headers)
    must never count as a real usage."""
    found: dict[str, list[str]] = {}
    for path in MOBILE_LIB.rglob("*.dart"):
        text = _strip_comment_lines(path.read_text(encoding="utf-8"))
        for pattern in ANCHOR_PATTERNS:
            for m in pattern.finditer(text):
                found.setdefault(m.group(1), []).append(str(path.relative_to(ROOT)))
    return found


def kb_anchors() -> dict[str, str]:
    """anchor -> KB entry id that declares it."""
    raw = json.loads(KB_FILE.read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for entry_id, entry in raw.items():
        anchor = (entry.get("anchor") or "").strip()
        if anchor:
            out[anchor] = entry_id
    return out


def main() -> int:
    used = code_anchors()
    declared = kb_anchors()

    missing_kb = sorted(set(used) - set(declared))
    orphaned_kb = sorted(set(declared) - set(used))

    failed = False
    if missing_kb:
        failed = True
        print("✗ anchors used in code with no mobile_kb.json entry:")
        for anchor in missing_kb:
            files = ", ".join(used[anchor])
            print(f"    {anchor}  (used in: {files})")

    if orphaned_kb:
        failed = True
        print("✗ mobile_kb.json entries whose anchor no widget references any more:")
        for anchor in orphaned_kb:
            print(f"    {anchor}  (entry: {declared[anchor]})")

    if failed:
        return 1

    print(f"✔ {len(used)} anchor(s) in code, all covered by mobile_kb.json, no orphans")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
