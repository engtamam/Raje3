"""No peer's success may be read from a field that might not be there.

THE SHAPE. `bool(result.get("ok", True))` — ask another service whether it did the thing, and when
it does not say, assume it did. Every one of these is a silent success: the peer refuses, or answers
a shape we did not expect, or half-answers, and the caller reports the act as done.

WHERE IT WAS FOUND (د-3). `erase_customer.py` read compliance's `/process` reply exactly that way.
compliance answers HTTP 200 with `{"ok": false, "reason": ...}` for every refusal except NOT_FOUND —
a legal hold, an unverified request, a target that would not take it — so a refusal arrived as 200,
`ok` was read with a default of True, and the route above it returned `{"ok": True, ...}`. The owner
pressed «احذف بياناته», compliance declined, and the screen said it was done. On a PDPL deadline.

WHY A DEFAULT IS THE WHOLE DEFECT. `.get(key)` returning None is honest — the caller has to decide
what None means. `.get(key, True)` decides for it, in the direction that never raises an alarm. The
same line with `False` would fail closed and be visible in a day.

WHAT THIS DOES NOT FLAG, and why it needs no exception table:
  · `.get("ok")` with no default — that is a read, and the caller still has to handle None.
  · `.get("ok", False)` — failing closed is the answer this check exists to produce.
  · Anything not named like an outcome. The names below are the ones that mean «did it work»;
    a default on `.get("limit", 100)` is a configuration choice, not a verdict.

    python ci/check_absent_means_ok.py
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"

#: Field names that carry a VERDICT from somewhere else. A truthy default on any of them converts
#: «it did not say» into «it worked».
OUTCOME = ("ok", "success", "succeeded", "delivered", "sent", "accepted", "applied", "recorded",
           "dispatched", "completed", "done", "valid", "allowed", "granted", "erased", "saved")

#: READ AS CODE, NOT AS TEXT. The first version matched source lines with a regex and reported its
#: own explanatory comments — a guard that cries on prose is one whose findings get skimmed. Walking
#: the syntax tree means a mention in a comment, a docstring or a string literal is invisible to it,
#: and only a real call is a finding.


def sources() -> list[pathlib.Path]:
    out: list[pathlib.Path] = []
    for base in (ROOT / "services", ROOT / "deploy", ROOT / "ci"):
        if not base.is_dir():
            continue
        for p in base.rglob("*.py"):
            parts = set(p.parts)
            # Tests may assert on the shape; a vendored dependency is not ours to hold.
            if ".venv" in parts or "tests" in parts or "__pycache__" in parts:
                continue
            # THIS FILE NAMES THE SHAPE IT HUNTS, in its own note and its own pattern. A guard that
            # reports itself teaches whoever runs it that one finding is always noise — and the day
            # a second appears beside it, nobody looks.
            if p.name == pathlib.Path(__file__).name:
                continue
            out.append(p)
    return out


def main() -> int:
    findings: list[str] = []
    for path in sources():
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                continue
            if node.func.attr != "get" or len(node.args) != 2:
                continue
            field, default = node.args
            if not (isinstance(field, ast.Constant) and field.value in OUTCOME):
                continue
            if not (isinstance(default, ast.Constant) and default.value is not None
                    and default.value is not False and bool(default.value)):
                continue
            rel = path.relative_to(ROOT).as_posix()
            findings.append(
                f"{rel}:{node.lineno}  .get(\"{field.value}\", {default.value!r}) — a peer that "
                f"did not answer is being read as one that succeeded")

    if findings:
        print(f"{C_R}  ✘ {len(findings)} place(s) read an ABSENT outcome as a successful one:{C_N}")
        for f in findings:
            print(f"{C_R}      {f}{C_N}")
        print(f"{C_R}    Drop the default and decide what the silence means. Failing closed costs a "
              f"retry; failing open tells a person something happened that did not.{C_N}")
        return 1

    print(f"{C_G}  ✔ no outcome is defaulted to success — every peer's silence is handled{C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
