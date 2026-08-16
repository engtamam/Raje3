"""A paged read of a time-ascending feed must not stop on a size cap and call the result the answer.

WHY THIS EXISTS (ي-1). insights builds every dashboard from `peers.visits(tenant, since=0)`. That
feed is paged by `created` ASCENDING — operations sorts it that way so the watermark can advance
safely — and the reader stopped as soon as it held 5000 rows, then returned `out[:limit]`. So the
snapshot of a busy shop was computed from its FIRST five thousand visits: the oldest ones, some of
them years old.

Nothing failed. `active_customers` counts a 90-day window and answered 0. `expected_flow` answered
0. `at_risk` listed people who had stopped coming two years ago. The shops this hurt are the busy
ones — the ones that pay — and the dashboard they were shown said their business was dead while
the till was ringing. The `exhaustive` and `more` flags the peer returns were read only to decide
whether to keep paging; nothing ever marked the snapshot as partial.

WHAT IT CHECKS. In an adapter that pages a peer feed — a function that reads a `watermark` or a
`more` flag from the answer — a `break` may not be conditioned on how many rows have been
COLLECTED. Stopping on the page budget is fine and necessary; stopping on the size cap is the
defect, because it always stops at the oldest end.

WHAT IT CANNOT SEE, said plainly: a truncation that happens in the peer itself. That is the peer's
contract to state, and `exhaustive` is where it states it.

    python ci/check_paging_keeps_the_recent.py
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVICES = ROOT / "services"
C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"

#: How a paged peer read announces itself: it advances on what the OTHER side reports.
PAGING_MARKS = ("watermark", '"more"', "'more'", "exhaustive")

#: The accumulator names a paging loop uses. A comparison between one of these and a limit is the
#: size cap; a comparison between a page counter and a budget is not.
COLLECTED = ("out", "rows", "acc", "collected", "items", "results")


def _is_size_cap(node: ast.AST) -> bool:
    """`len(out) >= limit` and its spellings — a stop decided by how much was gathered."""
    for cmp_node in ast.walk(node):
        if not isinstance(cmp_node, ast.Compare):
            continue
        left = cmp_node.left
        if not (isinstance(left, ast.Call) and isinstance(left.func, ast.Name)
                and left.func.id == "len" and left.args):
            continue
        target = left.args[0]
        name = target.id if isinstance(target, ast.Name) else ""
        if name not in COLLECTED:
            continue
        for other in cmp_node.comparators:
            if isinstance(other, ast.Name) and "limit" in other.id.lower():
                return True
            if isinstance(other, ast.Attribute) and "limit" in other.attr.lower():
                return True
    return False


def scan(path: pathlib.Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    rel = str(path.relative_to(ROOT)).replace("\\", "/")
    out: list[str] = []

    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        src = ast.get_source_segment(text, fn) or ""
        if not any(mark in src for mark in PAGING_MARKS):
            continue
        for node in ast.walk(fn):
            if not isinstance(node, ast.If):
                continue
            if not any(isinstance(b, ast.Break) for b in node.body):
                continue
            if _is_size_cap(node.test):
                out.append(f"{rel}:{node.lineno}  {fn.name}() stops paging once it holds `limit` "
                           f"rows — on an ascending feed that keeps the OLDEST and drops today")
    return out


def main() -> int:
    findings: list[str] = []
    scanned = 0
    for path in sorted(SERVICES.glob("*/app/adapters/**/*.py")):
        scanned += 1
        findings += scan(path)

    if findings:
        print(f"{C_R}  ✘ {len(findings)} paged read(s) that stop at the oldest end:{C_N}")
        for line in findings:
            print(f"{C_R}      {line}{C_N}")
        print(f"{C_R}    Page to the end and keep the newest rows, and say so when the cap "
              f"bit — a window computed over the wrong end reads as a dead business.{C_N}")
        return 1

    print(f"{C_G}  ✔ every paged peer read keeps the recent end ({scanned} adapters){C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
