"""The same peer call must not be checked in one place and ignored in another.

WHY THIS EXISTS. `portal/api/page.py` calls `reminders.set_prefs` twice. The form path binds the
answer and renders the confirmation from it, with the reason written out beside it: «a customer who
is told their choice was saved and keeps receiving messages does not try again, they block the
number». The one-tap `/stop` path — the link inside every marketing message, the one designed to be
easy — calls the same method, throws the answer away, and renders `saved=True`.

So the customer taps «إيقاف»، reads «تم حفظ تفضيلاتك»، and the offers keep coming. He does not
retry, because he was told it worked. He blocks the shop's number, and the shop loses him and its
sender reputation together — for a save that never happened, on the one path we made frictionless
on purpose.

WHAT IT CHECKS. Within one module: a peer method whose result is bound somewhere
(`saved = await c.reminders.set_prefs(...)`) and discarded somewhere else
(`await c.reminders.set_prefs(...)` as a statement). The module has already decided the answer
matters; the second call is where that decision was forgotten.

WHY THIS SHAPE AND NOT «EVERY DISCARDED RESULT». Written that way it reported 189 places, nearly
all of them `_client.rpush` and `datastore.put` — calls whose answer genuinely means nothing. A
list that long is a list nobody reads to the end, and this defect would have sat in the middle of
it. So two things must both be true, and together they are exactly the defect: the file checks that
same call somewhere else (the author already decided the answer matters), AND this function goes on
to TELL SOMEBODY IT WORKED with a hard-coded success. That pair has no innocent form.

    python ci/check_same_call_same_care.py
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVICES = ROOT / "services"
C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"


def _name(node: ast.AST) -> str:
    """`c.reminders.set_prefs` -> "reminders.set_prefs" — the peer and the method, without the
    container variable, which is spelled differently in different files."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return ""
    return ".".join(reversed(parts))


def _call_of(node: ast.AST) -> ast.Call | None:
    if isinstance(node, ast.Await):
        node = node.value
    return node if isinstance(node, ast.Call) else None


def scan(path: pathlib.Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    rel = str(path.relative_to(ROOT)).replace("\\", "/")

    checked: set[str] = set()
    discarded: list[tuple[str, int]] = []

    #: Functions that hand a hard-coded success to whatever renders the answer. `saved=True`,
    #: `ok=True`, `"ok": True` — the claim, written as a constant rather than read from the act.
    claims: set[str] = set()
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for sub in ast.walk(fn):
            if isinstance(sub, ast.keyword) and sub.arg in ("saved", "ok", "success", "done")                     and isinstance(sub.value, ast.Constant) and sub.value.value is True:
                claims.add(fn.name)
            if isinstance(sub, ast.Dict):
                for k, v in zip(sub.keys, sub.values):
                    if isinstance(k, ast.Constant) and k.value in ("ok", "saved", "success")                             and isinstance(v, ast.Constant) and v.value is True:
                        claims.add(fn.name)

    #: Which function each line belongs to, so a discarded call can be tied to the claim above it.
    owner: dict[int, str] = {}
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for sub in ast.walk(fn):
                if hasattr(sub, "lineno"):
                    owner.setdefault(sub.lineno, fn.name)

    def _consume(node: ast.AST | None) -> None:
        """The answer is genuinely used: assigned, returned, or the thing a branch turns on."""
        if node is None:
            return
        for sub in ast.walk(node):
            call = _call_of(sub)
            if call is not None and getattr(call.func, "attr", ""):
                name = _name(call.func)
                if name.count(".") >= 1:
                    checked.add(name)

    for node in ast.walk(tree):
        # THE VALUE, NOT THE NEIGHBOURHOOD. Walking a whole `if` counted every call in its BODY as
        # «checked» — so `await auditor.record(...)` written inside one branch made every other
        # audit write in the file look like a forgotten check. Eight of the nine findings were that
        # mistake, and a gate that is mostly wrong is one nobody reads.
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            _consume(node.value)
        elif isinstance(node, ast.Return):
            _consume(node.value)
        elif isinstance(node, ast.If):
            _consume(node.test)
        elif isinstance(node, ast.Compare):
            _consume(node)
        # A bare expression statement: the answer goes nowhere.
        if isinstance(node, ast.Expr):
            call = _call_of(node.value)
            if call is None:
                continue
            name = _name(call.func)
            if name.count(".") >= 1:
                discarded.append((name, node.lineno))

    return [f"{rel}:{line}  `{name}` is checked elsewhere in this file, thrown away here, and "
            f"`{owner.get(line, '?')}()` then reports success anyway — the person is told it "
            f"worked by a line that never asked"
            for name, line in discarded
            if name in checked and owner.get(line, "") in claims]


def main() -> int:
    findings: list[str] = []
    files = 0
    for path in sorted(SERVICES.glob("*/app/**/*.py")):
        files += 1
        findings += scan(path)

    if findings:
        print(f"{C_R}  ✘ {len(findings)} call(s) whose answer this file cares about elsewhere:"
              f"{C_N}")
        for line in findings:
            print(f"{C_R}      {line}{C_N}")
        print(f"{C_R}    Read it here too, or say plainly why this path may not. A confirmation "
              f"nobody verified is worse than an error: he stops trying.{C_N}")
        return 1

    print(f"{C_G}  ✔ no peer answer is checked in one place and ignored in another ({files} "
          f"modules){C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
