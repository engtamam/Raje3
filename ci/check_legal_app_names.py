#!/usr/bin/env python3
"""Every per-app annex in deploy/seed/legal/terms.md ("### N. ملحق: <name>") must name a REAL,
CURRENT app — apps/console/src/apps.ts's own APP_ROWS, UNIONED with apps/mobile's own kAppRows,
is the source of truth for what an app is actually called today.

WHY THIS EXISTS. terms.md's app annexes are hand-typed prose, not generated — a real app renamed
in apps.ts (the console's own app-store catalogue, the same list "متجر التطبيقات" renders from)
has no mechanism forcing anyone to notice its Terms of Service annex still speaks of the old name.
A legal document naming an app that no longer exists under that name is exactly the kind of drift
that turns into a real dispute later — the owner's own explicit ask (2026-09-29) was a gate that
makes that drift impossible to ship silently.

WHY BOTH CATALOGUES, NOT JUST apps.ts. Most apps are console-first and mobile mirrors apps.ts
1:1 (see app_store_model.dart's own header comment). But an app can be MOBILE-ONLY with no
console screen at all (الاستضافة المهنية / Coworking, found live 2026-09-29 — a real, listed,
sellable app whose entire UI is apps/mobile/lib/features/coworking, no apps.ts row exists for it
and none is owed one). Checking apps.ts alone would make this gate fail on a real app forever,
which is exactly the false-positive-noise failure mode that gets a real check muted or deleted —
so a name real in EITHER catalogue counts.

WHAT THIS CHECKS. Every `### <n>. ملحق: <name>` heading in terms.md's Arabic half must have its
<name> appear, verbatim, as some APP_ROWS row's own `name:` string OR some kAppRows row's own
`name:` string. It does NOT require the reverse (an app with no annex yet is fine — not every app
needs one, see terms.md's own header comment) and it does NOT touch the English half (its annex
titles are translations, not the matched string — the Arabic text is what governs on any
discrepancy, per terms.md's own General Provisions clause).

Exit 0 = clean. Exit 1 = an annex name that matches no current app, named explicitly.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPS_TS = ROOT / "apps" / "console" / "src" / "apps.ts"
APP_STORE_MODEL_DART = ROOT / "apps" / "mobile" / "lib" / "models" / "app_store_model.dart"
TERMS_MD = ROOT / "deploy" / "seed" / "legal" / "terms.md"

C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"
if not sys.stdout.isatty():
    C_G = C_R = C_N = ""


def _extract_app_rows_block(text: str) -> str:
    m = re.search(r"export const APP_ROWS[^=]*=\s*\[", text)
    if not m:
        raise RuntimeError(f"could not find `export const APP_ROWS = [` in {APPS_TS}")
    start = m.end()
    depth = 1
    i = start
    while depth > 0:
        if text[i] == "[":
            depth += 1
        elif text[i] == "]":
            depth -= 1
        i += 1
    return text[start:i]


def canonical_app_names() -> set[str]:
    block = _extract_app_rows_block(APPS_TS.read_text(encoding="utf-8"))
    names = set(re.findall(r"name:\s*'([^']+)'", block))
    # kAppRows entries look like `AppRow(\n  id: 'x', key: '...', name: 'الاسم',\n  ...)` — the
    # same `name: '...'` shape as apps.ts's own rows, so one regex over the whole const covers
    # both, mobile-only rows included (see this file's own module docstring).
    dart_text = APP_STORE_MODEL_DART.read_text(encoding="utf-8")
    m = re.search(r"const List<AppRow> kAppRows = \[", dart_text)
    if m:
        depth = 1
        i = m.end()
        while depth > 0:
            if dart_text[i] == "[":
                depth += 1
            elif dart_text[i] == "]":
                depth -= 1
            i += 1
        names |= set(re.findall(r"name:\s*'([^']+)'", dart_text[m.end():i]))
    return names


def annex_names_in_terms() -> list[tuple[int, str]]:
    text = TERMS_MD.read_text(encoding="utf-8")
    ar_half = text.split("## English", 1)[0]
    found = []
    for i, line in enumerate(ar_half.splitlines(), start=1):
        m = re.match(r"###\s*\d+\.\s*ملحق:\s*(.+?)\s*$", line.strip())
        if m:
            found.append((i, m.group(1)))
    return found


def main() -> int:
    names = canonical_app_names()
    annexes = annex_names_in_terms()
    if not annexes:
        print(f"{C_G}✔ no app annexes in terms.md yet — nothing to check{C_N}")
        return 0
    failed = False
    for lineno, name in annexes:
        if name in names:
            print(f"{C_G}✔ terms.md:{lineno} ملحق '{name}' matches a real app in apps.ts{C_N}")
        else:
            failed = True
            print(f"{C_R}✗ terms.md:{lineno} ملحق '{name}' matches NO app currently in "
                  f"apps/console/src/apps.ts's APP_ROWS — renamed or removed app, fix the annex "
                  f"heading (or the app itself, whichever drifted){C_N}")
    if failed:
        return 1
    print(f"{C_G}✔ every app annex in terms.md names a real, current app{C_N}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
