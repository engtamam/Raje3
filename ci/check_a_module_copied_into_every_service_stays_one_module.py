"""A module copied into several services must have the SAME CODE in all of them.

WHAT IS COPIED, AND WHY IT HAS TO BE. `app/core/pii.py` computes the pseudonym every service writes
into its immutable records — `HMAC-SHA256(PII_SALT, "<tenant>|<subject>")`. `app/core/secret_store.py`
seals operator credentials under `v1:gcm:`. These are not six implementations of an idea; they are
one implementation pasted six times, because these services are separate deployables and this
repository has no shared package to put it in.

WHAT DRIFT COSTS, AND IT IS NOT A CRASH. If one service's `pii.py` ever computes a different
pseudonym for the same person, nothing fails: each service is internally consistent and every test
passes. What changes is that the same customer becomes TWO PEOPLE across the fleet — and the first
place it surfaces is an erasure, where compliance fans the request out by pseudonym, the odd
service matches no row, answers `already_absent`, and the person is told their data is gone while
it sits untouched. That exact defect has been paid for once here already (د-2). A sealing prefix
that drifts is the same shape: secrets written by yesterday's copy stop opening.

THE COPIES SAY SO THEMSELVES, WHICH IS WHY THIS GATE NEEDS NO LIST. Each carries a marker line, and
this gate groups files by that marker rather than by a set of filenames written here. Two rules
follow, and the second is the one that matters:

  * Every marked file of the same name must have identical CODE.
  * If ANY service marks a file, EVERY service holding a file of that name must mark it too.

Without the second rule the marker would be an opt-out: delete your line and drift freely. With it,
leaving the group is a visible edit that fails CI rather than a quiet one nobody reads.

PROSE MAY DIFFER, CODE MAY NOT. Comparison is over the parsed syntax with docstrings stripped, so
each service can explain the copy in its own words — `operations` already does, at length, because
it is the service that held the real phone number when د-2 happened. Forcing six files to be
byte-identical would delete that, and would make this gate about formatting instead of behaviour.
`app/core/backup.py` is deliberately NOT in the group: its table lists genuinely differ per service,
so it carries no marker and is not compared.
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVICES = ROOT / "services"

#: The line a copy carries to say it is one. Written in the file it governs, not in a list here.
MARKER = "SHARED COPY"


def _code(text: str) -> str:
    """The module's syntax with every docstring removed, so prose is free and logic is not."""
    tree = ast.parse(text)
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if (isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                and body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            body.pop(0)
    return ast.dump(tree)


def main() -> int:
    if not SERVICES.is_dir():
        print("no services/ directory — this gate cannot answer, so it refuses to")
        return 1

    marked: dict[str, list[pathlib.Path]] = {}      # basename -> the copies that declare themselves
    present: dict[str, list[pathlib.Path]] = {}     # basename -> every file by that name
    for path in sorted(SERVICES.glob("*/app/core/*.py")):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"cannot read {path.relative_to(ROOT).as_posix()}: {exc} — so it was NOT checked")
            return 1
        present.setdefault(path.name, []).append(path)
        if MARKER in text:
            marked.setdefault(path.name, []).append(path)

    if not marked:
        # SILENCE IS NOT AGREEMENT. The markers are the gate's whole input; none found means they
        # were removed or renamed, not that nothing is copied any more.
        print(f"no module under services/*/app/core/ carries the «{MARKER}» marker — either the "
              f"copies stopped declaring themselves or this gate needs re-pointing. It will not "
              f"assume the second.")
        return 1

    escaped: list[str] = []
    diverged: list[str] = []
    for name, copies in sorted(marked.items()):
        # THE OPT-OUT, CLOSED. A sibling of the same name that dropped its marker is the exact edit
        # this gate exists to make visible.
        for path in present.get(name, []):
            if path not in copies:
                escaped.append(f"{path.relative_to(ROOT).as_posix()} — a sibling of a marked "
                               f"module, with no marker of its own")

        if len(copies) < 2:
            continue

        shapes: dict[str, list[str]] = {}
        for path in copies:
            try:
                shape = _code(path.read_text(encoding="utf-8"))
            except SyntaxError as exc:
                print(f"cannot parse {path.relative_to(ROOT).as_posix()}: {exc} — so it was NOT "
                      f"compared")
                return 1
            shapes.setdefault(shape, []).append(path.relative_to(ROOT).as_posix())
        if len(shapes) > 1:
            groups = " | vs | ".join(", ".join(sorted(g)) for g in shapes.values())
            diverged.append(f"{name}: {len(shapes)} different implementations — {groups}")

    if escaped or diverged:
        print(f"{len(escaped) + len(diverged)} problem(s) with modules copied across services:")
        for line in diverged + escaped:
            print("  " + line)
        print("\nThese carry no separate identity: one of them computes the pseudonym every other")
        print("service stores. When they disagree nothing crashes — the same customer simply")
        print("becomes two people, and the first place it shows is an erasure that reports success")
        print("over data it never found.")
        return 1

    n = sum(len(c) for c in marked.values())
    print(f"{n} copied module(s) in {len(marked)} group(s): every copy has the same code")
    return 0


if __name__ == "__main__":
    sys.exit(main())
