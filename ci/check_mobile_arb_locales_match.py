#!/usr/bin/env python3
"""apps/mobile's six lib/l10n/*.arb files must all carry the exact same key set as app_ar.arb.

WHY THIS EXISTS. The mobile app ships six locales (ar/en/bn/fil/ha/ur). Nothing stopped someone
from adding a new string key to app_ar.arb and forgetting the other five — Flutter's l10n
generator does not fail on a missing key in a non-primary .arb file, it just silently falls back,
so a translator gap ships silently and only shows up as untranslated Arabic text on a real device
in Bengali/Filipino/Hausa/Urdu, exactly the class of drift ci/check_i18n.py already polices on
the console side.

WHAT THIS CHECKS. Every non-"@..." key in app_ar.arb (the source of truth) exists in every other
locale file, and no other locale file carries a key app_ar.arb itself lacks (an orphan translation
nobody will ever see used).

Exit 0 = clean. Exit 1 = every locale's missing/extra keys, named.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
L10N_DIR = ROOT / "apps" / "mobile" / "lib" / "l10n"
BASE_LOCALE = "ar"
OTHER_LOCALES = ["en", "bn", "fil", "ha", "ur"]

C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"
if not sys.stdout.isatty():
    C_G = C_R = C_N = ""


def _keys(path: Path) -> set[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k for k in data if not k.startswith("@")}


def main() -> int:
    base_path = L10N_DIR / f"app_{BASE_LOCALE}.arb"
    base_keys = _keys(base_path)
    failed = False
    for locale in OTHER_LOCALES:
        path = L10N_DIR / f"app_{locale}.arb"
        if not path.exists():
            print(f"{C_R}✗ app_{locale}.arb is missing entirely{C_N}")
            failed = True
            continue
        keys = _keys(path)
        missing = base_keys - keys
        extra = keys - base_keys
        if missing or extra:
            failed = True
            print(f"{C_R}✗ app_{locale}.arb is out of sync with app_{BASE_LOCALE}.arb{C_N}")
            if missing:
                print(f"    missing ({len(missing)}): {sorted(missing)[:10]}"
                      f"{' ...' if len(missing) > 10 else ''}")
            if extra:
                print(f"    orphaned ({len(extra)}): {sorted(extra)[:10]}"
                      f"{' ...' if len(extra) > 10 else ''}")
        else:
            print(f"{C_G}✔ app_{locale}.arb: {len(keys)} keys, matches app_{BASE_LOCALE}.arb{C_N}")

    if failed:
        return 1
    print(f"{C_G}✔ all six locales carry the same {len(base_keys)} key(s){C_N}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
