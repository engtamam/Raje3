"""A PERSON MUST NEVER READ A ROUTE AND A STATUS CODE.

THE DEFECT THIS WAS WRITTEN FOR. The redemption on the visit screen caught a failure and rendered
`e.message` under a comment that read «THE SENTENCE THE SERVICE WROTE». It was not: `api.ts` throws
an `ApiError` whose message is built for a log — `POST /api/v1/loyalty/redeem → 400`. A cashier,
with the customer standing in front of him, read a route and a number. Loyalty had been changed to
RETURN its refusals rather than raise them precisely so he would read «رصيد العميل لا يكفي», and
the console threw that sentence away at the last step.

WHAT MAKES THIS HARD TO SEE BY EYE, and why the first count of it was wrong: thirty-seven call
sites share the shape `e instanceof Error ? e.message : '<arabic>'`, and thirty-six of them are
CORRECT — `catalog.call` and `auth.post` both dig the service's sentence out of the response body
and put it in `.message` before throwing. The shape is identical; only the thrower differs. So the
gate cannot match on the shape. It matches on WHICH ERROR the module in question throws.

THE RULE. A module that constructs an Error whose message is a route/status log line must not have
that message rendered by a screen. Concretely: any file importing from `api.ts` may not put a bare
`.message` from a caught error into the interface — it must go through `sentenceFor`.

WHAT IT CANNOT SEE, stated rather than implied:
  · An error rendered after being passed through a variable or a helper of its own.
  · A screen that renders `String(e)`, which is worse and which nothing does today.
  · The platform's own console, which is not ours.
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "apps" / "console" / "src"

# The thrower whose message is a log line: `${method} ${path} → ${status}`.
LOG_SHAPED = "api"

RENDERS_RAW = re.compile(r"(\w+) instanceof Error \? \1\.message")


def main() -> int:
    if not SRC.is_dir():
        print("  x apps/console/src is missing — this gate cannot answer, which is not a pass")
        return 1

    problems: list[str] = []
    for path in sorted(SRC.rglob("*.ts*")):
        if path.name.endswith(".test.ts") or path.name == "api.ts":
            continue
        src = path.read_text(encoding="utf-8")
        # Does this file take its calls from the module that throws the log-shaped error?
        if not re.search(rf"from '(\.\./|\./){LOG_SHAPED}'", src):
            continue
        for m in RENDERS_RAW.finditer(src):
            line = src[:m.start()].count("\n") + 1
            problems.append(
                f"{path.relative_to(ROOT)}:{line} renders `{m.group(1)}.message` from a module "
                f"that throws ApiError — its message is a LOG line (`POST /api/... → 400`), and "
                f"the person reading the screen cannot act on a route or a number. "
                f"Use sentenceFor(e, '<the act that failed, in Arabic>').")

    for line in problems:
        print(f"  x {line}")
    if problems:
        print(f"  x {len(problems)} screen(s) showing a person a log line")
        return 1

    print("  + no screen renders a log line to a person — every refusal arrives as a sentence")
    return 0


if __name__ == "__main__":
    sys.exit(main())
