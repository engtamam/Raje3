"""An erasure may not fan out over a map nobody re-read (و-3).

WHAT THE FAN-OUT DEPENDS ON. compliance erases exactly the data targets it holds for a tenant. That
map is written once, at signup. The owner's own role carries `compliance.manage` — it has to,
because the erasure button travels on HIS token so the act is his and we cannot erase a customer of
a shop that did not ask — and the same capability also grants DELETE on those targets.

So a shop can narrow its own map, by accident or otherwise. Every erasure afterwards fans out to
what is left, every one of those targets acknowledges, and the request closes COMPLETED. The
customer is told his data is gone while a whole service still holds it, and NOTHING FAILS anywhere:
no error, no log line, no unacknowledged target. It is the quietest way this product can break a
promise it made on a legal deadline.

`reassert_data_map` closes it — the registration is idempotent, so re-asserting costs one round
trip and restores whatever was removed. This gate is what keeps the two together: the day somebody
adds a second way to start an erasure, they will find the map is not optional.

WHY A GATE. The defect is a MISSING call before an existing one — invisible to any test of what the
erasure returns, because the erasure returns exactly what it should. Only the shape catches it.

No exceptions table: an erasure that skips the map is one we cannot stand behind, whatever the
reason for skipping it.
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
FANS_OUT = "erase_subject"
REASSERTS = "reassert_data_map"


def _names_called(node: ast.AST) -> set[str]:
    out = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            f = sub.func
            if isinstance(f, ast.Attribute):
                out.add(f.attr)
            elif isinstance(f, ast.Name):
                out.add(f.id)
        # `run_in_threadpool(E.erase_subject, ...)` hands the function over rather than calling it.
        elif isinstance(sub, ast.Attribute):
            out.add(sub.attr)
        elif isinstance(sub, ast.Name):
            out.add(sub.id)
    return out


def main() -> int:
    bad = []
    api = ROOT / "services" / "operations" / "app" / "api"
    for path in sorted(api.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            bad.append(f"{path.relative_to(ROOT).as_posix()} · unreadable: {exc}")
            continue
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            names = _names_called(fn)
            if FANS_OUT in names and REASSERTS not in names:
                bad.append(f"{path.relative_to(ROOT).as_posix()}:{fn.lineno} · {fn.name}")

    if bad:
        print("An erasure fans out without re-asserting the shop's data map:")
        for line in bad:
            print("  " + line)
        print("\nThe owner can DELETE a data target — the same capability that lets him start the")
        print("erasure at all — and a narrowed map closes the request COMPLETED over less than")
        print("everything, silently. Call `signup.reassert_data_map(tenant)` first and refuse on a")
        print("non-empty answer.")
        return 1
    print("every erasure re-asserts the map first")
    return 0


if __name__ == "__main__":
    sys.exit(main())
