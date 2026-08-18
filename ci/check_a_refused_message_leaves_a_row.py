"""A message the engine refuses must leave a row in the send log — every refusal, without exception.

WHAT THE SEND LOG IS FOR, in its own words: «What went out, or what did not and why. The ledger
every cap is counted against.» It is the only record in the product that a message ever existed,
and «رسائلي» reads it to answer the one question support is ever asked — «لماذا لم تصل الرسالة؟»

SO A REFUSAL THAT WRITES NOTHING IS A MESSAGE THAT NEVER HAPPENED. Not late, not blocked: absent
from history. Two of them shipped:

  · the customer was erased or was never there (`Unsendable`) — the row was closed and nothing was
    logged, so an owner asking why his customer heard nothing found a schedule that had quietly
    ended and no reason anywhere;

  · the owner switched that trigger off — the messages already scheduled under it were dropped in
    silence, which is precisely the moment he most wants a record («أوقفتُه أمس، هل خرجت رسائل؟»).

AND THE CAMPAIGN PATH REFUSES IN A DIFFERENT SHAPE, which is how three more survived a gate
written for the first one. `send_one` has no schedule to close — «it is decided, sent, and
recorded, and nothing waits for it» — so it says no by RETURNING `{"sent": False, …}`. Three of its
six refusals wrote nothing: a render that failed, an erased recipient, and the daily ceiling. A
campaign of a hundred and forty people, every one of them refused, left the owner a screen with no
rows on it at all.

So the rule is one rule with two shapes, and widening the PATTERN is the fix — never narrowing the
scope until the second shape falls outside it.

THE RULE, AND THE REASON IT IS ABOUT `suppressed` ALONE. `_close` ends a schedule in one of four
states. `sent` already logs, immediately above the call. `merged` is not a refusal — the folded row
has no message of its own and the lead's row names it, so logging here would count one message
twice, which is the opposite of what a ledger is for. `failed` returns to pending and is not an
ending at all. What is left is `suppressed`: we decided this message will not go, and that decision
is the thing the log exists to hold.

    python ci/check_a_refused_message_leaves_a_row.py
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
ENGINE = ROOT / "services" / "reminders" / "app" / "core" / "tick.py"

#: The state that means «this message will not go».
REFUSED = "suppressed"

#: The campaign path's way of saying the same thing: it returns rather than closing.
NOT_SENT = "sent"


def _is_call(node: ast.AST, attr: str) -> bool:
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == attr)


def _calls_in(stmt: ast.AST, attr: str) -> list[ast.Call]:
    return [n for n in ast.walk(stmt) if _is_call(n, attr)]


def _returns_not_sent(stmt: ast.AST) -> bool:
    """`return {"sent": False, …}` — a refusal with no schedule behind it."""
    if not isinstance(stmt, ast.Return) or not isinstance(stmt.value, ast.Dict):
        return False
    for key, value in zip(stmt.value.keys, stmt.value.values):
        if (isinstance(key, ast.Constant) and key.value == NOT_SENT
                and isinstance(value, ast.Constant) and value.value is False):
            return True
    return False


def _closes_as_refused(call: ast.Call) -> bool:
    for arg in call.args:
        if isinstance(arg, ast.Constant) and arg.value == REFUSED:
            return True
    for kw in call.keywords:
        if isinstance(kw.value, ast.Constant) and kw.value.value == REFUSED:
            return True
    return False


def main() -> int:
    if not ENGINE.is_file():
        print(f"{ENGINE.relative_to(ROOT)} is missing — the engine this gate reads is not where "
              f"it was, and «cannot find it» is not a pass")
        return 1

    tree = ast.parse(ENGINE.read_text(encoding="utf-8"))

    bad: list[str] = []
    # BY LINE, BECAUSE THE WALK REVISITS. A statement nested three blocks deep is reached once per
    # enclosing block, and a count that says «33 refusals» about eleven of them is a number that
    # would quietly stop meaning anything.
    seen: set[int] = set()

    # THE UNIT IS A BRANCH, NOT A FUNCTION. A function-wide check would let one logged refusal
    # excuse an unlogged one in a different `if` — which is exactly how these two survived beside
    # nine correct siblings.
    for node in ast.walk(tree):
        for field in ("body", "orelse", "finalbody"):
            block = getattr(node, field, None)
            if not isinstance(block, list):
                continue
            logged = any(_calls_in(s, "append") for s in block)
            for stmt in block:
                for call in _calls_in(stmt, "_close"):
                    if not _closes_as_refused(call):
                        continue
                    seen.add(call.lineno)
                    if not logged:
                        bad.append(f"{ENGINE.relative_to(ROOT)}:{call.lineno}")
                if _returns_not_sent(stmt):
                    seen.add(stmt.lineno)
                    if not logged:
                        bad.append(f"{ENGINE.relative_to(ROOT)}:{stmt.lineno}")

    if bad:
        print("  \033[31m✘ a message is refused and no row records it:\033[0m")
        for line in sorted(set(bad)):
            print(f"      \033[31m{line}\033[0m")
        print("\n    Append a SendLog row in the same branch, carrying the reason. A refusal "
              "nobody can read is\n    a message that, as far as this product can tell, never "
              "existed. Do not exempt it here.")
        return 1

    print(f"  \033[32m✔ every refused message leaves a row ({len(seen)} refusal(s))\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
