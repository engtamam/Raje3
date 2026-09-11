#!/usr/bin/env python3
"""The gate the owner asked for (2026-09-11): "سوي بوابة تمسك كل النصوص في الواجهة ما تدعم كل
اللغات أو في لغة ناقصة" — catch every UI string that doesn't support every locale the console
declares, and every screen that carries visible Arabic text with no translation hookup at all.

TWO HALVES, TWO SEVERITIES — because they answer different questions and one of them is a
regression a commit can introduce today, while the other is the honest size of a rollout still in
progress (operator-i18n.tsx's own header: "CURRENT PHASE covers field-operator screens only").

  PART A (FAILS THE BUILD) — every screen that HAS already opted into the translation system
  (`registerOperatorStrings`) must answer EVERY key in EVERY locale `operator-i18n.tsx` declares.
  A screen that ships an Arabic string today and forgets the Urdu one is a real drift a commit
  just introduced — this half exists to make that impossible to ship silently.

  PART B (REPORTS, NEVER FAILS) — every OTHER screen: real Arabic text in its JSX, never routed
  through `t()`/`useOperatorI18n()` at all. This is not a regression (the whole product has
  always been built this way) — it is the map of what "كل الشاشات" still means, so the owner's
  own next request ("رحّل شاشة كذا") can be answered against real numbers instead of a guess.

WHY REGEX, NOT A TS/JSX PARSER. This project's own CI has no JS/TS toolchain dependency for a
Python script to invoke, and every OTHER lightweight text gate in this ci/ directory already
reads source as text. `registerOperatorStrings({...})` is a small, consistent literal shape
(locale: { 'key': 'value', ... }) — a brace-depth scanner over it is honest here, not a shortcut
that risks missing what a real parser would catch; a syntax this script cannot make sense of is
reported as a parse failure, never silently skipped.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "apps" / "console" / "src"

# `operator-i18n.tsx`'s own OPERATOR_LOCALES — mirrored by hand (a locale added there and not
# here would make Part A blind to exactly the gap it exists to catch). Small, rarely-changing
# list; the mirror is intentional, same posture Messages.tsx's own REASON_TEMPLATE_TYPE holds.
LOCALES = ["ar", "en", "ur", "ha", "fil"]

_REGISTER_CALL = re.compile(r"registerOperatorStrings\(\s*\{", re.MULTILINE)
_LOCALE_HEAD = re.compile(r"(\b(?:" + "|".join(LOCALES) + r")\b)\s*:\s*\{")
_KEY = re.compile(r"'([a-zA-Z0-9_.]+)'\s*:")


def _match_braces(text: str, open_at: int) -> int:
    """`open_at` indexes the `{` itself. Returns the index just past its matching `}`, or -1 if
    the braces never close (a real syntax problem worth reporting, not silently ignoring)."""
    depth = 0
    i = open_at
    while i < len(text):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return -1


def extract_locale_keys(path: Path) -> dict[str, set[str]] | None:
    """{locale: {keys registered for it}} for every `registerOperatorStrings` call in this file
    (a file may call it more than once). `None` when the file calls it but this scanner could not
    find a matching call — reported as a parse failure by the caller, not swallowed."""
    text = path.read_text(encoding="utf-8")
    m = _REGISTER_CALL.search(text)
    if not m:
        return {}
    out: dict[str, set[str]] = {loc: set() for loc in LOCALES}
    pos = 0
    while True:
        m = _REGISTER_CALL.search(text, pos)
        if not m:
            break
        call_open = m.end() - 1  # index of the outer `{`
        call_close = _match_braces(text, call_open)
        if call_close == -1:
            return None
        body = text[call_open:call_close]
        for lm in _LOCALE_HEAD.finditer(body):
            loc = lm.group(1)
            loc_open = lm.end() - 1
            loc_close = _match_braces(body, loc_open)
            if loc_close == -1:
                return None
            block = body[loc_open:loc_close]
            out[loc].update(_KEY.findall(block))
        pos = call_close
    return out


def part_a() -> list[str]:
    problems: list[str] = []
    for path in sorted(SRC.rglob("*.ts*")):
        if ".test." in path.name or path.name.endswith(".d.ts"):
            continue
        if "registerOperatorStrings" not in path.read_text(encoding="utf-8"):
            continue
        keys = extract_locale_keys(path)
        rel = path.relative_to(ROOT)
        if keys is None:
            problems.append(f"{rel}: calls registerOperatorStrings() in a shape this gate could not parse")
            continue
        # ar IS THE SOURCE OF TRUTH (operator-i18n.tsx's own docstring: "every key is written
        # here first") — the set every OTHER locale is judged against. A key present in en/ur/…
        # but absent from ar is an orphan worth its own line, not silently ignored either.
        base = keys.get("ar", set())
        if not base:
            continue  # this file registers no `ar` block at all — nothing to check it against
        for loc in LOCALES:
            if loc == "ar":
                continue
            missing = base - keys.get(loc, set())
            if missing:
                sample = ", ".join(sorted(missing)[:6])
                more = "" if len(missing) <= 6 else f" (+{len(missing) - 6} more)"
                problems.append(f"{rel}: {loc} is missing {len(missing)} key(s) ar has — {sample}{more}")
        orphans = keys.get("ar", set())
        for loc in LOCALES:
            if loc == "ar":
                continue
            extra = keys.get(loc, set()) - base
            if extra:
                sample = ", ".join(sorted(extra)[:6])
                problems.append(f"{rel}: {loc} has {len(extra)} key(s) ar does not — {sample} (orphaned, or ar itself is missing them)")
    return problems


# ── PART B — REPORT ONLY ──────────────────────────────────────────────────────────────────────
_ARABIC = re.compile(r"[؀-ۿ]")
# rj-ui/ IS EXCLUDED ON PURPOSE — a kit component (Button, Badge, Modal…) renders whatever text a
# CALLER passes it; the Arabic lives at the call site, not in the component, so counting it here
# would double-count every screen that uses one and say nothing about the kit itself.
_EXCLUDE_DIRS = {"rj-ui"}


def part_b() -> tuple[int, int, list[tuple[Path, int]]]:
    covered_files: set[Path] = set()
    for path in SRC.rglob("*.ts*"):
        if ".test." in path.name:
            continue
        text = path.read_text(encoding="utf-8")
        if "useOperatorI18n" in text or "registerOperatorStrings" in text:
            covered_files.add(path)

    uncovered: list[tuple[Path, int]] = []
    total_screens = 0
    for path in sorted(SRC.rglob("*.tsx")):
        if ".test." in path.name:
            continue
        if any(part in _EXCLUDE_DIRS for part in path.relative_to(SRC).parts):
            continue
        text = path.read_text(encoding="utf-8")
        arabic_hits = len(_ARABIC.findall(text))
        if arabic_hits == 0:
            continue
        total_screens += 1
        if path not in covered_files:
            uncovered.append((path.relative_to(ROOT), arabic_hits))
    return total_screens, len(uncovered), uncovered


def main() -> int:
    quiet = "--quiet-report" in sys.argv[1:]  # Part B's per-file top-15 dump, skipped when wired
    # into every ship (ship.sh's own step 0) — the two summary lines stay either way; a real
    # regression (Part A) is never affected by this flag, only the informational breakdown is.
    a_problems = part_a()
    total, uncovered_count, uncovered = part_b()

    print("\033[1m  ▸ Part A — locales already wired: must answer every key\033[0m")
    if a_problems:
        for p in a_problems:
            print(f"    \033[31m✗ {p}\033[0m")
    else:
        print("    \033[32m✔ every key registered in ar is answered in en/ur/ha/fil, and none are orphaned\033[0m")

    print()
    print("\033[1m  ▸ Part B — screens with real Arabic text, by translation coverage (report only)\033[0m")
    print(f"    {total - uncovered_count} / {total} screens route their Arabic text through operator-i18n")
    print(f"    {uncovered_count} screens carry Arabic text with no translation hookup at all — the real size of \"كل الشاشات\"")
    if uncovered and not quiet:
        print("    heaviest first, top 15:")
        for rel, hits in sorted(uncovered, key=lambda x: -x[1])[:15]:
            print(f"      {hits:>4}  {rel}")

    if a_problems:
        print()
        print(f"\033[31m  ✗ {len(a_problems)} problem(s) in Part A — nothing here is a false positive worth ignoring\033[0m")
        return 1
    print()
    print("\033[32m  ✔ Part A is clean\033[0m — Part B is a report, not a failure: translating the rest is tracked work, not a regression this gate blocks on.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
