#!/usr/bin/env python3
"""apps/mobile/lib/theme/app_colors.g.dart must actually BE what
scripts/gen_mobile_theme.py would produce right now from config/product.json
and ui/packages/ui/src/theme/theme.config.ts — not a snapshot someone typed
once and forgot.

WHY THIS EXISTS. The mobile app's colour tokens used to be hand-copied
literals, the same drift class ci/check_a_hardcoded_color_does_not_shadow_a_token.py
already polices on the web side (a CSS/TS file quoting a theme.config.ts hex
instead of reading the variable). A Dart `const Color(...)` genuinely has to
be a literal — there is no CSS variable to read at runtime on mobile — so
the fix here is not "read a variable", it's "generate the literal from the
same source, and prove in CI that the generated file was actually
regenerated after the source changed, not hand-edited to match it by eye".

WHAT THIS CHECKS. Runs scripts/gen_mobile_theme.py's own generator function
in-process (so there is exactly one implementation of the extraction/mix
logic — this gate does not carry a second copy that could itself drift) and
byte-compares its output against the checked-in app_colors.g.dart. Any
difference — the brand accent changed, the light palette changed, or a human
hand-edited the generated file directly — fails the build with the fix
(`python scripts/gen_mobile_theme.py`) named explicitly.

Exit 0 = clean. Exit 1 = a problem, named on the exact line.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
OUTPUT = ROOT / "apps" / "mobile" / "lib" / "theme" / "app_colors.g.dart"

C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"
if not sys.stdout.isatty():
    C_G = C_R = C_N = ""


def main() -> int:
    print("▸ checking apps/mobile/lib/theme/app_colors.g.dart is up to date")

    sys.path.insert(0, str(SCRIPTS_DIR))
    try:
        import gen_mobile_theme  # type: ignore
    except Exception as exc:  # noqa: BLE001 — any import failure is a real failure to report
        print(f"{C_R}✖ could not import scripts/gen_mobile_theme.py: {exc}{C_N}")
        return 1

    try:
        expected = gen_mobile_theme.generate()
    except Exception as exc:  # noqa: BLE001
        print(f"{C_R}✖ scripts/gen_mobile_theme.py failed to generate: {exc}{C_N}")
        return 1

    if not OUTPUT.exists():
        print(f"{C_R}✖ {OUTPUT} does not exist — run: python scripts/gen_mobile_theme.py{C_N}")
        return 1

    actual = OUTPUT.read_text(encoding="utf-8")
    if actual != expected:
        print(f"{C_R}✖ {OUTPUT.relative_to(ROOT)} is out of date with "
              f"config/product.json / theme.config.ts.{C_N}")
        print("  Either the brand accent or the light palette changed and this file was not "
              "regenerated, or it was hand-edited directly.")
        print("  Fix: python scripts/gen_mobile_theme.py   (then commit the result)")
        return 1

    print(f"{C_G}✔ app_colors.g.dart matches the generator's current output{C_N}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
