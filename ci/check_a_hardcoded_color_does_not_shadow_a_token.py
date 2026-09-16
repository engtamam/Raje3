"""A component must read a theme colour by variable, never by a copied hex literal.

FOUND TWICE IN ONE SESSION, BOTH TIMES BY THE SAME PATH. `.rj-grid` (apps/console/src/index.css)
and Shop.tsx's own `TOKENS` both hardcoded a hex SNAPSHOT of theme.config.ts's `light` palette
under a comment promising to "follow" it — and both drifted silently the next time that palette
changed, because nothing re-read theme.config.ts; the copy just sat there, correct on the day it
was written and wrong on every day after. `.rj-grid`'s own header even said so about its OWN prior
drift: it was already the second time.

WHAT THIS CHECKS. Every `light` palette hex value in `ui/packages/ui/src/theme/theme.config.ts` is
the one allowed place that literal may appear. Any OTHER file under `apps/` or `ui/` that contains
the exact same hex string is not proof of a bug by itself — a coincidence is possible — but it is
the exact shape of a stale copy, so it is worth a human look every time, not a note someone reads
once and forgets. Scoped to CSS and TS/TSX source only (not test fixtures, not generated output);
theme.config.ts itself is the source of truth and is exempt from matching against its own values.
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
THEME_FILE = ROOT / "ui" / "packages" / "ui" / "src" / "theme" / "theme.config.ts"

SCAN_DIRS = [ROOT / "apps", ROOT / "ui"]
SCAN_EXTS = {".css", ".ts", ".tsx"}
EXCLUDE_PARTS = {"node_modules", "dist", "build", ".git", "coverage"}
# The theme runtime itself legitimately touches raw literals (fallback defaults, applied AS the
# CSS variables this gate tells everyone else to read) — not a copy that can drift unnoticed.
EXCLUDE_FILES = {ROOT / "ui" / "packages" / "ui" / "src" / "theme" / "applyTheme.ts"}

HEX_RE = re.compile(r"#[0-9a-fA-F]{6}\b")

# Only the NEUTRAL scaffold — background, surface, text, border — is judged, matching the two real
# defects this gate exists for. Accent/semantic colours are deliberately excluded: a design that
# reuses a similar-looking hue for its own unrelated purpose (a booking-status colour, a gift
# card's own gold) is a real, separate choice, not a stale snapshot of the shared palette.
NEUTRAL_KEYS = (
    "'surface-0'", "'surface-2'", "'surface-3'",
    "'text-primary'", "'text-secondary'", "'text-muted'",
    "'border-subtle'", "'border-strong'",
)
# Pure white/black are excluded even though `surface-0`/`surface-1` are now genuinely `#ffffff`
# (the 2026-09-16 glossy-white rebrand) — both hexes are used constantly for reasons that have
# nothing to do with tracking a surface token (an SVG fill, a shadow colour, a gradient stop, white
# ink on a coloured button), so matching them would flag that entire, legitimate class as noise
# instead of the two real snapshot-drift bugs this gate exists for.
EXCLUDED_HEXES = {"#ffffff", "#000000"}
LIGHT_BLOCK_RE = re.compile(r"const light: Palette = \{(.*?)\n\};", re.DOTALL)
NEUTRAL_LINE_RE = re.compile(r"^\s*(" + "|".join(re.escape(k) for k in NEUTRAL_KEYS) + r"):\s*'(#[0-9a-fA-F]{6})'")


def _light_palette_hexes() -> set[str]:
    text = THEME_FILE.read_text(encoding="utf-8")
    m = LIGHT_BLOCK_RE.search(text)
    if not m:
        print("could not find `const light: Palette = { ... }` in theme.config.ts — "
              "this gate needs re-pointing")
        sys.exit(1)
    hexes = set()
    for line in m.group(1).splitlines():
        lm = NEUTRAL_LINE_RE.match(line)
        if lm:
            hexes.add(lm.group(2).lower())
    return hexes


def _files():
    for base in SCAN_DIRS:
        for path in base.rglob("*"):
            if path.suffix not in SCAN_EXTS or not path.is_file():
                continue
            if any(part in EXCLUDE_PARTS for part in path.parts):
                continue
            if path == THEME_FILE or path in EXCLUDE_FILES:
                continue
            yield path


def main() -> int:
    tokens = _light_palette_hexes()
    if not tokens:
        print("no hex values found in theme.config.ts's light palette — this gate needs re-pointing")
        return 1

    findings: list[str] = []
    for path in _files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for hexval in HEX_RE.findall(line):
                if hexval.lower() in EXCLUDED_HEXES:
                    continue
                if hexval.lower() in tokens:
                    rel = path.relative_to(ROOT)
                    findings.append(f"{rel}:{lineno}: {hexval} — matches a theme.config.ts light "
                                     f"token literally; read it via var(--...) instead")

    if findings:
        print(f"{len(findings)} hardcoded colour(s) shadow a theme.config.ts token:")
        for line in findings:
            print("  " + line)
        print("\nA literal hex that happens to equal a token's current value is a snapshot, not a "
              "reference — it renders correctly today and silently stops matching the day the "
              "token changes. Read the CSS variable (e.g. var(--surface-0)) instead.")
        return 1

    print(f"{len(tokens)} light-palette token value(s) checked across apps/ and ui/: no hardcoded copies found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
