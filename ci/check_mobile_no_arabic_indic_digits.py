#!/usr/bin/env python3
"""No mobile `.arb` translation string may contain an Eastern Arabic-Indic digit (٠-٩) or the
Urdu/Extended-Arabic-Indic variant (۰-۹) — this app's own standing rule is Western digits (0-9)
everywhere, even inside Arabic text (core/utils/formatters.dart's own `_westernDigits` exists
for exactly this), and a translator typing Arabic prose can slip a native-script digit into a
literal by hand with nothing else catching it.

WHY THIS EXISTS. Found live, 2026-09-22: two Arabic ARB strings this same session wrote
(`customersLoyaltyAdjustNoteRequired`, `ratingWeightedAvgHint`) carried literal "٣" and "٣٠" —
typed while composing Arabic prose, no different from any other Arabic character to the person
typing it — and rendered as raw Eastern-Arabic-Indic numerals on screen, the exact bug class the
owner had just asked to be fixed everywhere else (Flutter's own `MaterialLocalizationAr`, see
widgets/date_time_picker_sheet.dart's own doc comment on that unrelated but same-shaped bug).
Neither `flutter analyze` nor any existing CI gate reads `.arb` file content at all.

Usage:
    python ci/check_mobile_no_arabic_indic_digits.py

Exits 1 and prints every offending key if found; exits 0 (silent) if none.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
L10N_DIR = ROOT / "apps" / "mobile" / "lib" / "l10n"
KB_FILE = ROOT / "apps" / "mobile" / "assets" / "knowledge" / "mobile_kb.json"

# arabic-indic-digits: intentional — this IS the detector; it has to name the characters it refuses.
# Eastern Arabic-Indic (٠-٩, U+0660-0669) and Extended Arabic-Indic / Urdu (۰-۹, U+06F0-06F9).
NATIVE_DIGIT_RE = re.compile(r"[٠-٩۰-۹]")


def _check_strings(rel: str, items: dict) -> bool:
    failed = False
    for key, value in items.items():
        if key.startswith("@") or not isinstance(value, str):
            continue
        found = NATIVE_DIGIT_RE.findall(value)
        if found:
            failed = True
            print(f"✗ {rel}: '{key}' contains native-script digit(s) {sorted(set(found))} — "
                  f"use Western 0-9: {value!r}")
    return failed


def main() -> int:
    failed = False
    for f in sorted(L10N_DIR.glob("app_*.arb")):
        data = json.loads(f.read_text(encoding="utf-8"))
        failed |= _check_strings(f.relative_to(ROOT).as_posix(), data)

    # mobile_kb.json — same rule, nested one level: {entry_id: {title: {locale: text}, body: {...}}}.
    kb = json.loads(KB_FILE.read_text(encoding="utf-8"))
    kb_rel = KB_FILE.relative_to(ROOT).as_posix()
    for entry_id, entry in kb.items():
        for field in ("title", "body"):
            texts = entry.get(field)
            if isinstance(texts, dict):
                failed |= _check_strings(kb_rel, {f"{entry_id}.{field}.{loc}": v for loc, v in texts.items()})

    if failed:
        return 1
    print("✔ no Arabic/Urdu-Indic digits in any mobile .arb string or mobile_kb.json entry")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
