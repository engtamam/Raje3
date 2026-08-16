"""A field a door accepts and no caller ever sends is a door with a hinge nobody fitted.

WHY THIS EXISTS (أ-2, أ-3). `POST /api/v1/visits` declares `operator_id` — and the field screen has
never once sent it. So every visit recorded from a phone has no operator on it, and `_branch_for`
reads exactly that field to decide which BRANCH the visit belongs to. The consequences all land
somewhere else:

  · the branch comparison table is a column of zeros, on a chain that bought branches;
  · `customer.last_branch_id` is never written, so a branch campaign finds nobody;
  · `actor` in the points ledger is blank — «من صرف نقاط هذا العميل؟» has no answer.

Nothing failed at any layer. The request is valid, the visit is saved, the screen says «تم». The
field is simply always its default, and a default is indistinguishable from a considered choice.

THIS IS THE MIRROR of `check_screens_send_declared_fields.py`. That one catches a screen sending
what no route declares; this one catches a route declaring what no screen sends. Both are the same
defect seen from the two ends, and each is invisible from the end the other watches.

WHAT IT CHECKS. For a door listed in DOORS below: every optional field on its request model is
mentioned somewhere in the console. Not «sent correctly» — mentioned at all, which is the weakest
possible claim and still enough to catch a field nothing has ever heard of.

WHY A LIST OF DOORS AND NOT EVERY ROUTE. Internal doors are called by services, not screens, and
sweeping those would report every one of them. The list is the routes a HUMAN SCREEN drives; it is
short, it is in this file, and a door added to the product without being added here is caught by
`check_actions_declared` instead — the catalogue is what the console can call at all.

    python ci/check_door_fields_are_sent.py
"""
from __future__ import annotations

import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONSOLE = ROOT / "apps" / "console" / "src"
C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"

#: (file, request model) for the doors a person's screen drives.
DOORS = [
    ("services/operations/app/api/v1/field.py", "VisitIn"),
    ("services/loyalty/app/api/v1/loyalty.py", "RedeemIn"),
]

#: Fields the screen has no business sending: the server fills them from the session or the row.
#: Each needs a reason, because a list nobody can justify is a list that grows until the check
#: means nothing.
SERVER_FILLED = {
    # Resolved from the operator's own row (spec 12.2) — a screen that sent one would be sending a
    # value nobody can check. See `_branch_for`.
    "branch_id",
}


def model_fields(path: pathlib.Path, name: str) -> dict[str, bool]:
    """field -> whether it is optional (has a default)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == name:
            out: dict[str, bool] = {}
            for stmt in node.body:
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                    src = ast.unparse(stmt.value) if stmt.value else ""
                    out[stmt.target.id] = "default" in src
            return out
    return {}


def main() -> int:
    console = "\n".join(p.read_text(encoding="utf-8")
                        for p in sorted(CONSOLE.rglob("*.ts*")))
    findings: list[str] = []
    checked = 0

    for rel, model in DOORS:
        path = ROOT / rel
        if not path.is_file():
            findings.append(f"{rel} is missing — this check names a door that no longer exists")
            continue
        for field, optional in model_fields(path, model).items():
            if not optional or field in SERVER_FILLED:
                continue
            checked += 1
            if not re.search(rf"\b{re.escape(field)}\b", console):
                findings.append(
                    f"{rel}  `{model}.{field}` is accepted by the door and the console never "
                    f"mentions it — the value is always its default, and a default cannot be "
                    f"told apart from a decision")

    if findings:
        print(f"{C_R}  ✘ {len(findings)} field(s) a door accepts that nothing ever sends:{C_N}")
        for line in findings:
            print(f"{C_R}      {line}{C_N}")
        print(f"{C_R}    Send it, or take it off the model. A field that is always absent is a "
              f"feature the code claims and the product does not have.{C_N}")
        return 1

    print(f"{C_G}  ✔ every optional door field is something a screen actually sends "
          f"({checked} fields){C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
