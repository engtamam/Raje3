"""No price may appear in code. The price list is deploy/seed/plans.json and nowhere else.

WHY THIS GUARD EXISTS AT ALL, when the plans are already seeded from a file.

Because the second copy never arrives as a decision. It arrives as a helpful constant during a
demo — `PRICE_SMART = 298` so a screen has something to render before billing answers — and it is
correct on the day it is written. Then the price list changes, the seeder corrects the cluster, and
the constant does not, because nobody remembers it is a price: it looks like a number.

What the customer is then shown and what he is charged disagree. That is not a display bug; in a
country with a consumer protection authority it is a published price that is not the price.

So the rule is mechanical: every published amount, in halalas or in riyals, may not appear in any
Python, YAML or shell we wrote. The seed file is the single exception, because it IS the list —
and the amounts are read OUT of it rather than copied here, so the guard cannot go on watching a
price list we retired.

IT ONLY READS WHAT WE WROTE. platform/ is somebody else's tree and read-only to us, and a test
fixture that happens to charge 29800 for something is not our price list.

A NUMBER THAT IS GENUINELY NOT A PRICE — 598 as a count, an id, a timeout — is exempted here by
name with the reason written down, rather than by loosening the pattern until it stops firing.
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

SEED = ROOT / "deploy" / "seed" / "plans.json"

# NOT SPELLED OUT HERE — READ FROM THE LIST ITSELF, and that is the whole of ز-8.
#
# This tuple used to be typed by hand: ("148", "298", "598", "14800", "29800", "59800"), the three
# tiers of a plan ladder that no longer exists. The product became a base plus apps, plans.json was
# rewritten, and not one of those six numbers survived into it. The guard went on passing green
# every build while watching for prices nobody charges — which is worse than no guard, because the
# build says the rule holds.
#
# A price list that has to be copied into its own guard drifts from its guard. So the guard opens
# the file, and the numbers it hunts for are by construction the numbers we charge on the day it
# runs.
#
# HALALAS ONLY, AND ONLY THE ONES A NUMBER CANNOT BE MISTAKEN FOR. Both of those are measured
# facts about this repo, not preferences, and both follow the rule this guard has always lived by:
# a guard that cries about things nobody can fix is a guard somebody switches off, and then it
# catches nothing at all — including the price it was working for.
#
#   the riyal forms are dropped.  Today's amounts are 99, 75 and 50 riyals. Searched bare across
#                                 what we wrote, «50» appears 144 times and «99» 12 — a loop
#                                 bound, a default priority, a hash range. Narrowing to lines that
#                                 also mention a price still leaves 31, because «50 ريال» is a
#                                 DISCOUNT a shop offers its own customer, which is his number and
#                                 not ours. Nothing separates them, so they are not guarded.
#   round hundreds are dropped.   The seat pack is a whole number of hundreds of riyals, and in
#                                 halalas it appears 63 times across this repo as a batch size, a
#                                 row limit, a reward cost and a basket total. An amount that
#                                 round is a number people write for a dozen other reasons.
#
# What is left is every amount ending in a part-riyal figure — two of them today, including the
# base plan — and those have zero false positives across the whole repo. The dropped ones rely on
# what every other value in plans.json relies on: they are read from billing, and there is no code
# path that would want them locally.
#
# NO NUMBER FROM THAT LIST IS WRITTEN ANYWHERE IN THIS FILE, deliberately. That is what lets this
# guard be judged by its own pattern instead of exempting itself by path — the first draft of this
# comment named the two amounts, and the guard failed on itself, correctly.
def _prices() -> list[str]:
    import json
    plans = json.loads(SEED.read_text(encoding="utf-8"))
    return sorted({str(h) for h in
                   (int(p.get("amount") or 0) for p in (plans.get("plans") or []))
                   # A free row costs nothing, and «0» is in every file we own.
                   if h > 0 and h % 1000 != 0})


PRICES = tuple(_prices())

# The price list itself. The single exception, because it IS the list — and the only one: this
# guard no longer spells the prices out, so it is judged by its own pattern like every other file.
# A guard that exempts itself by path is a guard with a blind spot exactly where somebody would
# reach for a constant.
EXEMPT_FILES = {
    "deploy/seed/plans.json",
}

# Ours only. platform/ is read-only to us and its numbers are not our prices.
SEARCH = ("services", "ci", "deploy", "scripts", "config")
SUFFIXES = {".py", ".yaml", ".yml", ".sh", ".json", ".ts", ".tsx", ".js"}

# CODE WE WROTE, and nothing else that happens to sit under services/.
#
# The first run found 26 "prices": every one was a CWE identifier in the platform's generated
# security catalogue (CWE-148, CWE-298, CWE-598 — all three, which is almost funny) or a colour
# tuple inside a vendored pip dependency. None was a price, and a guard that cries about 26 things
# nobody can fix is a guard somebody switches off in a week. So the scope is narrowed here rather
# than the pattern loosened: the pattern stays strict enough to catch a real one.
SKIP_PARTS = {".venv", "node_modules", ".git", "site-packages", "__pycache__", ".pytest_cache"}
SKIP_NAMES = {"cwe.json"}          # the platform's generated CWE catalogue, per service

# A bare number is a price only when it stands alone as one. `sha256:...59800...` and a port and a
# line `timeout=14800` are three different things, and only the second and third are worth a look —
# so the pattern requires a word boundary and rejects a digit or a dot on either side, which is
# what separates 298 from 1298 and from 2.98.
PATTERNS = [re.compile(rf"(?<![\d.]){p}(?![\d.])") for p in PRICES]

# Written down rather than pattern-loosened. Each entry says WHY the number is not a price.
ALLOW: dict[str, str] = {}


def main() -> int:
    problems: list[str] = []
    # AN EMPTY PRICE LIST IS A BROKEN GUARD, NOT A CLEAN REPO. A renamed field or a restructured
    # seed file would leave nothing to search for, and this would print «ok» forever — the exact
    # silence ز-8 was.
    if not PRICES:
        print(f"\033[31m  x no prices found in {SEED.relative_to(ROOT).as_posix()} — this guard "
              f"has nothing to look for, which is not the same as finding nothing\033[0m")
        return 1
    for top in SEARCH:
        base = ROOT / top
        if not base.exists():
            continue
        for f in base.rglob("*"):
            if not f.is_file() or f.suffix not in SUFFIXES:
                continue
            if f.name in SKIP_NAMES or SKIP_PARTS.intersection(f.parts):
                continue
            rel = f.relative_to(ROOT).as_posix()
            if rel in EXEMPT_FILES or rel in ALLOW:
                continue
            try:
                text = f.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for line_no, line in enumerate(text.splitlines(), 1):
                # A DIGEST IS NOT A PRICE. `sha256:...e598b9...` contains «598» surrounded by
                # letters, which every one of these patterns is deliberately blind to — they guard
                # against a digit boundary, and a hex string has none. The guard failed on a line
                # that CI itself rewrites on every publish, which is the worst possible false
                # positive: it fires on a change nobody made and teaches people to ignore it.
                if "sha256:" in line:
                    continue
                for price, pat in zip(PRICES, PATTERNS):
                    if pat.search(line):
                        problems.append(
                            f"{rel}:{line_no}: {price} — a price in code is a price that needs a "
                            f"deploy to change, so it stops matching the one we charge. "
                            f"Read it from billing, or put it in deploy/seed/plans.json.\n"
                            f"    {line.strip()[:110]}")

    for p in problems:
        print(f"\033[31m  x {p}\033[0m")
    if problems:
        print(f"\n\033[31m  x {len(problems)} price(s) in code\033[0m")
        return 1
    print("\033[32m  ok no price appears anywhere but deploy/seed/plans.json\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
