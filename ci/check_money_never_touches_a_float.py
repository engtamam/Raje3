#!/usr/bin/env python3
"""MONEY IS NEVER MULTIPLIED BY A FLOAT.

THE DEFECT, AND ITS OWN COMMENT DEFENDED IT (ح-5).

    return int(self.net_minor * self.rate)

with a docstring saying «never on a float» and «deterministic here because the result is
truncated». Both sentences are wrong, and the second is wrong in the way that matters: `int()`
truncates a value that BINARY FLOATING POINT already got wrong.

    100000 * 0.29  →  28999.999999999996  →  int()  →  28999

Twenty-nine thousand halalas becomes twenty-eight thousand nine hundred and ninety-nine. And it is
not a rounding policy anybody chose — 0.30 gives the exact answer and 0.29 does not, because 0.29
has no exact binary representation and 0.30 lands close enough. So a partner on 30% is paid
correctly, a partner on 29% is short one halala per statement, and nobody can tell from the code
which of them is which without running it.

ONE HALALA IS NOT THE POINT. The point is that the statement is not reproducible from its inputs
by anybody checking it — a partner who computes 29% of the net and compares gets a different
number than we do, and the difference has no explanation in any line of the file.

THE RULE, AND IT HAS NO EXCEPTIONS TABLE. In a module that computes money, a name ending in
`_minor` may not appear in a `*` or `/` with a float — neither a float literal nor a name holding
a rate. `Decimal` is exact for the decimal fractions money uses, and `Decimal(x) * Decimal(str(r))`
gives the same answer on every machine and matches what a person gets on paper.

WHY `_minor` RATHER THAN «anything that looks like money». Because the suffix is this codebase's
own convention for «an integer count of the smallest currency unit», applied consistently, and a
gate that guessed at money by name would sweep in row counts and message caps — and a gate that
overreaches gets loosened.
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVICES = ROOT / "services"

C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"

MONEY_SUFFIX = "_minor"


def _mentions_money(node: ast.AST) -> bool:
    """Does this expression read a `*_minor` value?"""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and sub.id.endswith(MONEY_SUFFIX):
            return True
        if isinstance(sub, ast.Attribute) and sub.attr.endswith(MONEY_SUFFIX):
            return True
    return False


def _is_decimal(node: ast.AST) -> bool:
    """`Decimal(...)` — exact by construction, so nothing inside it is a float."""
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == "Decimal")


def _float_operand(node: ast.BinOp) -> str:
    """The float in this expression, described — or an empty string if there is none.

    SUBTREES UNDER `Decimal(...)` ARE NOT WALKED, and that matters: the correct spelling of the
    fix is `Decimal(net_minor) * Decimal(str(self.rate))`, which still CONTAINS the name `.rate`.
    A gate that cannot tell the repair from the defect is a gate somebody deletes on the day they
    fix something — so the traversal is explicit rather than `ast.walk`, which has no way to skip
    a branch once it has queued it.
    """
    stack: list[ast.AST] = [node]
    while stack:
        sub = stack.pop()
        if _is_decimal(sub):
            continue                          # exact — and neither is anything below it
        if isinstance(sub, ast.Constant) and isinstance(sub.value, float):
            return repr(sub.value)
        # A NAME CALLED `rate`, `factor`, `percent`… IS THE COMMON CASE and is exactly what the
        # commission bug was: `self.rate` is a float field, and nothing at the call site says so.
        if isinstance(sub, ast.Attribute) and sub.attr in ("rate", "factor", "multiplier", "pct"):
            return f"`.{sub.attr}` (a rate)"
        if isinstance(sub, ast.Name) and sub.id in ("rate", "factor", "multiplier", "pct"):
            return f"`{sub.id}` (a rate)"
        stack.extend(ast.iter_child_nodes(sub))
    return ""


def main() -> int:
    if not SERVICES.is_dir():
        print(f"{C_R}no services/ — this gate checked nothing, and an empty set is not "
              f"agreement{C_N}")
        return 1

    bad: list[str] = []
    checked = 0

    files = [p for p in sorted(SERVICES.rglob("*.py"))
             if "test" not in p.parts and not p.name.startswith("test_")]
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError) as exc:
            bad.append(f"{rel}: cannot read it — {exc}")
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.BinOp) or not isinstance(node.op, (ast.Mult, ast.Div)):
                continue
            if not _mentions_money(node):
                continue
            checked += 1
            found = _float_operand(node)
            if not found:
                continue
            bad.append(
                f"{rel}:{node.lineno}: a `{MONEY_SUFFIX}` amount is multiplied by {found}. Binary "
                f"floating point cannot hold most decimal rates exactly — `100000 * 0.29` is "
                f"28999.999999999996, and truncating that gives 28999 rather than 29000. The "
                f"statement stops being reproducible by the person it is paid to")

    if bad:
        print(f"{C_R}money is being multiplied by a float{C_N}")
        for line in bad:
            print(f"  {line}")
        print("\n  Use Decimal: `int(Decimal(amount) * Decimal(str(rate)))`. `str(rate)` is not "
              "decoration — Decimal(0.29) inherits the float's error.")
        return 1

    if checked == 0:
        print(f"{C_R}no money arithmetic found — either the `{MONEY_SUFFIX}` convention changed "
              f"or this gate no longer matches it, and an empty set is not agreement{C_N}")
        return 1

    print(f"{C_G}ok{C_N}  {checked} money expressions, not one of them through a float")
    return 0


if __name__ == "__main__":
    sys.exit(main())
