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

C_G, C_R, C_Y, C_N = "\033[32m", "\033[31m", "\033[33m", "\033[0m"


def sold() -> set[str]:
    data = json.loads(PLANS.read_text(encoding="utf-8"))
    rows = data["plans"] if isinstance(data, dict) else data
    keys: set[str] = set()
    for plan in rows:
        keys |= {k for k in (plan.get("limits") or {}) if k.startswith("feature.")}
    return keys


# FILES THAT NAME A KEY WITHOUT GUARDING IT. This was the hole in the guard itself: it counted a
# mention ANYWHERE as enforcement, and `Plans.tsx` names every key as a price-list label — so a
# screen that SELLS a feature was read as the code that GUARDS it, and two features (`feature.api`
# and `feature.roles.custom`) were sold, unguarded, and reported green for as long as this ran.
#
# THE CONSOLE CAN NEVER ENFORCE. A lock drawn in a browser is a suggestion; the fetch behind it is
# one devtools tab away. So no `apps/console` file counts, ever — including the app store, whose
# whole job is to name every key it does not own.
DISPLAY_ONLY = (
    # The catalogue the store renders. It names all five keys and decides nothing: it reports what
    # billing said, and the gates live in the services that own the acts.
    "services/operations/app/core/apps.py",
)


# SOLD, AND THE PRODUCT DOES NOT HAVE IT. Not a silencer — a WARNING every run, with the decision
# written next to it. A line here says "we know we are charging for something that does not exist
# yet"; deleting the feature from the price list or building it both clear it.
#
# EMPTY, AND THAT IS THE POINT. `feature.roles.custom` sat here for one commit: it was sold on
# every tier and the product has three fixed roles with no screen that makes a fourth. With no
# subscribers yet, the honest fix was to stop selling it rather than to keep a note about it.
SOLD_UNBUILT: dict[str, str] = {}


def gated() -> dict[str, list[str]]:
    """key -> the SERVICE files that check it, so a failure names where to look."""
    where: dict[str, list[str]] = {}
    for pattern in ("services/*/app/**/*.py",):
        for path in glob.glob(str(ROOT / pattern), recursive=True):
            rel = str(Path(path).relative_to(ROOT)).replace("\\", "/")
            if rel in DISPLAY_ONLY or "/tests/" in rel:
                continue
            try:
                text = Path(path).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for key in set(re.findall(r"[\"'](feature\.[a-z_.]+)[\"']", text)):
                where.setdefault(key, []).append(
                    str(Path(path).relative_to(ROOT)).replace("\\", "/"))
    return where


def worded() -> set[str]:
    """The keys the pricing page has an Arabic sentence for.

    THE SCREEN READS THE PLAN FROM BILLING — every number, every limit, every feature — and the one
    thing kept here is the wording, because printing `feature.roles.custom` raw is a glossary rather
    than a page that sells. But a key with NO sentence is silently NOT RENDERED: sell a new feature
    tomorrow and it is enforced everywhere, priced into the plan, and invisible on the page where
    somebody decides to buy it. Nothing fails. It is the severed wire again, wearing a price tag.
    """
    text = (ROOT / "apps" / "console" / "src" / "screens" / "Plans.tsx").read_text(encoding="utf-8")
    block = text.split("LIMIT_WORDS", 1)[-1].split("};", 1)[0]
    return set(re.findall(r"['\"]?(feature\.[a-z_.]+)['\"]?\s*:", block))


def main() -> int:
    s, g = sold(), gated()
    problems: list[str] = []

    for key in sorted(s - worded()):
        problems.append(f"{key} is sold in the price list and the plans page has no Arabic "
                        f"sentence for it — a key with no wording is not rendered at all, so it is "
                        f"charged for and invisible on the page where somebody decides to buy")

    for key in sorted(set(g) - s):
        problems.append(f"{key} is checked in {g[key][0]} and NO plan grants it — the feature is "
                        f"dead for every customer, including the ones paying the most, and nothing "
                        f"anywhere reports it")
    warnings: list[str] = []
    for key in sorted(s - set(g)):
        decided = SOLD_UNBUILT.get(key)
        if decided:
            warnings.append(f"{key}: sold and not built — {decided}")
            continue
        problems.append(f"{key} is sold in the price list and no code checks it — every shop gets "
                        f"it, and the customer who paid for the tier above is the one who finds out")

    for key in sorted(set(SOLD_UNBUILT) - s):
        problems.append(f"{key} is listed as sold-and-unbuilt and no plan sells it — delete the "
                        f"line, or the next reader trusts a note about nothing")

    for w in warnings:
        print(f"{C_Y}  ! {w}{C_N}")
    for p in problems:
        print(f"{C_R}  ✗ {p}{C_N}")
    if problems:
        print(f"\n{C_R}  ✗ {len(problems)} feature key(s) sold and enforced differently{C_N}")
        return 1
    print(f"{C_G}  ✔ all {len(s) - len(warnings)} feature keys are both sold and enforced{C_N}")
    if warnings:
        print(f"{C_Y}    {len(warnings)} key(s) sold and not built — see above{C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
