#!/usr/bin/env python3
"""Every interactive widget on a real mobile screen is wrapped in KbAnchor (or IS a
KbHintButton) — the gate check_mobile_kb_anchors_are_covered.py itself cannot provide, since
that one only polices anchors someone already added. This one polices "did anyone forget to add
one in the first place."

WHY THIS EXISTS. "كل شاشة أو عنصر في شاشة لازم له KB" (the owner's own words) — a new button or
field with zero KbAnchor is invisible to the OTHER gate entirely (it never appears in either the
"used" or "declared" set), so it can ship fully unexplained to both the "؟" button and the
assistant's own KB forever, silently. This gate catches it at the moment it's written, not
whenever someone happens to notice.

HOW "WRAPPED" IS DECIDED. Real bracket-depth tracking through each file's text, not a nearby-line
heuristic — KbAnchor's own `child:` is often several lines above the widget it explains (see
visit_screen.dart's own note-toggle field, wrapped once around a whole AnimatedSize subtree). A
target widget counts as covered when its own opening line falls between a `KbAnchor(`'s opening
parenthesis and that same call's matching closing parenthesis.

EXEMPT_LINES holds specific, reasoned exceptions — a control with no real explanation to give
(the "×" that just closes an already-explained field, or a bare "retry" after a network error) —
never a way to silence a real gap.

Usage:
    python ci/check_mobile_screen_actions_are_anchored.py

Exits 1 and prints every unanchored widget found; exits 0 (silent) if everything is covered.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEATURES_DIR = ROOT / "apps" / "mobile" / "lib" / "features"

# Constructors that represent something a user actually interacts with — a widget the assistant
# and the "؟" button should both be able to explain.
TARGET_WIDGETS = (
    "TextFormField(",
    "TextField(",
    "ElevatedButton(",
    "TextButton(",
    "OutlinedButton(",
    "FilledButton(",
    "IconButton(",
)

# path -> {line substrings} deliberately left unanchored, with a real reason each. Match is a
# substring of the OFFENDING LINE (the widget's own opening line), not the whole file.
EXEMPT_LINES: dict[str, set[str]] = {
    "apps/mobile/lib/features/visit/visit_screen.dart": {
        # Closes the note field's own already-anchored editor — nothing new to explain.
        "icon: const Icon(Icons.close_rounded, size: 18, color: AppColors.textMuted)",
        # A generic "try again after a network error" control, the same on every screen that
        # could ever show it — not a feature of THIS screen specifically.
        "OutlinedButton(onPressed: onRetry, child: Text(S.of(context)!.retry))",
    },
}


def _find_anchor_spans(text: str) -> list[tuple[int, int]]:
    """Character-offset (start, end) of every KbAnchor(...) call's own parentheses, via real
    depth tracking — a regex alone can't find a call's OWN matching close paren."""
    spans = []
    for m in re.finditer(r"KbAnchor\(", text):
        start = m.end() - 1  # position of the opening '('
        depth = 0
        i = start
        while i < len(text):
            if text[i] == "(":
                depth += 1
            elif text[i] == ")":
                depth -= 1
                if depth == 0:
                    spans.append((start, i))
                    break
            i += 1
    return spans


def _line_offsets(text: str) -> list[int]:
    """Character offset where each line (1-indexed) begins."""
    offsets = [0]
    for line in text.splitlines(keepends=True):
        offsets.append(offsets[-1] + len(line))
    return offsets


def scan(path: Path) -> list[tuple[int, str]]:
    text = path.read_text(encoding="utf-8")
    if "KbAnchor" not in text and "KbHintButton" not in text and not any(
        w in text for w in TARGET_WIDGETS
    ):
        return []

    spans = _find_anchor_spans(text)
    offsets = _line_offsets(text)
    rel_path = str(path.relative_to(ROOT)).replace("\\", "/")
    exempt = EXEMPT_LINES.get(rel_path, set())

    hits: list[tuple[int, str]] = []
    lines = text.splitlines()
    in_block_comment = False
    for lineno, line in enumerate(lines, start=1):
        stripped = line.strip()
        if in_block_comment:
            if "*/" in stripped:
                in_block_comment = False
            continue
        if stripped.startswith("/*") and "*/" not in stripped:
            in_block_comment = True
            continue
        if stripped.startswith("//") or stripped.startswith("*"):
            continue
        if "KbHintButton(" in line:
            continue  # self-covering — it IS the anchor, not something to wrap again.
        if any(ex in line for ex in exempt):
            continue
        for widget in TARGET_WIDGETS:
            if widget not in line:
                continue
            char_pos = offsets[lineno - 1] + line.index(widget)
            if any(start <= char_pos <= end for start, end in spans):
                continue
            hits.append((lineno, stripped))
    return hits


def main(argv: list[str]) -> int:
    if not FEATURES_DIR.exists():
        print(f"✗ {FEATURES_DIR} does not exist")
        return 2

    failed = False
    total_files = 0
    for path in sorted(FEATURES_DIR.rglob("*.dart")):
        total_files += 1
        hits = scan(path)
        if hits:
            failed = True
            rel = path.relative_to(ROOT)
            print(f"✗ {rel}: {len(hits)} unanchored interactive widget(s)")
            for lineno, text in hits:
                print(f"    {lineno}: {text}")

    if failed:
        return 1
    print(f"✔ every interactive widget across {total_files} screen file(s) is anchored")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
