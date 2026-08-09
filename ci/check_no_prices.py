"""No price may appear in code. The price list is deploy/seed/plans.json and nowhere else.

WHY THIS GUARD EXISTS AT ALL, when the plans are already seeded from a file.

Because the second copy never arrives as a decision. It arrives as a helpful constant during a
demo — `PRICE_SMART = 298` so a screen has something to render before billing answers — and it is
correct on the day it is written. Then the price list changes, the seeder corrects the cluster, and
the constant does not, because nobody remembers it is a price: it looks like a number.

What the customer is then shown and what he is charged disagree. That is not a display bug; in a
country with a consumer protection authority it is a published price that is not the price.

So the rule is mechanical: the three published amounts, in halalas or in riyals, may not appear in
any Python, YAML or shell we wrote. The seed file is the single exception, because it IS the list.

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

# In riyals, as a customer says them, and in halalas, as billing stores them. Both, because the
# constant somebody writes is whichever unit they had in their head at the time.
#
# THE PACK PRICES ARE NOT GUARDED, and the reason is worth writing down so nobody "fixes" it.
#
# They are 50 and 90 riyals — 5000 and 9000 halalas — and every one of those four numbers is a
# port, a row limit, a timeout or a batch size somewhere in this repo. Adding them turned a guard
# with zero false positives into one with 41, including OBJECTSTORE_ENDPOINT_URL ending in :9000
# and SNAPSHOT_VISIT_LIMIT: 5000. A guard that cries 41 times is a guard somebody switches off,
# and then it catches nothing at all — including the plan prices it was working for.
#
# So the guard covers the three plan prices, which are distinctive, and the pack prices rely on
# the same thing every other value in plans.json relies on: they are read from billing, and there
# is no code path that would want them locally.
PRICES = ("148", "298", "598", "14800", "29800", "59800")

# The price list itself, and this guard, which has to name the numbers to look for them.
EXEMPT_FILES = {
    "deploy/seed/plans.json",
    "ci/check_no_prices.py",
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
