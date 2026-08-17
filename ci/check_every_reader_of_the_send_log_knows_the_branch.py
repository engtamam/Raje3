"""Whatever reads the send log resolves the caller's branch first (ط-4).

WHAT HAPPENED. Three owner-facing routes read `reminders`' send log, and exactly one of them —
`GET /log` — resolved the caller's branch scope. Its two neighbours, `/offer` and `/offers`, took a
`subject_ref` and nothing else. So a marketing supervisor confined to Jeddah needed one pseudonym
to read the text of every message Riyadh had sent that customer, the offer code the customer is
holding, and what it is worth: precisely the data the guarded route refuses him, through the door
beside it.

WHY A GATE. The guard was not forgotten out of carelessness — it was written on the route somebody
was thinking about branches while writing, and the other two were written while thinking about
offers. That is a pull, and the next route to read this collection will be written while thinking
about something else again. A check is the only thing that is thinking about branches every time.

NO EXCEPTIONS TABLE, and the SCOPE is narrow rather than the pattern: only handlers in this file,
only ones that touch `SendLogStore`. A reader that genuinely serves the whole shop says so by
calling `_branch_scope` and getting "" back — it does not say so by skipping the call.
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TARGET = ROOT / "services" / "reminders" / "app" / "api" / "v1" / "owner.py"
STORE = "SendLogStore"
RESOLVER = "_branch_scope"


def _names(node: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)} | {
        n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute)}


def main() -> int:
    if not TARGET.exists():
        # A GATE THAT CANNOT FIND WHAT IT GUARDS FAILS. If this file is renamed, the check must
        # stop and be re-pointed — not quietly pass because there is nothing left to look at.
        print(f"cannot find {TARGET.relative_to(ROOT).as_posix()} — this gate needs re-pointing")
        return 1
    try:
        tree = ast.parse(TARGET.read_text(encoding="utf-8"))
    except (OSError, SyntaxError) as exc:
        print(f"cannot read {TARGET.relative_to(ROOT).as_posix()}: {exc}")
        return 1

    bad = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        used = _names(node)
        if STORE not in used or RESOLVER not in used:
            if STORE in used:
                bad.append(f"{TARGET.relative_to(ROOT).as_posix()}:{node.lineno} · {node.name}")

    if bad:
        print(f"These read the send log without resolving the caller's branch (`{RESOLVER}`):")
        for line in bad:
            print("  " + line)
        print("\nOne pseudonym would then read another branch's messages, offer codes and values.")
        print(f"Call `{RESOLVER}(container, principal)` and filter with `_in_scope(row, scope)`.")
        return 1
    print("every reader of the send log knows the branch")
    return 0


if __name__ == "__main__":
    sys.exit(main())
