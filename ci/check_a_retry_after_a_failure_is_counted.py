"""A message retried after a failure must count its tries and be able to give up.

WHAT THIS IS THE LAST OF. The send engine had three ways for a message to disappear without a
trace, and two are closed: a render refusal thrown where nobody listened, and two refusals that
closed a schedule without writing a row. This is the third and it is the quietest of them.

`_fail` is what happens when anything in a row's pass raises. It returns the row to `pending` with
`due_at = now + 3600`, and its own docstring is honest about the assumption: «Most failures here
are a peer being briefly unavailable.» Most. The rest are not brief — a phone number Meta refuses,
a template rejected for this shop alone, a row whose data is malformed — and for those the same
inputs produce the same exception on every tick, hourly, for ever.

WHAT THAT COSTS. The message never arrives and never stops trying: no row in the send log, because
nothing was ever attempted as far as the log knows; no terminal state, so it is not in any report;
one wasted pass per hour per broken row for as long as the shop exists. The owner sees a customer
who was never messaged and has nothing to ask about. And the docstring's own comfort — «a row that
keeps failing shows up in the reason counts» — is about ONE tick's counts, which nobody stores and
no screen reads.

THE RULE. A function that hands a failed row back to `pending` must (1) read how many times it has
already failed, and (2) have somewhere to send it when the count runs out: a close, and a row in
the send log naming the last error. Retrying is fine; retrying blind, for ever, is not.

WHY IT NAMES THE FUNCTION. The other paths that return a row to `pending` are DECISIONS, not
failures — quiet hours, an engagement deferral, a daily ceiling — and they are open-ended on
purpose: tomorrow really can differ. Bounding those would be a product change dressed as a check.
So the rule is asked of the failure path alone, which is the only one whose retry cannot learn
anything.

    python ci/check_a_retry_after_a_failure_is_counted.py
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
ENGINE = ROOT / "services" / "reminders" / "app" / "core" / "tick.py"

#: The failure path, by name. One entry today; the shape is a mapping so a second engine that
#: grows one is added here rather than argued about.
RETRY_AFTER_FAILURE = {"_fail": "attempts"}


def _reads_key(fn: ast.AST, key: str) -> bool:
    """Does the body look at `key` — as a subscript, a `.get`, or a keyword?"""
    for node in ast.walk(fn):
        if isinstance(node, ast.Constant) and node.value == key:
            return True
    return False


def _calls(fn: ast.AST, attr: str) -> bool:
    return any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
               and n.func.attr == attr for n in ast.walk(fn))


def main() -> int:
    if not ENGINE.is_file():
        print(f"{ENGINE.relative_to(ROOT)} is missing — the engine this gate reads is not where "
              f"it was, and «cannot find it» has never been a pass here")
        return 1

    tree = ast.parse(ENGINE.read_text(encoding="utf-8"))
    found: dict[str, ast.AST] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name in RETRY_AFTER_FAILURE:
                found[node.name] = node

    missing = sorted(set(RETRY_AFTER_FAILURE) - set(found))
    if missing:
        # A RENAMED FUNCTION IS NOT A FIXED ONE. If the retry moved, this gate must be pointed at
        # where it went — deliberately, in a diff somebody reads.
        print("  \033[31m✘ the failure path this gate watches no longer exists under that name:"
              "\033[0m")
        for name in missing:
            print(f"      \033[31m{name}\033[0m")
        return 1

    bad: list[str] = []
    for name, fn in sorted(found.items()):
        key = RETRY_AFTER_FAILURE[name]
        if not _reads_key(fn, key):
            bad.append(f"{name}: never looks at «{key}» — it retries without knowing how many "
                       f"times it already has")
        if not _calls(fn, "_close"):
            bad.append(f"{name}: has no terminal branch — a row that keeps failing has nowhere "
                       f"to end")
        if not _calls(fn, "append"):
            bad.append(f"{name}: gives up without writing a row — the send log is where a message "
                       f"that never went is supposed to appear")

    if bad:
        print("  \033[31m✘ a failed message is retried blind:\033[0m")
        for line in bad:
            print(f"      \033[31m{line}\033[0m")
        print("\n    Count the attempts on the row, and when they run out close it and log the "
              "last error.\n    An hourly retry that can never succeed is a message nobody "
              "receives and nobody can see.\n    Do not exempt it here.")
        return 1

    print(f"  \033[32m✔ every retry after a failure is counted and can give up "
          f"({len(found)} path(s))\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
