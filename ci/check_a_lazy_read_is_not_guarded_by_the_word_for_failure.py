"""A screen that fetches lazily must ask «not yet», never «did it fail».

WHAT THIS PROTECTS. `loading.ts` gave every fetched value four states, and the two that matter here
are `undefined` — not yet, render the skeleton — and `null` — it failed, render the sentence. Before
that, screens held two states and `null` meant «nothing here yet», so a lazily-loaded tab was
written as:

    if (tab !== 'overdue' || overdue !== null) return;   // fetch once, when nothing is here yet

When the vocabulary changed, that line kept the old meaning and inverted itself. «من تأخّر» opened at
`undefined`, the guard read it as «already handled», NOTHING WAS EVER REQUESTED, and the tab was a
grey rectangle for ever — the exact defect the four states were introduced to end. The mirror image
is just as bad: had the tab ever reached `null`, the guard would have re-entered on every render and
hammered the service with a failing call.

THE RULE. In an effect, a `Loading<>` value decides whether to fetch by whether it is `undefined`.
`null` is an answer — the answer «it failed» — and answers do not start requests.

NO EXCEPTIONS TABLE. There is no screen for which «fetch again because the last attempt failed, on
every render, for ever» is the intent. If a retry is wanted it is a button that sets the state back
to `undefined`, which this gate reads as the truth it is.
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "apps" / "console" / "src"

# The states a screen fetches, by the type it declares them with. A guard is only interesting when
# the name it tests is one of these.
DECLARED = re.compile(r"useState<\s*Loading<[^>]*>[^>]*>\s*\(")
NAMED = re.compile(r"const\s*\[\s*(\w+)\s*,\s*set\w+\s*\]\s*=\s*useState<\s*Loading<")

# `if (… x !== null …) return` / `if (x === null) return` — a fetch decision keyed on failure.
GUARD = re.compile(r"if\s*\([^)]*?\b(\w+)\s*[!=]==\s*null[^)]*?\)\s*(?:\{[^}]*)?return\b")


def main() -> int:
    files = sorted(p for p in SRC.rglob("*.tsx") if not p.name.endswith(".test.tsx"))
    if not files:
        # SILENCE IS NOT AGREEMENT: no screens found means this gate lost its subject.
        print("no console screens found — this gate needs re-pointing")
        return 1

    bad: list[str] = []
    watched = 0
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"cannot read {path.relative_to(ROOT).as_posix()}: {exc}")
            return 1
        if not DECLARED.search(text):
            continue
        fetched = set(NAMED.findall(text))
        watched += len(fetched)
        for line_no, line in enumerate(text.splitlines(), start=1):
            hit = GUARD.search(line)
            if hit and hit.group(1) in fetched:
                bad.append(
                    f"{path.relative_to(ROOT).as_posix()}:{line_no} · `{hit.group(1)}` is a fetched "
                    "value and this guard decides by `null`. `null` means «it failed»; «not yet» is "
                    "`undefined` — so the read never starts, or repeats for ever."
                )

    if not watched:
        print("no lazily fetched values found — this gate needs re-pointing")
        return 1
    if bad:
        print("A lazy read is guarded by the word for failure:")
        for line in bad:
            print("  " + line)
        return 1
    print(f"{watched} fetched value(s): every lazy read asks «not yet», not «did it fail»")
    return 0


if __name__ == "__main__":
    sys.exit(main())
