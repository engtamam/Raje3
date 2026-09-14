#!/usr/bin/env python3
"""The gate the owner asked for (2026-09-11): "سوي بوابة تمسك كل النصوص في الواجهة ما تدعم كل
اللغات أو في لغة ناقصة" — catch every UI string that doesn't support every locale the console
declares, and every screen that carries visible Arabic text with no translation hookup at all.

TWO HALVES, BOTH FAIL THE BUILD — the owner's own explicit call (2026-09-11), made with the real
consequence stated out loud first and confirmed anyway: at the moment this flipped, 87 of 95
screens carried Arabic text with no translation hookup at all, so THIS GATE BLOCKS EVERY SHIP
(console and platform both, via ship.sh's own pre-flight) until every one of them is migrated onto
operator-i18n across all five locales. No allowlist, no partial exemption — a full stop, not a
staged one, by explicit instruction over the staged alternative offered at the time.

  PART A — every screen that HAS already opted into the translation system
  (`registerOperatorStrings`) must answer EVERY key in EVERY locale `operator-i18n.tsx` declares.
  A screen that ships an Arabic string today and forgets the Urdu one is a real drift a commit
  just introduced.

  PART B — every OTHER screen with real Arabic text, never routed through
  `t()`/`useOperatorI18n()` at all — the migration backlog itself, and now a build-blocking one.

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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_operator_screen_localized import scan as _scan_real_arabic  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "apps" / "console" / "src"

# `operator-i18n.tsx`'s own OPERATOR_LOCALES — mirrored by hand (a locale added there and not
# here would make Part A blind to exactly the gap it exists to catch). Small, rarely-changing
# list; the mirror is intentional, same posture Messages.tsx's own REASON_TEMPLATE_TYPE holds.
LOCALES = ["ar", "en", "ur", "ha", "fil", "bn"]

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


# ── PART B ────────────────────────────────────────────────────────────────────────────────────
# rj-ui/ IS EXCLUDED ON PURPOSE — a kit component (Button, Badge, Modal…) renders whatever text a
# CALLER passes it; the Arabic lives at the call site, not in the component, so counting it here
# would double-count every screen that uses one and say nothing about the kit itself.
#
# admin/ AND affiliates/ ARE EXCLUDED ENTIRELY, NOT JUST TRACKED — the owner's own explicit call
# (2026-09-11): these two serve OUR OWN platform team and marketing partners, not shop staff or
# owners — the whole reason ur/ha/fil exist at all (the guest-labour languages a shop's own field
# workers actually speak — operator-i18n.tsx's own header). Arabic-only there, by design, for
# ever — not a rollout gap this gate should ever ask to close.
_EXCLUDE_DIRS = {"rj-ui", "admin", "affiliates"}


def part_b() -> tuple[int, int, list[tuple[Path, int]]]:
    """Unchanged blocking criterion — still `*.tsx` only, still "does the file mention
    useOperatorI18n/registerOperatorStrings anywhere".

    THAT SUBSTRING TEST IS LOOSER THAN IT SHOULD BE, AND IT IS KNOWN NOW, NOT HYPOTHETICAL — it is
    exactly what let App.tsx carry real hardcoded Arabic (the rail's own chrome: `labels={{
    collapse: 'طيّ القائمة', … }}`, the navItems built from `nav.ts`'s literal `label` fields)
    through every language switch while this gate printed green (found live 2026-09-14; App.tsx
    never even CALLED `useOperatorI18n()` — the substring matched a comment elsewhere in the file
    quoting the hook's own name). That specific bug is now fixed at the source (App.tsx/nav.ts/
    nav-i18n.ts), verified by nav_i18n.test.ts — this function is left AS IT WAS rather than
    tightened to `arabic_hits == 0`, because tightening it here surfaced 12 OTHER, unrelated,
    pre-existing screens with their own leftover raw strings (Services.tsx, Messages.tsx,
    MessagePreview.tsx, Customer.tsx, Team.tsx, Points.tsx, Plans.tsx, Shop.tsx,
    AccountPanes.tsx, ServicesImportDrawer.tsx, operator-i18n.tsx, OperatorLocaleSwitcher.tsx —
    38 strings nobody has signed up to migrate today) and turning them into a build-blocking
    failure for every future ship is not a call this fix gets to make unilaterally. `part_c()`
    below is the honest middle ground: it runs the STRICTER, gap-free check this docstring
    describes, widened to plain `.ts` files too (which is what actually would have caught
    `nav.ts`), but reports it, never blocks on it — visible, not silently dropped, and not a
    surprise 38-file failure landing on someone else's unrelated ship.
    """
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
        parts = path.relative_to(SRC).parts
        if any(part in _EXCLUDE_DIRS for part in parts):
            continue
        # `scan()` is the SAME comment-aware pass check_operator_screen_localized.py runs per file
        # — a raw whole-text regex counted a comment quoting another screen's own Arabic name
        # (e.g. «متجر التطبيقات» inside an English header comment, StoreRoute.tsx/main.tsx's own
        # style throughout this repo) as "real Arabic text needing translation", which it never
        # was. Reusing the real check keeps the two gates from disagreeing about what counts.
        arabic_hits = len(_scan_real_arabic(path))
        if arabic_hits == 0:
            continue
        total_screens += 1
        if path not in covered_files:
            uncovered.append((path.relative_to(ROOT), arabic_hits))
    return total_screens, len(uncovered), uncovered


# ── PART C — INFORMATIONAL ONLY, NEVER BLOCKING ─────────────────────────────────────────────────
# The STRICT check — every `.ts`/`.tsx` file (not only `*.tsx`), judged purely on `arabic_hits`
# (not the loose "mentions the hook somewhere" substring Part B still uses) — surfaced instead of
# hidden, so the class of bug that let `nav.ts` (plain `.ts`, no JSX, invisible to Part B's
# `*.tsx` glob) carry nine hardcoded section labels through every language switch, AND the class
# that let App.tsx's OWN real strings hide behind a comment quoting "useOperatorI18n" by
# coincidence, both have somewhere to be SEEN — without unilaterally blocking every ship in the
# repo over files nobody has agreed belong to this migration yet.
_I18N_DICT_SUFFIXES = ("-i18n.ts",)
_I18N_DICT_NAMES = {"i18n.ts"}


def part_c() -> list[tuple[Path, int]]:
    hits: list[tuple[Path, int]] = []
    for path in sorted(SRC.rglob("*.ts*")):
        if ".test." in path.name or path.name.endswith(".d.ts"):
            continue
        if path.name.endswith(_I18N_DICT_SUFFIXES) or path.name in _I18N_DICT_NAMES:
            continue
        parts = path.relative_to(SRC).parts
        if any(part in _EXCLUDE_DIRS for part in parts):
            continue
        arabic_hits = len(_scan_real_arabic(path))
        if arabic_hits:
            hits.append((path.relative_to(ROOT), arabic_hits))
    return hits


def main() -> int:
    a_problems = part_a()
    total, uncovered_count, uncovered = part_b()

    print("\033[1m  ▸ Part A — locales already wired: must answer every key\033[0m")
    if a_problems:
        for p in a_problems:
            print(f"    \033[31m✗ {p}\033[0m")
    else:
        print("    \033[32m✔ every key registered in ar is answered in en/ur/ha/fil/bn, and none are orphaned\033[0m")

    print()
    print("\033[1m  ▸ Part B — every screen with real Arabic text must route it through operator-i18n\033[0m")
    print(f"    {total - uncovered_count} / {total} screens do")
    if uncovered:
        # ALWAYS THE FULL LIST, NEVER TRIMMED — this half now blocks the build, and a failure that
        # only says "87 screens" with no names is not actionable. Heaviest (most Arabic text, the
        # rough cost to migrate) first, so the list itself suggests a sane order to work through it.
        print(f"    \033[31m✗ {uncovered_count} screen(s) carry raw Arabic text outside any t() call:\033[0m")
        for rel, hits in sorted(uncovered, key=lambda x: -x[1]):
            print(f"      \033[31m✗\033[0m {hits:>5}  {rel}")

    if a_problems or uncovered:
        print()
        print(f"\033[31m  ✗ {len(a_problems)} problem(s) in Part A, {uncovered_count} screen(s) failing Part B"
              " — nothing here is a false positive worth ignoring\033[0m")
        return 1
    print()
    print("\033[32m  ✔ every screen with visible Arabic text routes it through operator-i18n, in every declared locale\033[0m")

    # NEVER AFFECTS THE RETURN CODE — see part_c()'s own header for why this stays informational.
    other = part_c()
    if other:
        print()
        print("\033[1m  ▸ Part C — plain .ts modules with raw Arabic, informational only\033[0m")
        for rel, hits in sorted(other, key=lambda x: -x[1])[:10]:
            print(f"    \033[33m!\033[0m {hits:>5}  {rel}")
        if len(other) > 10:
            print(f"    \033[2m… and {len(other) - 10} more\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
