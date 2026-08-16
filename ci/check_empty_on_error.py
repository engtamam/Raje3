"""A failed read rendered as an empty one — the lie a screen tells with a straight face.

WHY THIS EXISTS. `Customers.tsx` fetched the customer list and, on any failure, set the list to
`[]`. The screen then rendered «لا يوجد عملاء بعد» to a shop with three thousand customers. The
same shape told a paying shop «لا يوجد اشتراك فعّال», an owner «لا شيء في السجل بعد», and — worst
of the four — congratulated him with «لا أحد متأخر» when the schedule read had failed. That last
one is not merely wrong: it is reassuring, so he stops chasing exactly when he should start.

THE RULE THIS ENFORCES is the product's three-state rule, applied to a screen: a read is either
READ, or UNAVAILABLE WITH A REASON, or genuinely empty. Collapsing the middle state into the third
is how a defect becomes a compliment.

WHAT IT LOOKS FOR, and it is deliberately narrow: a `.catch(...)` whose handler sets state to an
empty array, an empty string, or zero. That shape is always this defect — the caller cannot tell
the difference afterwards, and neither can the person reading the screen.

WHAT IS FINE and is not flagged: `.catch(() => setX(null))` — null is the unavailable state this
codebase already uses — and a catch that sets an error message, or re-throws, or does nothing.

    python ci/check_empty_on_error.py
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONSOLE = ROOT / "apps" / "console" / "src"
C_G, C_R, C_Y, C_N = "\033[32m", "\033[31m", "\033[33m", "\033[0m"

# `.catch(() => setThing([]))` and its close relatives, including the `if (!stale)` guard this
# codebase uses on debounced reads.
EMPTY = r"(\[\s*\]|''|\"\"|``|0)"
PATTERNS = [
    re.compile(r"\.catch\(\s*\(\s*\)\s*=>\s*\{?[^)}]*?set[A-Za-z0-9_]+\(\s*" + EMPTY + r"\s*\)"),
    re.compile(r"\.catch\(\s*\(\s*\)\s*=>\s*\{[^}]*?if\s*\(![A-Za-z0-9_]+\)\s*"
               r"set[A-Za-z0-9_]+\(\s*" + EMPTY + r"\s*\)"),
]

# A screen may legitimately fall back to empty when the ACTION IS ABSENT — that is «this account
# may not», not «we could not read». Those are guarded by `if (!a)` rather than by a catch, and the
# patterns above do not match them.


def main() -> int:
    if not CONSOLE.exists():
        print(f"{C_R}  ✘ {CONSOLE} does not exist{C_N}")
        return 1

    found: list[str] = []
    scanned = 0
    for path in sorted(CONSOLE.rglob("*.tsx")) + sorted(CONSOLE.rglob("*.ts")):
        text = path.read_text(encoding="utf-8")
        scanned += 1
        for pattern in PATTERNS:
            for m in pattern.finditer(text):
                line = text.count("\n", 0, m.start()) + 1
                rel = str(path.relative_to(ROOT)).replace("\\", "/")
                found.append(f"{rel}:{line}  {m.group(0).strip()[:90]}")

    if found:
        print(f"{C_R}  ✘ {len(found)} read(s) that render a FAILURE as «nothing»:{C_N}")
        for line in sorted(set(found)):
            print(f"{C_R}      {line}{C_N}")
        print(f"{C_R}    Set the state to null on failure and render «تعذّرت القراءة» — a shop "
              f"told «لا يوجد» about data it has stops trusting the screen, and a shop told "
              f"«لا أحد متأخر» stops chasing.{C_N}")
        return 1

    print(f"{C_G}  ✔ no screen renders a failed read as an empty one ({scanned} files){C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
