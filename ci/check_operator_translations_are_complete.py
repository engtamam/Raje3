#!/usr/bin/env python3
"""Every key an operator screen registers exists in EVERY operator locale, not just Arabic.

WHY THIS EXISTS. `registerOperatorStrings` (operator-i18n.tsx) falls back to Arabic for a
missing key — which is the right behaviour for a screen not yet translated at all, and the wrong
one for a screen that WAS translated and then grew a sixth key nobody carried into the other four
locales. `services-i18n.ts` did exactly that: six keys added across three phases of the same
feature (a downloadable import template, the packages tab, an image column) landed in `ar` and
were never mirrored into `en`/`ur`/`ha`/`fil` — an operator on any locale but Arabic read those
six labels in Arabic, silently, forever, with nothing anywhere saying the translation was missing.
Nobody would have noticed: the screen renders, it is not an error, `t()` never throws.

ARABIC IS THE SOURCE, BY CONVENTION THIS FILE FAMILY ALREADY STATES. Every one of these
`*-i18n.ts` files says so in its own header ("every key is written here first") — so `ar`'s own
key set is the ground truth this gate diffs every other locale against, in both directions: a key
missing from a locale is a translation nobody wrote, and a key present in a locale but ABSENT from
`ar` is a rename or a typo that drifted the two apart (translated the old name, forgot the new
one, or vice versa).

THE LOCALE LIST IS READ FROM `OPERATOR_LOCALES` ITSELF (operator-i18n.tsx), never duplicated here
as a second list this gate would silently stop checking against the day a sixth language is added
and only that source is updated.

EXTENSIBLE BY CONSTRUCTION, NOT BY REMEMBERING TO EXTEND A LIST. Every `apps/console/src/screens/
*-i18n.ts` file is checked — a future screen's own translation file is covered the moment it
exists, with nothing to register here.

    python ci/check_operator_translations_are_complete.py
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONSOLE = ROOT / "apps" / "console" / "src"
OPERATOR_I18N = CONSOLE / "operator-i18n.tsx"
SCREENS = CONSOLE / "screens"

C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"

#: `{ value: 'ar', label: 'العربية' }, …` — one locale per line inside OPERATOR_LOCALES' own
#: array literal. Read from the source rather than typed here, so a sixth language is picked up
#: the moment it is added to that one array, with nothing in this file to also remember to touch.
LOCALE_VALUE = re.compile(r"value:\s*'([a-z]+)'")

#: A top-level locale block inside `registerOperatorStrings({ … })` — `  ar: {`, two-space indent,
#: matching every existing `*-i18n.ts` file's own formatting. A block not indented exactly this
#: way is not one of these files' own locale sections and is deliberately not matched.
BLOCK_START = re.compile(r"^  ([a-z]+): \{", re.MULTILINE)

#: A registered string entry: `'some.key': 'value',`. Deliberately blind to anything that is not
#: this exact shape (a computed key, a spread) — those are not how this file family writes a
#: translation, and a screen using a different shape is a different problem from this gate's own.
ENTRY = re.compile(r"^\s*'([^']+)':\s*'", re.MULTILINE)


def operator_locales() -> list[str]:
    text = OPERATOR_I18N.read_text(encoding="utf-8")
    values = LOCALE_VALUE.findall(text)
    return values


def locale_blocks(text: str) -> dict[str, str]:
    """`{locale: its own block's text}` — split on every top-level `  <locale>: {` line, the
    block running to the next one (or EOF)."""
    starts = [(m.start(1), m.group(1)) for m in BLOCK_START.finditer(text)]
    blocks: dict[str, str] = {}
    for i, (pos, loc) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(text)
        blocks[loc] = text[pos:end]
    return blocks


def main() -> int:
    if not OPERATOR_I18N.is_file():
        print(f"{C_R}{OPERATOR_I18N.relative_to(ROOT).as_posix()} is missing — this gate cannot "
              f"read the locale list, so it refuses to{C_N}")
        return 1
    locales = operator_locales()
    if len(locales) < 2 or "ar" not in locales:
        print(f"{C_R}OPERATOR_LOCALES read as {locales!r} — expected Arabic plus at least one "
              f"other language; this gate cannot check anything against that{C_N}")
        return 1

    files = sorted(SCREENS.glob("*-i18n.ts"))
    if not files:
        print(f"{C_R}no *-i18n.ts files under {SCREENS.relative_to(ROOT).as_posix()} — this gate "
              f"has nothing to check, which is not the same as finding nothing wrong{C_N}")
        return 1

    problems: list[str] = []
    checked_keys = 0
    for f in files:
        text = f.read_text(encoding="utf-8")
        blocks = locale_blocks(text)
        rel = f.relative_to(ROOT).as_posix()

        missing_blocks = [loc for loc in locales if loc not in blocks]
        if missing_blocks:
            problems.append(f"{rel}: no `{missing_blocks[0]}: {{` block at all — every other "
                            f"locale in OPERATOR_LOCALES must appear here, even if every key in "
                            f"it still reads Arabic today")
            continue

        keysets = {loc: set(ENTRY.findall(blocks[loc])) for loc in locales}
        ar = keysets["ar"]
        checked_keys += len(ar)
        for loc in locales:
            if loc == "ar":
                continue
            missing = sorted(ar - keysets[loc])
            extra = sorted(keysets[loc] - ar)
            if missing:
                shown = ", ".join(missing[:6])
                more = f" (+{len(missing) - 6} more)" if len(missing) > 6 else ""
                problems.append(f"{rel}: {loc} is missing {len(missing)} key(s) `ar` has: "
                                f"{shown}{more}")
            if extra:
                shown = ", ".join(extra[:6])
                more = f" (+{len(extra) - 6} more)" if len(extra) > 6 else ""
                problems.append(f"{rel}: {loc} has {len(extra)} key(s) `ar` does not: {shown}"
                                f"{more} — a rename that only reached one locale?")

    if problems:
        print(f"{C_R}operator translations are incomplete ({len(problems)} problem(s)):{C_N}")
        for p in problems:
            print(f"  {p}")
        return 1

    print(f"{C_G}ok{C_N}  {len(files)} screen(s), {checked_keys} key(s) total, "
          f"{len(locales)} locales ({', '.join(locales)}) — every key answered everywhere")
    return 0


if __name__ == "__main__":
    sys.exit(main())
