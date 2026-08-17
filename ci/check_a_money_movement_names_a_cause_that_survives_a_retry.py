#!/usr/bin/env python3
"""EVERY LEDGER MOVEMENT IS CAUSED BY SOMETHING THE CALLER NAMED — never by an id we just made up.

THE DOUBLE DEDUCTION THIS EXISTS FOR, AND THE RECONCILER WAS RATIFYING IT.

`ledger.post` refuses a movement whose `(tenant, source, reason)` it has already recorded. That is
the only thing standing between a retry and a customer paying twice for one reward. It works when
`source` is stable across attempts — a visit id, an idempotency key, the lapse being expired — and
it is silently useless when `source` is generated fresh inside the call.

`redeem` passed `rec.id`: a new uuid on every attempt. So:

  1. `ledger.post` deducted the points and succeeded,
  2. the process died before the REDEMPTIONS receipt was written,
  3. the retry looked for the receipt, found nothing, and walked past every check,
  4. `already_posted` compared a NEW uuid against the old one and said «no, go ahead»,
  5. the points came out a second time.

The `if entry is None` guard below that call was therefore DEAD CODE on the field path — it could
only ever fire for the till, which passes an explicit source. And `SpendLock` did not help: it
holds for fifteen seconds, and the retry that matters is the one after a timeout.

WORST OF ALL, THE CORRECTION CEMENTED IT. `/platform/reconcile` resets a balance to the sum of the
ledger, and the ledger held both deductions — so the one tool built to fix drift was ratifying it.
A wrong number somebody audited is harder to find than a wrong number nobody did.

THE RULE, AND IT HAS NO EXCEPTIONS TABLE. The `source` of a movement must trace back to something
the CALLER supplied — a parameter of the enclosing function, a module constant, or a named
derivation over those. A locally-constructed object's `.id`, a bare `uuid4()`, a timestamp: all
refused, because none of them is the same on the second attempt.

WHY THIS SHAPE RATHER THAN «check redeem.py». Because three of the four call sites were already
correct, and they were correct by the author's care rather than by anything enforcing it. The
fourth was written by somebody equally careful who reached for the id that was in scope. The next
movement — a refund, a partner payout, a correction — will be written the same way.
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVICES = ROOT / "services"

C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"

# Names that are never a stable cause, whatever they are attached to.
FRESHLY_MADE = ("uuid", "uuid4", "token_hex", "randint", "random", "time", "now", "monotonic")


def _root_name(node: ast.AST) -> str:
    """The base identifier of an expression: `rec.id` -> `rec`, `a.b.c()` -> `a`."""
    while True:
        if isinstance(node, ast.Attribute):
            node = node.value
        elif isinstance(node, ast.Call):
            node = node.func
        elif isinstance(node, ast.Subscript):
            node = node.value
        elif isinstance(node, ast.BoolOp):           # `source or fallback` — check both sides
            return ""
        else:
            break
    return node.id if isinstance(node, ast.Name) else ""


def _constructs(node: ast.AST) -> bool:
    """Is this a call that MAKES a new thing, rather than one that derives from what it is given?

    THE DISTINCTION THAT MATTERS, and the first sabotage of this gate slipped through without it.
    `_cause(tenant, idem_key)` is pure over its inputs: same arguments, same answer, every attempt.
    `Redemption(tenant=..., reward_id=...)` takes the same arguments and mints a NEW id inside —
    which is the entire defect, wearing arguments that look like caller input.

    Capitalisation is the signal, and it is the one Python itself relies on: a class is
    `Redemption`, a derivation is `_cause`. It is a convention rather than a proof, and a gate
    built on a convention this consistent is worth more than one that cannot tell them apart.
    """
    root = _root_name(node)
    return isinstance(node, ast.Call) and bool(root) and root[:1].isupper()


def _operands(node: ast.AST) -> list[ast.AST]:
    """`a or b or c` flattens; anything else is itself. Every branch must be a valid cause."""
    if isinstance(node, ast.BoolOp):
        out: list[ast.AST] = []
        for v in node.values:
            out.extend(_operands(v))
        return out
    return [node]


class _Visitor(ast.NodeVisitor):
    def __init__(self, rel: str) -> None:
        self.rel = rel
        self.bad: list[str] = []
        self.checked = 0
        self._scope: list[set[str]] = []

    def _enter(self, node) -> None:
        a = node.args
        names = {x.arg for x in (*a.posonlyargs, *a.args, *a.kwonlyargs)}
        if a.vararg:
            names.add(a.vararg.arg)
        if a.kwarg:
            names.add(a.kwarg.arg)
        # A LOCAL THAT ONLY EVER HOLDS CALLER INPUT IS CALLER INPUT. Refusing to follow one
        # assignment would force the fix to be written as an unreadable expression inline — and a
        # gate that dictates awkward code gets worked around rather than obeyed. So a local bound
        # once, from an expression this same rule accepts, is treated as the thing it was bound to.
        for sub in ast.walk(node):
            if (isinstance(sub, ast.Assign) and len(sub.targets) == 1
                    and isinstance(sub.targets[0], ast.Name)):
                if all(self._is_supplied(o, names) for o in _operands(sub.value)):
                    names.add(sub.targets[0].id)
        self._scope.append(names)
        self.generic_visit(node)
        self._scope.pop()

    @staticmethod
    def _is_supplied(operand: ast.AST, params: set[str]) -> bool:
        """Would this expression pass the rule on its own?"""
        if isinstance(operand, ast.Constant):
            return True
        root = _root_name(operand)
        if not root or root in FRESHLY_MADE or root.startswith("_uuid"):
            return False
        if _constructs(operand):
            return False
        return isinstance(operand, ast.Call) or root in params

    visit_FunctionDef = _enter
    visit_AsyncFunctionDef = _enter

    def visit_Call(self, node: ast.Call) -> None:
        kw = {k.arg: k.value for k in node.keywords if k.arg}
        # A ledger movement: it names both a reason and a signed delta. Matching on the method name
        # alone would sweep in every `.post()` in the fleet, most of which are HTTP.
        if not (isinstance(node.func, ast.Attribute) and node.func.attr == "post"
                and "reason" in kw and "delta" in kw):
            self.generic_visit(node)
            return

        self.checked += 1
        line = node.lineno
        src = kw.get("source")
        if src is None:
            self.bad.append(f"{self.rel}:{line}: a movement with no `source` cannot be "
                            f"deduplicated at all — a retry posts it again")
            self.generic_visit(node)
            return

        params = set().union(*self._scope) if self._scope else set()
        for operand in _operands(src):
            if isinstance(operand, ast.Constant):
                continue                              # a literal is stable by definition
            root = _root_name(operand)
            if not root:
                continue
            if root in FRESHLY_MADE or root.startswith("_uuid"):
                self.bad.append(
                    f"{self.rel}:{line}: `source` comes from `{root}` — a value that differs on "
                    f"every attempt, so `already_posted` compares two causes and lets the retry "
                    f"through. Derive it from the caller's idempotency key")
                continue
            if _constructs(operand):
                self.bad.append(
                    f"{self.rel}:{line}: `source` is built by `{root}(...)`, which mints a new "
                    f"identity every call. The arguments look like caller input; the id it returns "
                    f"is not — and that is precisely how this got past review the first time")
                continue
            if isinstance(operand, ast.Call):
                continue                              # a named derivation; its own tests own it
            if root not in params:
                self.bad.append(
                    f"{self.rel}:{line}: `source` is `{ast.unparse(operand)}`, which is built here "
                    f"rather than supplied by the caller. A locally-made id is new on the retry — "
                    f"the deduplication silently passes and the money moves twice")
        self.generic_visit(node)


def main() -> int:
    bad: list[str] = []
    checked = 0

    files = sorted(SERVICES.rglob("*.py"))
    if not files:
        print(f"{C_R}no service modules found — this gate checked nothing, which is not the same "
              f"as finding nothing wrong{C_N}")
        return 1

    for path in files:
        if "test" in path.parts or path.name.startswith("test_"):
            continue
        rel = path.relative_to(ROOT).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, ValueError, UnicodeDecodeError) as exc:
            bad.append(f"{rel}: cannot parse it — {exc}")
            continue
        v = _Visitor(rel)
        v.visit(tree)
        bad.extend(v.bad)
        checked += v.checked

    if bad:
        print(f"{C_R}a money movement names a cause that does not survive a retry{C_N}")
        for line in bad:
            print(f"  {line}")
        print("\n  See services/loyalty/app/core/redeem.py: `_cause`.")
        return 1

    if checked == 0:
        print(f"{C_R}no ledger movement found — either they moved or this gate no longer matches "
              f"them, and an empty set is not agreement{C_N}")
        return 1

    print(f"{C_G}ok{C_N}  {checked} ledger movements, every cause supplied by the caller")
    return 0


if __name__ == "__main__":
    sys.exit(main())
