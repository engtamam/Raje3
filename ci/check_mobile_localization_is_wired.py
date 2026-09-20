#!/usr/bin/env python3
"""apps/mobile's lib/l10n system must actually be wired into MaterialApp, not just generated.

WHY THIS EXISTS. Found live in this session: lib/l10n/*.arb, the generated S class, and every
locale's own translation file all existed — a complete six-locale system — and main.dart's
MaterialApp.router never carried `localizationsDelegates`, `supportedLocales`, or `locale`.
S.of(context) would have returned null on every call and every screen that used it would have
crashed at runtime; nothing caught it because there is no Flutter SDK in this environment to
`flutter analyze`/run the app. A generated, unwired feature is worse than a missing one — it
reads as done.

WHAT THIS CHECKS. lib/main.dart's MaterialApp.router call site actually references
S.localizationsDelegates, S.supportedLocales, and reads a locale from LocaleProvider (so switching
language actually does something) — the same "generated and wired, not just generated" question
ci/check_mobile_theme_is_generated.py and ci/check_mobile_nav_is_generated.py answer for the two
other Dart-side generators.

Exit 0 = clean. Exit 1 = a problem, named on the exact line missing.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "apps" / "mobile" / "lib" / "main.dart"

C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"
if not sys.stdout.isatty():
    C_G = C_R = C_N = ""

REQUIRED = {
    "S.localizationsDelegates": "MaterialApp.router is missing `localizationsDelegates: S.localizationsDelegates`",
    "S.supportedLocales": "MaterialApp.router is missing `supportedLocales: S.supportedLocales`",
    "locale:": "MaterialApp.router is missing a `locale:` argument — nothing reads LocaleProvider's choice",
}


def main() -> int:
    if not MAIN.exists():
        print(f"{C_R}✗ {MAIN.relative_to(ROOT)} does not exist{C_N}")
        return 1

    text = MAIN.read_text(encoding="utf-8")
    missing = [msg for needle, msg in REQUIRED.items() if needle not in text]

    if missing:
        print(f"{C_R}✗ apps/mobile's l10n system is generated but not wired into MaterialApp:{C_N}")
        for msg in missing:
            print(f"    - {msg}")
        print("  Fix: wire S.localizationsDelegates/S.supportedLocales/locale into "
              "MaterialApp.router in lib/main.dart.")
        return 1

    print(f"{C_G}✓ lib/l10n is wired into MaterialApp.router (lib/main.dart){C_N}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
