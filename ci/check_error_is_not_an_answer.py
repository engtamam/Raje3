#!/usr/bin/env python3
"""A PEER'S ERROR STATUS AND A PEER'S ANSWER MAY NOT BE JUDGED IN ONE CONDITION.

Every HTTP helper in this repository returns `(status, body)` and hands back an EMPTY body when
the transport or the peer failed — that is the honest thing for a helper to do, because there was
no answer to parse. What it means for the caller is that reading the body after an error status
reads a default, and a default has an opinion.

`reminders/core/quota.take` wrote it as one line:

    if status >= 400 or not out.get("allowed"):
        ...
        raise QuotaError("بلغت حدّ باقتك من النصوص الخاصة هذا الشهر.")

billing returns 500. `out` is `{}`. `out.get("allowed")` is None. The subscriber is told he has
reached a plan limit he never approached, and he telephones support about a package rather than
about an outage — which is the support call that costs us the customer AND tells us nothing.

THE RULE, AND IT NEEDS NO EXCEPTIONS. Decide the status first, on its own line, and decide the
body afterwards. The two questions are «did the peer answer?» and «what did it say?», and a
boolean operator between them answers neither.

The eight other status checks in this repository already do it that way — `quota.consume` two
methods above the defect, `core/subscribe`, `core/library`, `core/submission`. This gate keeps
them that way, because the shape reads perfectly well and fails only in production.

HOW IT READS. The condition of every `if`/`while` and every boolean expression is walked as an
AST: a comparison against a name that holds an HTTP status, joined by `and`/`or` to a subscript or
`.get(...)` on the body bound from the same call. No path is exempt — including this file, whose
own offending pattern is assembled from pieces below rather than written out, so the gate judges
its own source exactly as it judges everybody else's.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"

# The names a status lives in. Narrow on purpose: `n >= 400` on a count is not this defect, and a
# gate that guesses would need the exceptions table that makes a gate stop being one.
STATUS_NAMES = {"status", "status_code", "code", "http_status", "resp_status"}

# What "reading the answer" looks like. A `.get(...)` or a `[...]` on a name — the two ways a
# decoded JSON body is consulted anywhere in this repository.
BODY_READERS = ("get", "keys", "items")


def _is_status_test(node: ast.AST) -> bool:
    """`status >= 400`, `status != 200`, `status_code == 402` — a test of the transport outcome."""
    if not isinstance(node, ast.Compare):
        return False
    left = node.left
    if isinstance(left, ast.Attribute) and left.attr in STATUS_NAMES:
        return True
    return isinstance(left, ast.Name) and left.id in STATUS_NAMES


def _is_body_read(node: ast.AST) -> bool:
    """`out.get("allowed")`, `not body.get(...)`, `data["x"]` — a question about what it SAID."""
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return _is_body_read(node.operand)
    if isinstance(node, ast.Compare):
        return _is_body_read(node.left)
    if isinstance(node, ast.Subscript):
        return isinstance(node.value, ast.Name)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        return (node.func.attr in BODY_READERS
                and isinstance(node.func.value, ast.Name))
    return False


def offenders(tree: ast.AST) -> list[int]:
    """Line numbers where a status test and a body read share one boolean expression."""
    bad: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.BoolOp):
            continue
        has_status = any(_is_status_test(v) for v in node.values)
        has_body = any(_is_body_read(v) for v in node.values)
        if has_status and has_body:
            bad.append(node.lineno)
    return bad


def main() -> int:
    problems: list[str] = []
    checked = 0
    # EVERY python file we own, this one included. `platform/` is somebody else's repository.
    for py in sorted(ROOT.rglob("*.py")):
        rel = py.relative_to(ROOT).as_posix()
        if rel.startswith("platform/") or "/.venv/" in f"/{rel}":
            continue
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
        except (SyntaxError, OSError):
            continue
        checked += 1
        for line in offenders(tree):
            problems.append(f"{rel}:{line}: an error status and the answer's body are judged in "
                            f"one condition — an empty body then decides what the person reads")

    if problems:
        print(f"{C_R}an error status is being read as an answer{C_N}")
        for p in problems:
            print(f"  {p}")
        print("\n  Split it: refuse on the status first, then read the body.")
        return 1
    print(f"{C_G}ok{C_N}  {checked} files — no error status is joined to the answer it replaced")
    return 0


if __name__ == "__main__":
    sys.exit(main())
