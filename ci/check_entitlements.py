#!/usr/bin/env python3
# =============================================================================
# check_entitlements.py — every feature key is both SOLD and ENFORCED.
#
# THE PRICE LIST AND THE GATES ARE TWO HALVES OF ONE PROMISE, written in two files that nothing
# compared. Two ways for them to disagree, and they fail in opposite directions:
#
#   GATED BUT NOT SOLD    a screen is locked behind a key no plan grants — the feature is dead for
#                         every customer, including the ones paying the most. Nothing fails, nothing
#                         logs; the section is simply never there.
#
#   SOLD BUT NOT GATED    a plan promises something no code checks. Every shop gets it, the price
#                         list is a fiction, and the first honest customer to notice is the one who
#                         paid for the tier above.
#
# Both are silent. A typo in a key — `feature.insight.engine` — is the whole gap, and it renders as
# an absence rather than an error, which is the hardest thing in this product to see.
#
# THIS IS ALSO WHY THE KEYS ARE THE AUTHORITY AND NOT THE PLAN NAMES (§16.4.1): «الذكية» is a
# commercial word that changes when marketing changes it, and `feature.loyalty` is what the code
# asks. This guard is what keeps that separation from drifting into two truths.
# =============================================================================
from __future__ import annotations

import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLANS = ROOT / "deploy" / "seed" / "plans.json"

C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"


def sold() -> set[str]:
    data = json.loads(PLANS.read_text(encoding="utf-8"))
    rows = data["plans"] if isinstance(data, dict) else data
    keys: set[str] = set()
    for plan in rows:
        keys |= {k for k in (plan.get("limits") or {}) if k.startswith("feature.")}
    return keys


def gated() -> dict[str, list[str]]:
    """key -> the files that check it, so a failure names where to look."""
    where: dict[str, list[str]] = {}
    patterns = ["services/*/app/**/*.py", "apps/console/src/**/*.ts",
                "apps/console/src/**/*.tsx"]
    for pattern in patterns:
        for path in glob.glob(str(ROOT / pattern), recursive=True):
            try:
                text = Path(path).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for key in set(re.findall(r"[\"'](feature\.[a-z_.]+)[\"']", text)):
                where.setdefault(key, []).append(
                    str(Path(path).relative_to(ROOT)).replace("\\", "/"))
    return where


def main() -> int:
    s, g = sold(), gated()
    problems: list[str] = []

    for key in sorted(set(g) - s):
        problems.append(f"{key} is checked in {g[key][0]} and NO plan grants it — the feature is "
                        f"dead for every customer, including the ones paying the most, and nothing "
                        f"anywhere reports it")
    for key in sorted(s - set(g)):
        problems.append(f"{key} is sold in the price list and no code checks it — every shop gets "
                        f"it, and the customer who paid for the tier above is the one who finds out")

    for p in problems:
        print(f"{C_R}  ✗ {p}{C_N}")
    if problems:
        print(f"\n{C_R}  ✗ {len(problems)} feature key(s) sold and enforced differently{C_N}")
        return 1
    print(f"{C_G}  ✔ all {len(s)} feature keys are both sold and enforced{C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
