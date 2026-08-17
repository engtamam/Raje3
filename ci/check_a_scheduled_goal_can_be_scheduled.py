"""A goal the engine only fires on a date must have a way to name that date.

WHAT IT COST. `occasion` — «هنّئ في مناسبة · رسالة في يوم يخصّه» — is one of the six goals the
launch screen offers, and the only one whose trigger is `scheduled`. The dispatcher's guard for a
scheduled campaign is:

    if not fire_at or fire_at > now: skipped

So `fire_at = 0` does not mean «send now». It means «skip, on this tick and every tick after it,
for ever». The console never sent `fire_at`. Every congratulation campaign a shop ever created was
accepted by the door, stored, listed as active, previewed with a correct audience count, and
confirmed with تم — and not one of them was ever delivered. Nothing failed at any layer: no 4xx, no
exception, no log line. The campaign simply sat there being skipped, and the owner's evidence that
it worked was the banner we showed him.

The engine half was even TESTED — `test_a_scheduled_campaign_with_no_time_never_fires` asserts
exactly this behaviour, correctly, and passes. The test proved the guard works; nothing asked
whether anything could ever satisfy it.

WHY A GATE AND NOT A TEST. A test would pin `occasion`. The rule is about a KIND of goal: the day
somebody adds a second scheduled goal, the same silence returns, and a test naming `occasion`
stays green through all of it. So the scheduled goals are READ from `GOAL_TRIGGER` — the one place
that decides which they are — and the console is required to carry the field for them.

WHAT IT CHECKS, AND WHY THAT IS THE WEAKEST HONEST CLAIM. That the console SENDS `fire_at` at all.
Not that the control is usable, not that the date is right — mentioned in a request body, which is
the least this can be and still catch a whole feature that never once ran.
"""
from __future__ import annotations

import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
MODELS = ROOT / "services" / "campaigns" / "app" / "core" / "models.py"
CONSOLE = ROOT / "apps" / "console" / "src"

#: The field the dispatcher reads to decide whether a scheduled campaign may go.
SCHEDULE_FIELD = "fire_at"


#: `/* … */` and `// …`. A `//` inside a string is not a comment, so only a line whose FIRST
#: non-space characters are the marker is cut — a cruder rule would blind this gate to a real call
#: that shares its line with a trailing note.
BLOCK = re.compile(r"/\*.*?\*/", re.DOTALL)


def _code(text: str) -> str:
    """The source with its prose removed."""
    text = BLOCK.sub("", text)
    return "\n".join("" if line.lstrip().startswith("//") else line
                     for line in text.split("\n"))


def scheduled_goals() -> list[str]:
    """The goals `GOAL_TRIGGER` marks as scheduled — read, never restated here."""
    tree = ast.parse(MODELS.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if "GOAL_TRIGGER" not in names or not isinstance(node.value, ast.Dict):
            continue
        out = []
        for key, value in zip(node.value.keys, node.value.values):
            if (isinstance(key, ast.Constant) and isinstance(value, ast.Constant)
                    and value.value == "scheduled"):
                out.append(key.value)
        return out
    return []


def main() -> int:
    if not MODELS.is_file():
        # A GATE THAT CANNOT READ MUST FAIL LOUDLY.
        print(f"{MODELS.relative_to(ROOT).as_posix()} is missing — this gate cannot answer")
        return 1
    if not CONSOLE.is_dir():
        print("apps/console/src is missing — this gate cannot answer")
        return 1

    goals = scheduled_goals()
    if not goals:
        # SILENCE IS NOT AGREEMENT. Finding no scheduled goals is how a renamed constant or a
        # changed shape would look, and it is indistinguishable from «all of them are fine».
        print("GOAL_TRIGGER declares no scheduled goal — either the map moved or this gate needs "
              "re-pointing. Both are answers this gate must not give silently")
        return 1

    # COMMENTS ARE STRIPPED, AND THE FIRST VERSION OF THIS GATE DID NOT STRIP THEM. Every file
    # that lost or gained this wire carries a note explaining it, so `fire_at` sits in prose right
    # beside the code — and a gate reading raw text is satisfied by the sentence describing the bug
    # instead of by the fix. Deleting both call sites left it green.
    console = "\n".join(_code(p.read_text(encoding="utf-8"))
                        for p in sorted(CONSOLE.rglob("*.ts*")))
    if not console.strip():
        print("read no console source — this gate needs re-pointing")
        return 1

    if not re.search(rf"\b{re.escape(SCHEDULE_FIELD)}\b", console):
        print(f"{len(goals)} goal(s) fire only on a date the owner sets — "
              f"{', '.join(sorted(goals))} — and the console never sends `{SCHEDULE_FIELD}`.")
        print(f"\nThe dispatcher skips a scheduled campaign whose `{SCHEDULE_FIELD}` is 0, on every")
        print("tick, for ever. So these campaigns are created, listed as active, previewed with a")
        print("real audience, confirmed with تم — and never delivered. Nothing fails; there is no")
        print("error to find later.")
        return 1

    print(f"{len(goals)} scheduled goal(s) — {', '.join(sorted(goals))} — and the console sends "
          f"`{SCHEDULE_FIELD}`")
    return 0


if __name__ == "__main__":
    sys.exit(main())
