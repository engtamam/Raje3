#!/usr/bin/env python3
"""ONE SUBSCRIBE FLOW, NOT ONE PER APP.

`apps/console/src/subscribeFlow.ts::useSubscribeFlow` is the single place that mints a payment
token, opens the 3DS redirect, and posts the purchase — `subscription.activate` (our own path,
enforcing WhatsApp-before-paid) or its `billing.subscribe` fallback. Any second screen that calls
either action ID directly is rebuilding that sequence from scratch: `Plans.tsx` had already earned
every rule in it the hard way (see its own header note — د-15's gateway/token-mint check, the
`pendingPayment` round trip across a full-page 3DS redirect) before this hook lifted that half of
it out for `Locked.tsx`'s inline buy button to reuse. A third copy is how the two quietly drift —
one honours `plan.requires_any`'s ordering and the other forgets it.

So this gate is narrow on purpose: a real STRING LITERAL of either action id may appear only in
the two files that are allowed to call it. Everywhere else — including a brand-new app's own
locked card or route — reads a plan through `useSubscribeFlow` instead, same as `Locked.tsx`.

A comment or docstring MENTIONING the action id in prose (explaining the rule, not calling it) is
fine and stays unflagged — this scans only for the action id inside a quoted string literal used
as a call argument shape (`'subscription.activate'` / `"billing.subscribe"`), not bare prose text,
which is already indistinguishable from a real call by a simple string search; so this checks
each matching line for a nearby call-shaped context (`action(` / `call(` on the same or an
adjacent line) rather than flagging every prose mention.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "apps/console/src"

ALLOWED = {
    SRC / "subscribeFlow.ts",
    SRC / "screens/Plans.tsx",
}

ACTION_IDS = re.compile(r"""['"](subscription\.activate|billing\.subscribe)['"]""")
CALL_SHAPED = re.compile(r"\b(action|call)\s*\(")


def offending_lines(path: Path) -> list[tuple[int, str]]:
    out = []
    lines = path.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if not ACTION_IDS.search(line):
            continue
        window = "\n".join(lines[max(0, i - 1):i + 2])
        if CALL_SHAPED.search(window):
            out.append((i + 1, line.strip()))
    return out


def main() -> int:
    bad: list[str] = []
    for path in SRC.rglob("*.ts*"):
        if path in ALLOWED:
            continue
        if path.name.endswith(".test.ts") or path.name.endswith(".test.tsx"):
            continue
        for lineno, text in offending_lines(path):
            bad.append(f"{path.relative_to(ROOT)}:{lineno}: {text}")
    if bad:
        print("A screen calls subscription.activate/billing.subscribe directly instead of "
              "going through useSubscribeFlow() (apps/console/src/subscribeFlow.ts):")
        for line in bad:
            print(f"  {line}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
