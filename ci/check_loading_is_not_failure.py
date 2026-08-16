"""«Not yet» and «it failed» must not be the same value on a screen.

WHY THIS EXISTS (م · النمط 1 — fourteen places). A screen holds `useState<Rows | null>(null)`,
renders a skeleton while the value is `null`, and its failure handler is `.catch(() => setRows(null))`.
So a read that fails puts the state back exactly where it started, the skeleton renders for ever,
and the Arabic sentence somebody wrote for the failure is unreachable code.

WHAT THE OWNER SEES. «نقرأ نقاطك وجوائزك» that never resolves. A payments screen — the one that
sells — as two grey rectangles. «نوع النشاط» on the FIRST screen of the product as a permanent
skeleton with a dead «ابدأ» button. Nobody is told anything, so nobody retries, and support hears
«التطبيق ما يفتح».

THE FIX IS ONE LINE PER SITE: `undefined` means «still loading», `null` means «this failed». Then
the skeleton is bound to `undefined` and the sentence that was already written finally renders.
`Messages.tsx` has the correct shape (`logFailed`, `campaignsFailed`) and always did.

WHAT IT CHECKS. A state initialised to `null` whose setter is called with `null` from inside a
`catch`. That is the collapse itself, and it is exact: the initial value and the failure value are
the same token, in the same file, for the same setter.

    python ci/check_loading_is_not_failure.py
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "apps" / "console" / "src"
C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"

#: `const [rows, setRows] = useState<Invoice[] | null>(null)`
INIT = re.compile(r"const\s*\[\s*(\w+)\s*,\s*(set\w+)\s*\]\s*=\s*useState<[^>]*\|\s*null\s*>\(\s*null\s*\)")

#: `setRows(null)` — anywhere; the catch test is applied to the surrounding text.
SET_NULL = re.compile(r"\b(set\w+)\(\s*null\s*\)")


def failures_in_catch(text: str) -> set[str]:
    """Setters called with `null` from inside a catch handler.

    Scanned over the whole `.catch(...)` expression rather than a single line, because the handler
    is written both ways in this app: `.catch(() => setX(null))` and the guarded
    `.catch(() => { if (!stale) setX(null); })`.
    """
    out: set[str] = set()
    for match in re.finditer(r"\.catch\(", text):
        start = match.end()
        depth = 1
        i = start
        while i < len(text) and depth:
            if text[i] == "(":
                depth += 1
            elif text[i] == ")":
                depth -= 1
            i += 1
        out |= {m.group(1) for m in SET_NULL.finditer(text[start:i])}
    return out


def scan(path: pathlib.Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    rel = str(path.relative_to(ROOT)).replace("\\", "/")
    failed = failures_in_catch(text)
    out: list[str] = []
    for m in INIT.finditer(text):
        value, setter = m.group(1), m.group(2)
        if setter not in failed:
            continue
        line = text[:m.start()].count("\n") + 1
        out.append(f"{rel}:{line}  `{value}` starts null and its failure handler sets null — "
                   f"a failed read is indistinguishable from one that has not arrived")
    return out


def main() -> int:
    findings: list[str] = []
    files = 0
    for path in sorted(SRC.rglob("*.tsx")):
        files += 1
        findings += scan(path)

    if findings:
        print(f"{C_R}  ✘ {len(findings)} state(s) where «loading» and «failed» are the same "
              f"value:{C_N}")
        for line in findings:
            print(f"{C_R}      {line}{C_N}")
        print(f"{C_R}    `undefined` is «not yet», `null` is «this failed» — and the sentence "
              f"written for the failure is dead code until they are told apart.{C_N}")
        return 1

    print(f"{C_G}  ✔ every screen tells «not yet» apart from «it failed» ({files} screens){C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
