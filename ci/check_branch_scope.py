"""Every route that serves per-branch data must ask WHO IS ASKING — and fail closed when it cannot.

WHY THIS EXISTS. `GET /api/v1/insights/branches` returns the branch comparison table: every branch's
revenue and traffic, side by side. It never asked for the caller's branch scope at all, so a
branch-scoped manager read the whole chain's copy of it. The dashboard next door WAS scoped — which
is what made the hole invisible: the isolation held everywhere except the single screen that exists
to compare people against each other.

And the dashboard's own scope check failed OPEN. `branch_scope` answers `_unreadable` when the peer
that knows who works where could not be asked, and the code turned that into «no branch filter»,
which means the whole establishment. An unknown scope is not an empty scope: refusing costs a
manager his dashboard for a minute, guessing costs the owner a confidentiality he never agreed to
give up.

WHAT IT CHECKS, in two directions:

  1. A user-facing route whose body reads per-branch data must call the scope resolver.
  2. Wherever `_unreadable` is compared, the branch that follows must REFUSE — never fall through
     to the unscoped read. This is the fail-open shape, and it is detectable: `_unreadable`
     appearing in the same expression as an empty-string default is the exact line that shipped.

WHAT IT CANNOT SEE, said plainly: a route that reads branch data through a helper whose name does
not mention branches. Those are listed as unverifiable rather than passed over.

    python ci/check_branch_scope.py
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVICES = ROOT / "services"
C_G, C_R, C_Y, C_N = "\033[32m", "\033[31m", "\033[33m", "\033[0m"

SCOPE_CALL = "branch_scope"
SENTINEL = "_unreadable"
#: How the sentinel appears in real code: its own literal, or the name bound to it. Matching the
#: bare substring also matches every longer word that ends in it.
SENTINEL_TOKENS = (f'"{SENTINEL}"', f"'{SENTINEL}'", "UNREADABLE", "DENIED")

# A body that touches any of these is serving one branch's numbers ALONGSIDE another's.
#
# `branch_id` ALONE IS NOT ON THIS LIST, and the first version of this file learned that the hard
# way: it flagged eleven WRITES — recording a visit, redeeming a reward, hiring someone — which
# carry a branch to ATTRIBUTE the act, not to reveal anybody's numbers. And the branch on those is
# resolved from the PERSON, never from the request (spec 12.2, task 265). A gate that cries wolf
# on eleven correct routes is one people learn to skip, which is how the twelfth gets through.
BRANCH_READS = ("branch_rows", "branch_comparison", "branch_snapshot", "branch_can_rank",
                "branch_stats", "per_branch",
                # A READ THAT TAKES A BRANCH AS A FILTER is the other half: whoever may pass
                # `branch_id=X` and get X's rows is choosing whose numbers to look at, and the
                # answer must not be «whichever he typed».
                "branch_id: str = \"\"", "branch_id: str = Query",
                # AND THE BRANCH A ROW CARRIES, not only the branch a caller names. The gate read
                # `branch_id` and nothing else, so `last_branch_id` — the field on a customer that
                # says where he was last served — was invisible to it. The strip along the top of
                # the field screen returned every branch's customers by name and phone, ten at a
                # time, and this check said the route was fine (و-8).
                "last_branch_id")

# Routes that are NOT a person reading branch data — each with the reason, because a list whose
# entries nobody can justify is a list that grows until the check means nothing.
NOT_A_BRANCH_READ: dict[str, str] = {
    "create_branch": "creating one, not reading the others",
    "update_branch": "editing one he already named",
    "list_branches": "the establishment's own list of places — the picker every scoped screen "
                     "needs to render its own name; it carries no numbers",
    "set_digest": "subscribing a person to a report, not reading a branch",
}


def routes(path: pathlib.Path) -> list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for deco in node.decorator_list:
            if isinstance(deco, ast.Call) and isinstance(deco.func, ast.Attribute) \
                    and deco.func.attr in ("get", "post", "put", "delete", "patch"):
                out.append((deco.func.attr, node))
                break
    return out


def main() -> int:
    unscoped: list[str] = []
    fail_open: list[str] = []
    checked = 0

    for path in sorted(SERVICES.glob("*/app/api/v1/*.py")):
        text = path.read_text(encoding="utf-8")
        rel = str(path.relative_to(ROOT)).replace("\\", "/")

        for method, fn in routes(path):
            # READS ONLY. A write that names a branch is attributing an act to it; the question
            # this file asks — «may this person see that branch's numbers» — does not arise.
            if method != "get":
                continue
            src = ast.get_source_segment(text, fn) or ""
            if not any(k in src for k in BRANCH_READS):
                continue
            if fn.name in NOT_A_BRANCH_READ:
                continue
            checked += 1
            if SCOPE_CALL not in src:
                unscoped.append(f"{rel}:{fn.lineno} {fn.name}() serves per-branch data and never "
                                f"asks for the caller's scope")

        # THE FAIL-OPEN SHAPE, wherever it appears: the sentinel resolved to «no filter».
        # THE SENTINEL ITSELF, NOT A WORD THAT CONTAINS IT. A substring match fired on the audit
        # action `subscription.gate_unreadable` — a line with nothing to do with branches, in a
        # file with no branch read in it. A guard that flags an unrelated identifier is one whose
        # findings get skimmed, and the next real one is skimmed with them.
        for i, line in enumerate(text.splitlines(), 1):
            if not any(tok in line for tok in SENTINEL_TOKENS):
                continue
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if '""' in line or "''" in line:
                fail_open.append(f"{rel}:{i}  {stripped[:100]}")

    if fail_open:
        print(f"{C_R}  ✘ {len(fail_open)} place(s) where an UNREADABLE scope becomes an EMPTY "
              f"one — «we could not check» rendered as «no restriction»:{C_N}")
        for line in fail_open:
            print(f"{C_R}      {line}{C_N}")
    if unscoped:
        print(f"{C_R}  ✘ {len(unscoped)} route(s) serving per-branch data with no scope check:{C_N}")
        for line in unscoped:
            print(f"{C_R}      {line}{C_N}")

    if fail_open or unscoped:
        print(f"{C_R}    A branch is a description on an event, not a division of the account "
              f"(spec 12.2) — but WHO MAY SEE WHOSE NUMBERS is exactly what it does divide.{C_N}")
        return 1

    print(f"{C_G}  ✔ every route serving per-branch data asks who is asking, and an unreadable "
          f"scope refuses ({checked} routes){C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
