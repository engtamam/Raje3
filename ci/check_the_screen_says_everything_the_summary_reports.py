"""Every number the health summary reports must reach the screen that summary was built for.

WHAT HAPPENED THE DAY BEFORE THIS GATE. The summary behind «هل كل شيء يعمل؟» learned to tell a
message that is calmly waiting from one that has failed eleven times, and reported the second under
its own key with its own sentence. The screen rendered `sent_today` and `waiting`, as it always
had, and knew nothing about the new key.

So the fix stopped one layer short of the person it was for. The shop whose every message was
failing still read two calm numbers — and the work, the gate and the tests behind it were all
correct and all invisible. This repository has closed that shape a dozen times under a dozen names:
a thing built, wired, tested, and called by nobody.

THE RULE. The `messages` block of the today summary is a contract with one screen. Every key in it
must appear in that screen's source. Not «rendered nicely» — a check cannot judge that — but
NAMED, so that adding a number to the service forces somebody to decide what the owner reads.

WHY THIS BLOCK AND NOT EVERY RESPONSE IN THE PRODUCT. This one has a single consumer and a single
purpose: it is the answer to a question the screen is named after. A gate over every field of every
endpoint would be a different rule with a different, much weaker justification — and it would need
an exceptions table by the second day, which is what this repository does not keep.

    python ci/check_the_screen_says_everything_the_summary_reports.py
"""
from __future__ import annotations

import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "services" / "reminders" / "app" / "api" / "v1" / "owner.py"
SCREEN = ROOT / "apps" / "console" / "src" / "screens" / "Shop.tsx"  # Today.tsx merged in, 6c6345d6

#: The block the screen is built from.
BLOCK = "messages"

#: THE SHAPE DECLARATION IS NOT THE SCREEN. A key typed in `interface Today` and rendered nowhere
#: satisfies a naive search and leaves the owner reading the old numbers — which is precisely the
#: defect this gate exists for, wearing a type annotation. Proved by sabotage: deleting the block
#: that renders the number left this gate green until the declaration was excluded from the
#: evidence, so the declaration is cut out before anything is looked for.
DECLARATION = re.compile(r"\binterface\s+\w+\s*\{")


def _without_declarations(source: str) -> str:
    """The screen with its `interface X { … }` blocks cut out.

    BY COUNTING BRACES, NOT BY MATCHING TO THE NEXT `}`. A regex that stopped at the first
    line-initial brace swallowed the whole render body of the component following a one-line
    interface, and the gate then reported that the screen says nothing at all — a lie in the other
    direction, and one that would have been «fixed» by weakening the rule. A block ends where its
    own brace does.
    """
    out = source
    while True:
        found = DECLARATION.search(out)
        if not found:
            return out
        depth, i = 0, found.end() - 1
        while i < len(out):
            if out[i] == "{":
                depth += 1
            elif out[i] == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        out = out[:found.start()] + out[i + 1:]


def _keys_of_messages_block(tree: ast.AST) -> list[str]:
    """Every key of the `"messages": { … }` dict the summary returns."""
    out: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values):
            if (isinstance(key, ast.Constant) and key.value == BLOCK
                    and isinstance(value, ast.Dict)):
                for k in value.keys:
                    if isinstance(k, ast.Constant) and isinstance(k.value, str):
                        out.append(k.value)
    return out


def main() -> int:
    for path in (SUMMARY, SCREEN):
        if not path.is_file():
            print(f"{path.relative_to(ROOT)} is missing — one half of this contract is not where "
                  f"it was, and «cannot find it» is not a pass")
            return 1

    keys = _keys_of_messages_block(ast.parse(SUMMARY.read_text(encoding="utf-8")))
    if not keys:
        # THE BLOCK IS GONE OR RESHAPED. Silence here would mean this gate quietly stopped
        # checking anything — the one outcome a gate may never have.
        print(f"  \033[31m✘ the summary no longer returns a «{BLOCK}» block — point this gate at "
              f"what replaced it\033[0m")
        return 1

    screen = _without_declarations(SCREEN.read_text(encoding="utf-8"))
    missing = [k for k in sorted(set(keys)) if k not in screen]
    if missing:
        print("  \033[31m✘ the summary reports numbers the screen never says:\033[0m")
        for key in missing:
            print(f"      \033[31m{BLOCK}.{key} — absent from "
                  f"{SCREEN.relative_to(ROOT).as_posix()}\033[0m")
        print("\n    Render it, or stop computing it. A number the service knows and the screen "
              "does not say is\n    work nobody receives — and the owner keeps reading the "
              "numbers that were true yesterday.\n    Do not exempt it here.")
        return 1

    print(f"  \033[32m✔ the screen says every number the summary reports "
          f"({len(set(keys))} of them)\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
