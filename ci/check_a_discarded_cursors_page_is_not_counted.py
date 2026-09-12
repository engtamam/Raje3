"""A page whose cursor was thrown away must never be counted as if it were the whole set.

WHY THIS EXISTS. `ci/check_a_read_that_meant_everything_admits_it_stopped.py` already refuses a
`find(..., limit=N)` whose cursor is silently dropped ONCE `N` reaches four figures — the reasoning
there is that a small `limit` reads as an ordinary screen-sized page, and the caller genuinely does
not care what comes after. A second QA pass found that reasoning has a real blind spot: several
places take exactly that kind of "just a page" read and then compute `len(rows)`, presenting the
result as a COUNT or TOTAL — a claim about the whole set, made from a fragment of it, regardless of
how small the configured limit was.

FOUND, TWICE, IN THE SAME FILE. `campaigns/app/api/v1/campaigns.py`'s `list_campaigns` returns
`{"campaigns": rows, "count": len(rows)}` from `rows, _ = await store.find(..., limit=200)` — a
shop with 250 campaigns is told it has 200. Its sibling `runs` route did the identical thing for
`campaign_runs` (limit=200, cursor discarded) before this same QA pass fixed the neighbouring
`campaign_reached` read the same day. Neither is anywhere near the 1000-row threshold the sibling
gate polices — the size of the limit was never the signal that mattered here.

WHAT THIS CHECKS. A `.find(...)` call assigned as `rows, _ = ...` (the cursor bound to a literal,
throwaway `_` — an explicit "I am not going to look at this") whose `rows`-side name is later
handed, unmodified, to `len(...)` as the value of a `"count"`/`"total"` key in a dict literal — the
exact shape the response this reaches an owner/operator's screen as a claim about the WHOLE set.
Deliberately unconditional on `limit`'s value: a page is a page regardless of how big you asked
for it, and `len()` of a page labelled "count" is never a count of anything but that page.

WHAT THIS DELIBERATELY DOES NOT FLAG, having over-matched on both once: `len(rows)` used inside a
COMPARISON to compute a `truncated` flag (`"truncated": len(rows) >= capped`) — the honest,
already-correct pattern this gate's own sibling requires, not the defect; and a bounded sweep's own
progress counter (`res.scanned = len(rows)`, a `while` loop's `scanned += len(rows)`) naming what
THIS PASS looked at, never a claim about the whole set. Both are real shapes a first version of
this gate flagged before being narrowed to dict-literal count/total keys specifically.

WHAT THIS CANNOT SEE, said plainly: a `.find()` result whose cursor is bound to a REAL name and
then simply never read (the sibling gate's own "binding is not handling" limitation, inherited
here); and a count/total built through an intermediate variable rather than inline in the dict
literal (`n = len(rows); return {"count": n}`) — a narrower, more literal match was chosen
deliberately over guessing at every possible route from a page to a number.

    python ci/check_a_discarded_cursors_page_is_not_counted.py
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVICES = ROOT / "services"
_EXCLUDED_DIRS = {".venv", "venv", "site-packages", "__pycache__", "node_modules", ".git"}


def _is_excluded(path: pathlib.Path) -> bool:
    return any(part in _EXCLUDED_DIRS for part in path.parts)


def _is_find_call(node: ast.AST) -> bool:
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr in ("find", "scan_all", "list"))


def _rows_name_if_discarded(stmt: ast.stmt) -> str | None:
    """If `stmt` is `<rows_name>, _ = await X.find(...)` (or the sync equivalent) — the cursor
    bound to a literal, throwaway `_` — returns the rows-side name; else None. Only the exact
    two-element-tuple, `_`-as-second-element shape counts: `rows, cursor = ...` (a real name) is a
    different case this gate does not touch."""
    if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
        return None
    target = stmt.targets[0]
    if not (isinstance(target, ast.Tuple) and len(target.elts) == 2):
        return None
    rows_target, cursor_target = target.elts
    if not (isinstance(cursor_target, ast.Name) and cursor_target.id == "_"):
        return None
    if not isinstance(rows_target, ast.Name):
        return None
    value = stmt.value
    if isinstance(value, ast.Await):
        value = value.value
    if not _is_find_call(value):
        return None
    return rows_target.id


_TOTALITY_KEYS = {"count", "total"}


def _len_used_as_count_or_total(fn: ast.AST, name: str, after_lineno: int) -> ast.Call | None:
    """`len(name)` is only a completeness CLAIM when it is handed to the caller labelled as
    "count"/"total" — a dict literal's value for a `"count"`/`"total"` key, exactly the shape
    `list_campaigns` was written with (`{"campaigns": rows, "count": len(rows)}`).

    NOT FLAGGED: `len(name)` used inside a COMPARISON to decide a `truncated` flag (`"truncated":
    len(rows) >= capped`) — that is the honest, already-correct pattern this gate's sibling exists
    to require, not the defect; and a bare progress counter (`res.scanned = len(rows)`) naming
    what a bounded sweep looked at THIS PASS, never a total. Both are real shapes this gate
    over-matched on before being narrowed to dict-literal count/total keys specifically."""
    for node in ast.walk(fn):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values):
            if not (isinstance(key, ast.Constant) and isinstance(key.value, str)
                    and key.value.lower() in _TOTALITY_KEYS):
                continue
            if (isinstance(value, ast.Call) and isinstance(value.func, ast.Name)
                    and value.func.id == "len" and getattr(value, "lineno", 0) >= after_lineno
                    and len(value.args) == 1 and isinstance(value.args[0], ast.Name)
                    and value.args[0].id == name):
                return value
    return None


def main() -> int:
    if not SERVICES.is_dir():
        print("no services/ directory — this gate cannot answer, so it refuses to")
        return 1

    files = sorted(
        f for f in SERVICES.rglob("*.py")
        if not _is_excluded(f) and "test" not in f.parts and not f.name.startswith("test_")
    )

    violations: list[str] = []
    reads_checked = 0

    for f in files:
        try:
            src = f.read_text(encoding="utf-8")
            tree = ast.parse(src, filename=str(f))
        except (SyntaxError, UnicodeDecodeError):
            continue

        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for node in ast.walk(fn):
                if node is fn or not isinstance(node, ast.Assign):
                    continue
                rows_name = _rows_name_if_discarded(node)
                if rows_name is None:
                    continue
                reads_checked += 1
                len_call = _len_used_as_count_or_total(fn, rows_name, node.lineno)
                if len_call is not None:
                    violations.append(
                        f"{f.relative_to(ROOT)}:{node.lineno}: `{rows_name}, _ = ...find(...)` "
                        f"discards its cursor, but line {len_call.lineno} calls "
                        f"`len({rows_name})` anyway — that is the size of ONE PAGE, presented as "
                        f"if it were the whole set")

    if violations:
        print(f"  ✘ {len(violations)} discarded-cursor page(s) counted as a total (of "
              f"{reads_checked} discarded-cursor reads checked):")
        for v in violations:
            print(f"      {v}")
        return 1

    print(f"  ✔ none of the {reads_checked} discarded-cursor page read(s) is counted as a total")
    return 0


if __name__ == "__main__":
    sys.exit(main())
