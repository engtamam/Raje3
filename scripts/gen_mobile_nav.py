#!/usr/bin/env python3
"""Generate apps/mobile/lib/core/nav/nav_sections.g.dart FROM the same
source of truth the web console already uses — apps/console/src/nav.ts's
`SECTIONS` array.

WHY A GENERATOR, NOT A HAND COPY. The web console derives its whole
navigation from `SECTIONS` + `visibleSections()` (which filters on
`hasAll(catalog, ...section.requires)`) — no `if (role === …)` anywhere.
A hand-written Dart list of "the sections the app can show" would be a
second copy of that same decision, and the copy is the one that goes
stale: a section added, renamed, or re-gated in nav.ts would need someone
to remember to also update a Dart file nobody is looking at when they
touch nav.ts. This script closes that hole the same way
gen_mobile_theme.py already closes it for colour tokens: derive the Dart
file from the TS source, and fail CI if the checked-in file disagrees
with what the generator currently produces.

HOW IT READS nav.ts FROM PYTHON. Same technique gen_mobile_theme.py already
uses for theme.config.ts: no TS parser, no Node toolchain — a regex finds
the `export const SECTIONS: Section[] = [ ... ];` block, then a brace-depth
scan (not a second regex) splits it into one `{ ... }` object literal per
section, because those literals can span multiple lines and nest an array
(`requires: [...]`). Each object literal is then read with small per-field
regexes.

SCOPE: only the fields a Dart-side visibleSections()-equivalent needs to
filter and render a row — id, path, label, an icon name mapped to a
Flutter-appropriate Material icon, and `requires`. Anything nav.ts
computes only for the web rail (icon *component*, `service`/`accent`) is
translated, not dropped silently — `service` is kept (same "hide if its
service is unreachable" rule the web applies), `accent` is dropped: the
mobile shell reads colours from AppColors, never from NAV_ACCENTS.

Usage:
    python scripts/gen_mobile_nav.py            # writes the .g.dart file
    python scripts/gen_mobile_nav.py --check     # exits 1 if the file would change (no write)
    python scripts/gen_mobile_nav.py --print     # prints the generated content to stdout
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAV_TS = ROOT / "apps" / "console" / "src" / "nav.ts"
OUTPUT = ROOT / "apps" / "mobile" / "lib" / "core" / "nav" / "nav_sections.g.dart"

SECTIONS_START_RE = re.compile(r"export const SECTIONS: Section\[\] = \[")

# lucide-react icon name -> Flutter Material icon constant. Only icons
# actually used by SECTIONS below need an entry; an unmapped icon fails
# the generator loudly rather than silently falling back to something
# wrong on a phone.
ICON_MAP = {
    "ClipboardPlus": "Icons.assignment_turned_in_outlined",
    "TrendingUp": "Icons.trending_up",
    "CalendarClock": "Icons.calendar_month_outlined",
    "Users": "Icons.people_outline",
    "Star": "Icons.star_outline",
    "Handshake": "Icons.handshake_outlined",
    "Truck": "Icons.local_shipping_outlined",
    "Wrench": "Icons.build_outlined",
    "Megaphone": "Icons.campaign_outlined",
    "Gift": "Icons.card_giftcard_outlined",
    "LifeBuoy": "Icons.support_outlined",
}


def _extract_sections_block(text: str) -> str:
    m = SECTIONS_START_RE.search(text)
    if not m:
        raise RuntimeError(
            f"could not find `export const SECTIONS: Section[] = [` in {NAV_TS} — "
            "this generator needs re-pointing, not a hand-edit of its output"
        )
    start = m.end()
    depth = 1  # we're already inside the outer '['
    i = start
    while depth > 0:
        c = text[i]
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
        i += 1
    return text[start:i - 1]


def _split_object_literals(block: str) -> list[str]:
    """Split the SECTIONS array body into its top-level `{ ... }` entries,
    by brace depth — tolerant of nested arrays (`requires: [...]`) and of
    single-quoted strings containing braces (none do today, but a naive
    string search for '}' would be wrong the day one does)."""
    entries: list[str] = []
    depth = 0
    cur_start = None
    for i, c in enumerate(block):
        if c == "{":
            if depth == 0:
                cur_start = i
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0 and cur_start is not None:
                entries.append(block[cur_start:i + 1])
                cur_start = None
    return entries


def _field(pattern: str, entry: str, required: bool = True) -> str | None:
    m = re.search(pattern, entry)
    if m:
        return m.group(1)
    if required:
        raise RuntimeError(f"could not extract field (pattern {pattern!r}) from entry:\n{entry}")
    return None


def _extract_requires(entry: str) -> list[str]:
    m = re.search(r"requires:\s*\[([^\]]*)\]", entry)
    if not m:
        raise RuntimeError(f"could not extract `requires` from entry:\n{entry}")
    inner = m.group(1).strip()
    if not inner:
        return []
    return [s.strip().strip("'\"") for s in inner.split(",") if s.strip()]


def parse_sections() -> list[dict]:
    text = NAV_TS.read_text(encoding="utf-8")
    block = _extract_sections_block(text)
    sections = []
    for entry in _split_object_literals(block):
        service = _field(r"service:\s*'([^']+)'", entry, required=False)
        section_id = _field(r"\bid:\s*'([^']+)'", entry)
        path = _field(r"\bpath:\s*'([^']+)'", entry)
        label = _field(r"\blabel:\s*'([^']+)'", entry)
        icon = _field(r"\bicon:\s*(\w+)", entry)
        requires = _extract_requires(entry)
        if icon not in ICON_MAP:
            raise RuntimeError(
                f"nav.ts icon {icon!r} (section {section_id!r}) has no Flutter mapping — "
                f"add it to ICON_MAP in {Path(__file__).name}"
            )
        sections.append({
            "service": service,
            "id": section_id,
            "path": path,
            "label": label,
            "icon": ICON_MAP[icon],
            "requires": requires,
        })
    if not sections:
        raise RuntimeError(f"parsed zero sections out of {NAV_TS} — extraction is broken")
    return sections


def _dart_string_list(values: list[str]) -> str:
    return "[" + ", ".join(f"'{v}'" for v in values) + "]"


def generate() -> str:
    sections = parse_sections()

    lines: list[str] = []
    lines.append("// GENERATED FILE — DO NOT EDIT BY HAND.")
    lines.append("//")
    lines.append("// Produced by scripts/gen_mobile_nav.py from:")
    lines.append("//   - apps/console/src/nav.ts (the `SECTIONS` array)")
    lines.append("//")
    lines.append("// Re-run `python scripts/gen_mobile_nav.py` after nav.ts changes.")
    lines.append("// ci/check_mobile_nav_is_generated.py fails the build if this file drifts")
    lines.append("// from what the generator would currently produce.")
    lines.append("//")
    lines.append("// THE ORDER IS THE PRODUCT'S ARGUMENT, exactly as nav.ts's own header says —")
    lines.append("// this list is in the SAME order as SECTIONS in nav.ts, and that order is what")
    lines.append("// both the default landing screen and the default pin priority read.")
    lines.append("")
    lines.append("import 'package:flutter/material.dart';")
    lines.append("")
    lines.append("/// One navigable section, as nav.ts's own `Section` interface declares it —")
    lines.append("/// see that file for the full reasoning (capability-derived nav, no role checks).")
    lines.append("class NavSectionDef {")
    lines.append("  final String id;")
    lines.append("  final String path;")
    lines.append("  final String label;")
    lines.append("  final IconData icon;")
    lines.append("  /// Every id must be present in the fetched catalogue for this section to show.")
    lines.append("  /// Empty = always available (mirrors nav.ts's own `requires: []` rule).")
    lines.append("  final List<String> requires;")
    lines.append("  /// Which service provides its actions — a down service hides nothing (mirrors")
    lines.append("  /// nav.ts's own `unreachable` handling), this is carried for parity/telemetry only.")
    lines.append("  final String? service;")
    lines.append("")
    lines.append("  const NavSectionDef({")
    lines.append("    required this.id,")
    lines.append("    required this.path,")
    lines.append("    required this.label,")
    lines.append("    required this.icon,")
    lines.append("    required this.requires,")
    lines.append("    this.service,")
    lines.append("  });")
    lines.append("}")
    lines.append("")
    lines.append("/// SAME ORDER, SAME IDS AND `requires` AS nav.ts's `SECTIONS` — do not reorder")
    lines.append("/// or hand-edit; re-run the generator instead.")
    lines.append("const List<NavSectionDef> kNavSections = [")
    for s in sections:
        service_lit = f"'{s['service']}'" if s["service"] else "null"
        lines.append("  NavSectionDef(")
        lines.append(f"    id: '{s['id']}',")
        lines.append(f"    path: '{s['path']}',")
        lines.append(f"    label: '{s['label']}',")
        lines.append(f"    icon: {s['icon']},")
        lines.append(f"    requires: {_dart_string_list(s['requires'])},")
        lines.append(f"    service: {service_lit},")
        lines.append("  ),")
    lines.append("];")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    content = generate()

    if "--print" in argv:
        print(content)
        return 0

    if "--check" in argv:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else None
        if current != content:
            print(f"{OUTPUT} is out of date with nav.ts — "
                  f"run `python scripts/gen_mobile_nav.py` and commit the result")
            return 1
        print(f"{OUTPUT} is up to date")
        return 0

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(content, encoding="utf-8", newline="\n")
    print(f"wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
