#!/usr/bin/env python3
"""A screen migrated to operator-i18n must carry NO raw Arabic string outside t('key') calls —
this is the exhaustive checklist during migration, and the permanent CI gate afterward.

WHY A REGEX OVER THE ARABIC UNICODE RANGE, not a list of known strings: every hardcoded Arabic
literal in a screen's SOURCE is caught this way regardless of which runtime branch renders it —
loading state, error state, an empty list, a validation message — because they all exist as
static text in the file whether or not that branch ever executes during a manual click-through.
Same idiom `apps/console/src/api.ts`'s own `sentenceFor` already uses to detect a server's Arabic
sentence (`/[؀-ۿ]/`).

Usage:
    python ci/check_operator_screen_localized.py apps/console/src/screens/Visit.tsx
    python ci/check_operator_screen_localized.py --all   # every screen in SCREENS below

Exits 1 and prints every offending line if any raw Arabic text remains; exits 0 (silent) if clean.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Screens in scope for operator-i18n migration (current phase). Add a path here once its
# migration starts — an unlisted screen is not yet expected to be clean, so `--all` never flags
# work nobody has begun.
SCREENS = [
    "apps/console/src/screens/Visit.tsx",
    "apps/console/src/screens/Bookings.tsx",
    "apps/console/src/screens/Services.tsx",
    "apps/console/src/screens/ServicesImportDrawer.tsx",
    "apps/console/src/screens/Points.tsx",
]

ARABIC = re.compile(r"[؀-ۿ]")
# Arabic-Indic digits inside a REGEX CHARACTER CLASS — e.g. `/[0-9٠-٩]/` — are code, not display
# text: this screen deliberately accepts a plate typed on an Arabic keyboard (see formatPlate's
# own header). A digit range is not a string a translator would ever touch.
REGEX_DIGIT_CLASS = re.compile(r"\[[^\]]*[٠-٩][^\]]*\]")


def _is_exempt(line: str) -> bool:
    stripped = line.strip()
    if stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("/*"):
        return True
    # A t('...') CALL ARGUMENT MAY LEGITIMATELY EMBED ARABIC — the key itself, or a literal
    # fallback default the call supplies (`t(x, 'نص افتراضي')`) is authored content already
    # routed through the dictionary lookup, not a bypass of it.
    if re.search(r"\bt\(", stripped):
        return True
    if REGEX_DIGIT_CLASS.search(stripped) and not re.search(r"[،-ۿ]", REGEX_DIGIT_CLASS.sub("", stripped)):
        return True
    return False


def scan(path: Path) -> list[tuple[int, str]]:
    hits: list[tuple[int, str]] = []
    in_block_comment = False
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        # A MULTI-LINE /** ... */ COMMENT, this codebase's own house style: only the FIRST line
        # opens with `/**`, and continuation lines carry no `*` prefix at all (see this repo's
        # header comments throughout) — so a comment's own quoted Arabic term ("«عملائي»") on a
        # continuation line is not a screen string, and must be exempt the same as an opening or
        # `*`-prefixed line already is.
        if in_block_comment:
            if "*/" in stripped:
                in_block_comment = False
            continue
        # `{/* ... */}` — the JSX comment form, opening mid-line with `{` rather than at column 0.
        if stripped.startswith("/**") or stripped.startswith("/*") or stripped.startswith("{/*"):
            if "*/" not in stripped:
                in_block_comment = True
            continue
        if ARABIC.search(line) and not _is_exempt(line):
            hits.append((i, line.strip()))
    return hits


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    targets = [ROOT / s for s in SCREENS] if argv[0] == "--all" else [ROOT / argv[0]]
    failed = False
    for path in targets:
        hits = scan(path)
        if hits:
            failed = True
            print(f"✗ {path.relative_to(ROOT)}: {len(hits)} raw Arabic string(s) outside t()")
            for lineno, text in hits:
                print(f"    {lineno}: {text}")
        else:
            print(f"✓ {path.relative_to(ROOT)}: clean")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
