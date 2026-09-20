#!/usr/bin/env python3
"""A mobile screen/widget migrated to lib/l10n must carry no raw Arabic string outside
S.of(context) — the mobile mirror of ci/check_operator_screen_localized.py's rule on the
console side, same SCREENS-allowlist shape and same reason for it.

WHY THIS EXISTS. The mobile app supports six locales through lib/l10n/*.arb — the exact same
idea apps/console/src/operator-i18n.tsx already applies. A widget that hardcodes an Arabic
literal instead of reading it through `S.of(context)!.someKey` renders Arabic to every
non-Arabic locale regardless of the user's own language setting — the drift this repo's console
gate already polices, on a door this session found unwired (main.dart never carried
S.localizationsDelegates/supportedLocales until the same pass that added this gate).

WHY AN ALLOWLIST, not every *.dart file: apps/mobile predates its own l10n system — most of the
app (auth screens, validators, the network layer's own error strings) was written entirely in
Arabic before lib/l10n/*.arb existed, and migrating all of it is its own tracked, ongoing pass,
not a thing one CI gate can retroactively demand of code nobody has touched yet. Exactly
check_operator_screen_localized.py's own reasoning: "an unlisted screen is not yet expected to
be clean, so --all never flags work nobody has begun." Add a path here once ITS migration starts.

WHY A REGEX OVER THE ARABIC UNICODE RANGE, not a list of known strings: every hardcoded Arabic
literal in a screen's SOURCE is caught this way regardless of which runtime branch renders it,
the same reasoning check_operator_screen_localized.py's own header gives.

Usage:
    python ci/check_mobile_screen_localized.py apps/mobile/lib/features/home/home_screen.dart
    python ci/check_mobile_screen_localized.py --all   # every file in SCREENS below

Exits 1 and prints every offending line if any raw Arabic text remains; exits 0 (silent) if clean.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Files already migrated to lib/l10n — add a path here once its migration starts.
SCREENS = [
    "apps/mobile/lib/features/home/home_screen.dart",
    "apps/mobile/lib/features/shell/main_shell.dart",
    "apps/mobile/lib/widgets/app_widgets.dart",
    "apps/mobile/lib/features/auth/login_screen.dart",
    "apps/mobile/lib/features/auth/signup_screen.dart",
    "apps/mobile/lib/features/auth/verify_phone_screen.dart",
    "apps/mobile/lib/features/visit/visit_screen.dart",
    "apps/mobile/lib/core/utils/url_helper.dart",
    "apps/mobile/lib/core/utils/snackbar_helper.dart",
    "apps/mobile/lib/core/router/app_router.dart",
]

ARABIC = re.compile(r"[؀-ۿ]")


def _is_exempt(line: str) -> bool:
    stripped = line.strip()
    if stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("/*"):
        return True
    # A CALL ALREADY ROUTED THROUGH THE DICTIONARY LOOKUP is not a bypass of it — same reasoning
    # check_operator_screen_localized.py gives for t('...') call arguments.
    if "S.of(context)" in stripped:
        return True
    # THE BRAND'S OWN NAME IS NOT UI COPY TO TRANSLATE — same category as console's NAME_AR
    # exemption. AppConfig.appInfoNameAr is the product's Arabic wordmark itself, and stays Arabic
    # in every locale the same way a brand name does in any product translated around it.
    if "appInfoNameAr" in stripped:
        return True
    return False


def scan(path: Path) -> list[tuple[int, str]]:
    hits: list[tuple[int, str]] = []
    in_block_comment = False
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if in_block_comment:
            if "*/" in stripped:
                in_block_comment = False
            continue
        if stripped.startswith("/*") and "*/" not in stripped:
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
            print(f"✗ {path.relative_to(ROOT)}: {len(hits)} raw Arabic string(s) outside S.of(context)")
            for lineno, text in hits:
                print(f"    {lineno}: {text}")
        else:
            print(f"✓ {path.relative_to(ROOT)}: clean")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
