"""The screen that asks «هل كل شيء يعمل؟» must not count a failing message as a calm one.

WHAT IT REPORTS TODAY. The owner's health summary answers with two numbers — how many went out
today, and how many are waiting — and «waiting» is every row in `pending`. That was a complete
answer while `pending` meant one thing.

IT NO LONGER DOES. A message whose pass throws goes back to `pending` with `due_at` an hour out
and its `attempts` raised: a number Meta refuses, a template rejected for this shop alone, a peer
that is down. So `pending` now holds two different states wearing the same word — a reminder
calmly booked for next Tuesday, and a message that has failed twelve times in a row and will be
tried eight more before it is given up on.

Counting them together is the same defect the rest of this screen was built to avoid, one field
further along: the shop whose messages are all failing reads «12 في الانتظار» and concludes it is
working. The screen is NAMED after that question, and the one case it must never miss is the case
where nothing works.

THE RULE. Whatever the summary calls «waiting», it must have looked at `attempts` to decide it.
Separating the two, or naming the stuck ones, is a product choice; counting a failure as calm
without ever reading the field that says so is not.

    python ci/check_a_stuck_message_is_not_counted_as_calm.py
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
OWNER = ROOT / "services" / "reminders" / "app" / "api" / "v1" / "owner.py"

#: The field a retry raises, declared on the schedule in core/models.py.
ATTEMPTS = "attempts"

#: The key the summary reports the number under. Found by its RESPONSE KEY rather than by the
#: function's name: the endpoint may be renamed, and what the owner reads is the contract.
WAITING = "waiting"


def _mentions(node: ast.AST, text: str) -> bool:
    return any(isinstance(n, ast.Constant) and n.value == text for n in ast.walk(node))


def main() -> int:
    if not OWNER.is_file():
        print(f"{OWNER.relative_to(ROOT)} is missing — the summary this gate reads is not where "
              f"it was, and «cannot find it» is not a pass")
        return 1

    tree = ast.parse(OWNER.read_text(encoding="utf-8"))

    reporting: list[ast.AST] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _mentions(node, WAITING):
            reporting.append(node)

    if not reporting:
        # NOBODY REPORTS IT ANY MORE — which may be right, and is not something this gate may
        # decide by staying quiet. Point it at whatever replaced the number.
        print(f"  \033[31m✘ no function reports «{WAITING}» — the summary this gate watches has "
              f"moved or gone. Point it at what replaced it.\033[0m")
        return 1

    blind = [n.name for n in reporting if not _mentions(n, ATTEMPTS)]  # type: ignore[attr-defined]
    if blind:
        print("  \033[31m✘ a failing message is counted as a calm one:\033[0m")
        for name in blind:
            print(f"      \033[31m{name}() reports «{WAITING}» without ever reading "
                  f"«{ATTEMPTS}»\033[0m")
        print("\n    A row that has thrown and been rescheduled is not waiting, it is stuck. "
              "Count them apart\n    and say so — the screen is named after the question this "
              "number is the answer to. Do not\n    exempt it here.")
        return 1

    print(f"  \033[32m✔ what is waiting is told apart from what is stuck "
          f"({len(reporting)} summary)\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
