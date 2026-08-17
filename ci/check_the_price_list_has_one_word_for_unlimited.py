"""«Unlimited» is a word in this product, never -1 — and a reader must accept the word.

WHY THE PRICE LIST FORBIDS THE NUMBER, in its own sentence (`deploy/seed/plans.json`):

    `unlimited` RATHER THAN -1. billing merges its own sentinel by beating every arithmetic;
    -1 is just a number to it, and two of them summed to -2 — which refuses every send.

So this is not a style preference. A shop holding two plans that both spell it -1 gets -2, and -2
is below every quantity, so every send is refused. The word cannot be summed and therefore cannot
produce that.

WHAT WAS ACTUALLY WRONG. `subscribe.granted_keys` read the limit with `int()` inside a `try` and
`continue`d on failure — so a feature carrying the sanctioned WORD was not a grant, and not an
error either. It was absent from the set: a shop that paid for an app would not hold it, with
nothing raised anywhere. And the comment beside it read «-1 is unlimited», teaching the next author
the exact value the price list spends a paragraph forbidding. `reminders/core/quota.py` said the
same thing in its module docstring, about our own plans.

TWO SPELLINGS, AND ONLY ONE IS OURS. `-1 unlimited, 0 unknown` is notification-service's OWN
contract for the WhatsApp ceiling, documented as theirs in five places and correct there. This
gate is not about that number; it is about OUR plan limits being described as -1. So the scope is
the files that read a plan's `limit`, and the finding is prose or code that equates our unlimited
with -1.

A GATE ON WHAT IS TAUGHT, NOT ONLY ON WHAT RUNS. The code was fixed in one line; the comments are
what would have produced the next instance, and this repository has now seen four defects in a
week whose root was prose read as truth.
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLANS = ROOT / "deploy" / "seed" / "plans.json"
SERVICES = ROOT / "services"

#: A file that reads a PLAN's limit — as opposed to notification-service's ceiling, which is a
#: different number owned by somebody else and correctly spelled -1.
READS_A_PLAN_LIMIT = re.compile(r"limits_snapshot|granted_keys|plans\.json|messages\.monthly")

#: Our unlimited equated with the forbidden number, in prose or in code.
TEACHES_MINUS_ONE = re.compile(
    r"-1\s+is\s+unlimited|unlimited\s+at\s+-1|at\s+-1[,.]?\s+and\s+unlimited"
    r"|`?messages\.monthly`?\s+at\s+-1|limit\s*==\s*-1\s*#.*unlimited", re.IGNORECASE)


def main() -> int:
    if not PLANS.is_file():
        # A GATE THAT CANNOT READ ITS AUTHORITY MUST FAIL LOUDLY.
        print(f"{PLANS.relative_to(ROOT).as_posix()} is missing — this gate cannot answer")
        return 1
    plans = PLANS.read_text(encoding="utf-8")
    if '"unlimited"' not in plans:
        # SILENCE IS NOT AGREEMENT: if the price list stopped using the word, this gate is
        # enforcing a rule that no longer exists and must say so rather than pass.
        print("deploy/seed/plans.json no longer spells any limit `unlimited` — the rule this gate "
              "enforces may have changed, and it will not decide that quietly")
        return 1

    # TESTS ARE IN SCOPE HERE, UNLIKE EVERY OTHER GATE IN THIS DIRECTORY. One of the two places
    # teaching the forbidden value was a test's docstring asserting that our plans carry it — and a
    # test is the most persuasive prose in a repository, because it reads as verified.
    files = sorted(SERVICES.rglob("*.py"))
    if not files:
        print("no service source found — this gate needs re-pointing")
        return 1

    hits: list[str] = []
    scoped = 0
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"cannot read {rel}: {exc}")
            return 1
        if not READS_A_PLAN_LIMIT.search(text):
            continue                       # somebody else's sentinel is somebody else's business
        scoped += 1
        for n, line in enumerate(text.split("\n"), start=1):
            if TEACHES_MINUS_ONE.search(line):
                hits.append(f"{rel}:{n}: {line.strip()[:88]}")

    if hits:
        print(f"{len(hits)} place(s) call OUR unlimited -1:")
        for h in hits:
            print("  " + h)
        print("\nThe price list forbids the number and says why: billing beats every arithmetic "
              "with its own sentinel, so two plans at -1 sum to -2 — and -2 refuses every send.")
        print("Spell it `unlimited`, and make the reader accept the word.")
        return 1

    print(f"{scoped} plan-limit readers: none of them calls our unlimited -1")
    return 0


if __name__ == "__main__":
    sys.exit(main())
