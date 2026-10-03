"""A row created from a peer's identity is keyed by that identity, not by a fresh id (ز-10).

WHAT HAPPENED. `hire_member` asks identity to create a membership — keyed by phone, idempotent, so
asking twice is one membership — and then wrote its own operator row with `new_id("opr")`. New on
every call. A double press, or a retry on a slow reply, produced ONE person and TWO rows: two seats
billed on a per-seat plan, the same name twice on the team screen with nothing to tell them apart,
and whichever row a lookup reached first winning.

Nothing failed. 201, a valid row, a screen that refreshed — the second press looked exactly like
the first one working.

WHAT THIS CHECKS. In a handler that receives an identifier back from a peer, a locally minted id
must not be the key of the row that identifier belongs to: the row is looked up by the peer's
identifier first, and only minted when there is nothing to reuse. The rule is written as «the
minting is CONDITIONAL» because that is the shape the correct code has and the broken code cannot
have.

NO EXCEPTIONS TABLE. A handler that genuinely needs a fresh row per call for a person a peer
already identified is describing a defect; if one ever exists, it argues its case by editing this
file.
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVICES = ROOT / "services"
# The identifiers a peer hands back, which are the natural keys of the rows built from them.
PEER_KEYS = ("person_id", "subject_ref")
MINT = "new_id"


class _Visitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.mints_unconditionally: list[tuple[str, int]] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:      # noqa: N802
        self._check(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:   # noqa: N802
        self._check(node)
        self.generic_visit(node)

    def _check(self, node) -> None:
        names = {n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute)} | {
            n.id for n in ast.walk(node) if isinstance(n, ast.Name)} | {
            k.arg for k in ast.walk(node) if isinstance(k, ast.keyword) and k.arg}
        strings = {s.value for s in ast.walk(node)
                   if isinstance(s, ast.Constant) and isinstance(s.value, str)}
        if not (set(PEER_KEYS) & (names | strings)):
            return
        for call in ast.walk(node):
            if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                    and call.func.id == MINT):
                continue
            # CONDITIONAL IS THE WHOLE TEST. `new_id(...)` inside an IfExp — «reuse what is there,
            # mint only when there is nothing» — is the fix; a bare call is the defect.
            if not any(isinstance(p, ast.IfExp) for p in _parents(node, call)):
                self.mints_unconditionally.append((node.name, call.lineno))


def _parents(root: ast.AST, target: ast.AST) -> list[ast.AST]:
    """Every node on the path from `root` down to `target`."""
    path: list[ast.AST] = []

    def walk(node: ast.AST, trail: list[ast.AST]) -> bool:
        if node is target:
            path.extend(trail)
            return True
        for child in ast.iter_child_nodes(node):
            if walk(child, [*trail, node]):
                return True
        return False

    walk(root, [])
    return path


def main() -> int:
    bad = []
    files = sorted(SERVICES.rglob("app/api/**/*.py"))
    if not files:
        # SILENCE IS NOT AGREEMENT. An empty sweep means the tree moved, not that all is well.
        print("no handlers found under services/*/app/api — this gate needs re-pointing")
        return 1

    for path in files:
        if "__pycache__" in path.parts or "tests" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError) as exc:
            print(f"cannot read {path.relative_to(ROOT).as_posix()}: {exc}")
            return 1
        visitor = _Visitor()
        visitor.visit(tree)
        for name, line in visitor.mints_unconditionally:
            bad.append(f"{path.relative_to(ROOT).as_posix()}:{line} · {name}()")

    if bad:
        print("These mint a fresh id for a person a peer already identified:")
        for line in bad:
            print("  " + line)
        print("\nPressing the button twice then makes two rows for one human — two seats billed,")
        print("one name listed twice, and whichever row a lookup reaches first wins.")
        print(f"Look the row up by its {' / '.join(PEER_KEYS)} and mint only when there is none.")
        return 1
    print(f"{len(files)} handler file(s): every row built from a peer's identity is keyed by it")
    return 0


if __name__ == "__main__":
    sys.exit(main())
