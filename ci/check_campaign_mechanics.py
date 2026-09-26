"""Every campaign goal names a real, wired mechanic — never a word with nothing behind it.

WHY THIS EXISTS. `services/campaigns/app/core/goals.py::CARDS` gives every goal a `"mechanic"` —
today always `"فردي"`, the one mechanic that exists (one candidate, matched independently, per
`app.core.audience.resolve`). `services/campaigns/app/core/mechanics.py::MECHANIC_RESOLVERS` is the
registry that turns that word into the real resolver function `container.py` actually calls.

This is the exact same failure mode `services/campaigns/app/core/audience.py`'s own comments already
document happening TWICE before there was any gate at all: `package_offer` shipped with no matcher
in `_MATCHERS` and matched nobody, silently, until 2026-09-12; `occasion` matched nobody for as long
as the goal existed because the field it read was never written. A goal naming a mechanic with no
resolver registered would be the same silent gap one level up — `mechanics.resolver_for` raises
loudly at RUNTIME, but a fleet with no traffic on a brand-new goal could ship that gap for weeks
before anyone presses the button that finds it. This gate finds it at BUILD time instead.

WHAT IT CHECKS, mirroring `ci/check_branch_scope.py`'s own "don't trust the registry's own claim"
discipline — never a runtime-only check:

  1. Every goal in `CARDS` names a mechanic that is one of `goals.MECHANICS` — a typo here
     (`"فرد"` instead of `"فردي"`) must fail the build, not fall through to `mechanics.py`'s own
     `KeyError`-shaped `ValueError` the first time a real campaign of that goal fires.
  2. Every mechanic in `goals.MECHANICS` has a real, registered resolver in
     `mechanics.MECHANIC_RESOLVERS` — a mechanic named in the registry with nothing wired to it is
     exactly as dead as a goal `_MATCHERS` never got a row for.
  3. Every goal in `CARDS` also appears in `models.GOAL_TEMPLATE` — `goals.resolve_goal`'s own
     docstring already promises this ("a new goal is a row in CARDS and a row in GOAL_TEMPLATE, not
     a change in four files where the fourth is forgotten"), but nothing enforced the promise until
     this gate; a goal missing from `GOAL_TEMPLATE` raises a bare `KeyError` the first time
     `resolve_goal` is actually called for it.
  4. No orphaned resolver — every key in `MECHANIC_RESOLVERS` is actually named by at least one
     goal in `CARDS`, so a mechanic nobody uses cannot sit there unnoticed, half-built and untested
     by anything that exercises it.

    python ci/check_campaign_mechanics.py
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CAMPAIGNS_APP = ROOT / "services" / "campaigns"
C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"


def main() -> int:
    sys.path.insert(0, str(CAMPAIGNS_APP))
    from app.core import goals, mechanics, models  # noqa: PLC0415

    problems: list[str] = []

    for goal, meta in goals.CARDS.items():
        mechanic = meta.get("mechanic", "")
        if mechanic not in goals.MECHANICS:
            problems.append(
                f"goals.CARDS[{goal!r}] names mechanic {mechanic!r}, not one of "
                f"goals.MECHANICS ({sorted(goals.MECHANICS)})")
        elif mechanic not in mechanics.MECHANIC_RESOLVERS:
            problems.append(
                f"goals.CARDS[{goal!r}]'s mechanic {mechanic!r} is a real entry in "
                f"goals.MECHANICS but has no resolver in mechanics.MECHANIC_RESOLVERS")
        if goal not in models.GOAL_TEMPLATE:
            problems.append(
                f"goals.CARDS[{goal!r}] has no row in models.GOAL_TEMPLATE — "
                f"goals.resolve_goal({goal!r}) will raise KeyError the first time it is called")

    used_mechanics = {meta.get("mechanic", "") for meta in goals.CARDS.values()}
    orphaned = sorted(set(mechanics.MECHANIC_RESOLVERS) - used_mechanics)
    for mechanic in orphaned:
        problems.append(
            f"mechanics.MECHANIC_RESOLVERS[{mechanic!r}] is registered but no goal in "
            f"goals.CARDS names it — an untested, unreachable mechanic")

    if problems:
        print(f"{C_R}  ✘ {len(problems)} campaign-mechanic wiring problem(s):{C_N}")
        for line in problems:
            print(f"{C_R}      {line}{C_N}")
        print(f"{C_R}    A goal is a row in CARDS, a row in GOAL_TEMPLATE, and its mechanic is a "
              f"real resolver — not a change in three files where one is forgotten.{C_N}")
        return 1

    print(f"{C_G}  ✔ every campaign goal names a real mechanic with a real resolver, and every "
          f"goal has its GOAL_TEMPLATE row ({len(goals.CARDS)} goals, "
          f"{len(mechanics.MECHANIC_RESOLVERS)} mechanic(s)){C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
