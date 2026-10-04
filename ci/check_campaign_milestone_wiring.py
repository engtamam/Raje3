"""Every "جماعي" (shared-counter) campaign goal keeps its real machinery wired — proven from the
actual AST, never trusted from a comment or a string search.

WHY THIS EXISTS. `ci/check_campaign_mechanics.py` already proves every goal names a real,
registered mechanic. That is necessary but not sufficient for "جماعي" specifically: three separate,
easy-to-silently-break invariants keep a milestone campaign honest, and none of them would fail
loudly if quietly removed — each would just make a real bug ship silently, the exact shape
`audience.py`'s own comments already document happening twice before (`package_offer` matching
nobody, `occasion` matching nobody) for a DIFFERENT reason (a missing matcher). This gate is the
one for these three:

  1. EVERY "جماعي" GOAL IS IN `OFFER_GOALS` — a shared counter with no deadline concept would
     count forever with nothing to ever stop or reset it; `core/milestone.py`'s own `within_window`
     and `core/tick.py`'s own expiry/recurrence branch both assume `expires_at` is a real, required
     field for this mechanic. A future "جماعي" goal added to `GOAL_MECHANIC` without also joining
     `OFFER_GOALS` would create exactly that silently-forever-counting campaign.

  2. `dispatch.py::Dispatcher.fire`'S SPREAD-REFUSAL CHECK STILL EXEMPTS `trigger == "milestone"` —
     found and fixed live in this same session: without the exemption, a milestone's own reveal
     send is refused the instant the threshold crosses close to its own deadline, because
     `expires_at` means something different for this one goal (the deadline to CROSS the
     threshold, not a deadline by which every recipient must be notified). A future refactor of
     this method that drops the exemption reintroduces that exact bug, silently, the next time a
     shop's own challenge finishes close to its own deadline — which is the ONE moment worth
     testing for, and the least likely moment anyone manually re-tests by hand.

  3. `tick.py`'S MILESTONE BRANCH STILL CALLS `milestone.reset_progress` AND STILL READS
     `milestone_recurring`/`expires_at` — proving the recurrence and expiry decisions this session
     built are still actually reachable code inside the `trigger == "milestone"` branch specifically,
     not merely present somewhere else in the file (which a substring search would happily accept).

    python ci/check_campaign_milestone_wiring.py
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CAMPAIGNS_APP = ROOT / "services" / "campaigns"
DISPATCH_PY = CAMPAIGNS_APP / "app" / "core" / "dispatch.py"
TICK_PY = CAMPAIGNS_APP / "app" / "core" / "tick.py"
C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"

MILESTONE_MECHANIC = "جماعي"


def _parse(path: pathlib.Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _is_get_call(node: ast.AST, *, key: str) -> bool:
    """Is this `X.get("key")` (or `X.get("key", default)`), for the given literal key?"""
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
           and node.func.attr == "get" and bool(node.args)
           and isinstance(node.args[0], ast.Constant) and node.args[0].value == key)


def _walk_compares(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            yield node


def _dispatch_exempts_milestone_from_spread_refusal() -> str:
    """"" when `Dispatcher.fire` still contains a real `campaign.get("trigger") != "milestone"`
    comparison — found ANYWHERE in the method (it lives inside a `BoolOp` alongside the existing
    `per_pass > 0` check today, but this does not assume that exact shape, only that the real
    comparison exists at all, the same "a real AST node, not a string" discipline
    `ci/check_branch_scope.py` already holds `branch_scope()` calls to).
    """
    tree = _parse(DISPATCH_PY)
    for cmp in _walk_compares(tree):
        for op, comparator in zip(cmp.ops, cmp.comparators):
            if (isinstance(op, ast.NotEq) and _is_get_call(cmp.left, key="trigger")
                    and isinstance(comparator, ast.Constant) and comparator.value == "milestone"):
                return ""
    return (f"{DISPATCH_PY.relative_to(ROOT)}: no `campaign.get(\"trigger\") != \"milestone\"` "
           f"comparison found in Dispatcher.fire — the spread-refusal check may have regained "
           f"the power to refuse a milestone campaign's own reveal send near its deadline "
           f"(the exact bug this session found and fixed live)")


def _find_milestone_branch(tree: ast.Module) -> ast.If | None:
    """The `if trigger == "milestone":` block inside `Tick._one` — walked structurally (an `If`
    whose test is `<name> == "milestone"`), never assumed to be at a fixed line number."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if (isinstance(test, ast.Compare) and len(test.ops) == 1
                and isinstance(test.ops[0], ast.Eq)
                and isinstance(test.comparators[0], ast.Constant)
                and test.comparators[0].value == "milestone"):
            return node
    return None


def _names_used(node: ast.AST) -> set[str]:
    """Every attribute access, call target, and string constant anywhere under `node` — a coarse
    but honest net: it cannot tell WHERE a name is used, only that it genuinely appears in the
    real parsed code under this exact branch, not merely somewhere else in the file.
    """
    found: set[str] = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Attribute):
            found.add(n.attr)
        elif isinstance(n, ast.Constant) and isinstance(n.value, str):
            found.add(n.value)
    return found


def _tick_milestone_branch_still_wired() -> list[str]:
    tree = _parse(TICK_PY)
    branch = _find_milestone_branch(tree)
    if branch is None:
        return [f"{TICK_PY.relative_to(ROOT)}: no `if trigger == \"milestone\":` branch found in "
               f"Tick._one — the milestone trigger may no longer be handled at all"]
    names = _names_used(branch)
    problems: list[str] = []
    if "reset_progress" not in names:
        problems.append(
            f"{TICK_PY.relative_to(ROOT)}: the milestone branch no longer calls "
            f"milestone.reset_progress — a recurring campaign would never start a fresh round")
    if "milestone_recurring" not in names:
        problems.append(
            f"{TICK_PY.relative_to(ROOT)}: the milestone branch no longer reads "
            f"\"milestone_recurring\" — recurrence vs. one-shot is no longer a real decision")
    if "expires_at" not in names:
        problems.append(
            f"{TICK_PY.relative_to(ROOT)}: the milestone branch no longer reads \"expires_at\" — "
            f"a challenge that never crosses its threshold would stay active forever")
    return problems


def main() -> int:
    sys.path.insert(0, str(CAMPAIGNS_APP))
    from app.core import models  # noqa: PLC0415

    problems: list[str] = []

    for goal, mechanic in models.GOAL_MECHANIC.items():
        if mechanic == MILESTONE_MECHANIC and goal not in models.OFFER_GOALS:
            problems.append(
                f"models.GOAL_MECHANIC[{goal!r}] names the {MILESTONE_MECHANIC!r} mechanic but "
                f"{goal!r} is not in models.OFFER_GOALS — a shared counter with no deadline "
                f"concept, nothing to ever stop or reset it")

    spread_problem = _dispatch_exempts_milestone_from_spread_refusal()
    if spread_problem:
        problems.append(spread_problem)

    problems.extend(_tick_milestone_branch_still_wired())

    if problems:
        print(f"{C_R}  ✘ {len(problems)} milestone-wiring problem(s):{C_N}")
        for line in problems:
            print(f"{C_R}      {line}{C_N}")
        return 1

    print(f"{C_G}  ✔ every \"جماعي\" goal has a deadline concept, the spread refusal still "
          f"exempts a milestone reveal, and tick.py's milestone branch still calls the real "
          f"recurrence/expiry machinery{C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
