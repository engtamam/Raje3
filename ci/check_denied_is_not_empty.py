"""A permission answer must not be served as an empty list.

WHY THIS EXISTS (م · النمط 2 — eleven places). The console draws each screen from an action
catalogue, and where an action was missing the screens wrote:

    if (!canList) { setRows([]); return; }

So «this is not yours to see» arrived at the render as «there is nothing here», and the emptiness
sentence written for a genuinely empty shop was said to somebody whose role simply excludes the
section. What the owner reads:

  · «لا يوجد عملاء بعد» — to a shop with three thousand customers.
  · «لا أحد متأخر» — a CONGRATULATION, at the exact moment somebody should be chasing people.
  · «تعذّر قراءة رسائلك · حسابك سليم. حاول بعد قليل» — whose only path is a missing capability, so
    he retries every day on something that waiting will never open.
  · «لا يوجد موظفون بعد — أضف موظفيك» — with the add button hidden, for the same missing action.

Every one of these is a true sentence about the wrong thing, which is worse than an error: he acts
on it.

WHAT IT CHECKS. A `set*([])` inside a guard that tests a variable which this file also obtained
from the action catalogue. That is the collapse itself: a capability decided the value, and the
value it decided is indistinguishable from a fact about the shop.

The fix is the fourth state — `DENIED` (apps/console/src/loading.ts) — so the screen can say «لا
يشمل دورك هذا القسم» and mean it.

    python ci/check_denied_is_not_empty.py
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "apps" / "console" / "src"
C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"

#: `const canList = action(catalog, 'billing.invoices')` — the names a capability decides.
FROM_CATALOGUE = re.compile(r"(?:const|let)\s+(\w+)\s*=\s*action\s*\(")

#: `if (!canList) { setRows([]); return; }`, and the multi-guard spellings beside it.
GUARD = re.compile(r"if\s*\(([^)]*)\)\s*\{[^}]*?\bset(\w+)\(\s*\[\s*\]\s*\)")


def scan(path: pathlib.Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    rel = str(path.relative_to(ROOT)).replace("\\", "/")
    decided = set(FROM_CATALOGUE.findall(text))
    if not decided:
        return []

    out: list[str] = []
    for m in GUARD.finditer(text):
        test = m.group(1)
        named = {n for n in decided if re.search(rf"!\s*{re.escape(n)}\b", test)}
        if not named:
            continue
        line = text[:m.start()].count("\n") + 1
        out.append(f"{rel}:{line}  a missing capability ({', '.join(sorted(named))}) becomes an "
                   f"EMPTY list — «not yours to see» is then rendered as «there is nothing here»")
    return out


def main() -> int:
    findings: list[str] = []
    files = 0
    for path in sorted(SRC.rglob("*.tsx")):
        files += 1
        findings += scan(path)

    if findings:
        print(f"{C_R}  ✘ {len(findings)} place(s) where a permission answer is served as "
              f"emptiness:{C_N}")
        for line in findings:
            print(f"{C_R}      {line}{C_N}")
        print(f"{C_R}    Use DENIED (src/loading.ts). «لا يشمل دورك هذا القسم» is a different "
              f"sentence from «لا يوجد شيء بعد», and he acts on the wrong one.{C_N}")
        return 1

    print(f"{C_G}  ✔ no screen renders a missing capability as an empty list ({files} screens)"
          f"{C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
