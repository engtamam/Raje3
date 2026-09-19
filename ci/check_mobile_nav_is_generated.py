#!/usr/bin/env python3
"""apps/mobile/lib/core/nav/nav_sections.g.dart must actually BE what
scripts/gen_mobile_nav.py would produce right now from
apps/console/src/nav.ts — not a snapshot someone typed once and forgot.

Same pattern as ci/check_mobile_theme_is_generated.py: run the generator's
own function in-process (one implementation, not a second copy that could
itself drift) and byte-compare its output against the checked-in file.

Exit 0 = clean. Exit 1 = a problem, named on the exact line.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
OUTPUT = ROOT / "apps" / "mobile" / "lib" / "core" / "nav" / "nav_sections.g.dart"

C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"
if not sys.stdout.isatty():
    C_G = C_R = C_N = ""


def main() -> int:
    print("▸ checking apps/mobile/lib/core/nav/nav_sections.g.dart is up to date")

    sys.path.insert(0, str(SCRIPTS_DIR))
    try:
        import gen_mobile_nav  # type: ignore
    except Exception as exc:  # noqa: BLE001
        print(f"{C_R}✖ could not import scripts/gen_mobile_nav.py: {exc}{C_N}")
        return 1

    try:
        expected = gen_mobile_nav.generate()
    except Exception as exc:  # noqa: BLE001
        print(f"{C_R}✖ scripts/gen_mobile_nav.py failed to generate: {exc}{C_N}")
        return 1

    if not OUTPUT.exists():
        print(f"{C_R}✖ {OUTPUT} does not exist — run: python scripts/gen_mobile_nav.py{C_N}")
        return 1

    actual = OUTPUT.read_text(encoding="utf-8")
    if actual != expected:
        print(f"{C_R}✖ {OUTPUT.relative_to(ROOT)} is out of date with apps/console/src/nav.ts.{C_N}")
        print("  nav.ts changed (a section added/removed/re-gated) and this file was not "
              "regenerated, or it was hand-edited directly.")
        print("  Fix: python scripts/gen_mobile_nav.py   (then commit the result)")
        return 1

    print(f"{C_G}✔ nav_sections.g.dart matches the generator's current output{C_N}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
