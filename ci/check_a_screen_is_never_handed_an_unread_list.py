"""A list a PERSON will read must say whether it was read at all.

WHAT THIS WAS WRITTEN AFTER. `PlatformLibrary.all()` returns the templates it holds, and on a peer
failure it returns `list(self._rows)` — the last good answer, or `[]` on a pod that has never had
one. That is the right behaviour for the SEND path: a scheduler with no library skips, retries next
tick, and nobody is told a story.

It is the wrong shape for a SCREEN. `/reasons/{id}/preview` handed that same list to the owner's
message preview, which rendered its emptiness as «لا توجد صيغة معتمدة لهذه الرسالة بعد. القوالب
تُراجَع لدى واتساب، وقد تستغرق ساعات» — a sentence naming a cause the screen has no evidence for.
Three different truths arrive as `[]`:

  * the library could not be read at all — ours to fix, and he should be told nothing more;
  * it was read and holds nothing for this reason — our gap, and Meta is not involved;
  * his OWN text is genuinely waiting at Meta — the only case that sentence describes.

Telling him to wait for WhatsApp in the first two is the failure this repository keeps finding: a
screen that states a cause it cannot know, and reassures where it should report.

THE RULE. A route that answers a person may not call the read that hides its own failure. `read()`
carries `ok` beside the rows; `all()` does not, and belongs to the paths where an empty answer is
handled rather than displayed. So: no module under `api/v1` may call `.library.all(`.

`api/internal.py` still may — its caller is another service, which has its own way of telling an
outage from an emptiness, and passing the flag there would be a contract nobody reads.

    python ci/check_a_screen_is_never_handed_an_unread_list.py
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVICES = ROOT / "services"

#: The read that cannot report its own failure, and the one that can.
HIDES_FAILURE = re.compile(r"\.library\.all\s*\(")
CARRIES_OK = ".library.read("


def main() -> int:
    if not SERVICES.is_dir():
        print("no services/ — this gate cannot answer, so it refuses to")
        return 1

    faults: list[str] = []
    checked = 0
    # EVERY USER-FACING ROUTE MODULE, by where it lives rather than by a list somebody maintains.
    # `api/v1` is what a person's browser reaches; `api/internal.py` is what a peer reaches.
    for path in sorted(SERVICES.glob("*/app/api/v1/*.py")):
        text = path.read_text(encoding="utf-8")
        checked += 1
        for m in HIDES_FAILURE.finditer(text):
            line = text[: m.start()].count("\n") + 1
            faults.append(
                f"{path.relative_to(ROOT)}:{line} calls `.library.all()` — which answers `[]` for "
                f"a read that FAILED exactly as it does for a library with nothing in it. A screen "
                f"cannot tell those apart, so it invents a reason. Call `.library.read()` and pass "
                f"its `ok` through.")

    if not checked:
        # SILENCE IS NOT AGREEMENT: no v1 modules found means this gate is pointed at nothing.
        print("no api/v1 module was read at all — this gate needs re-pointing. Refusing to report "
              "a pass over an empty set.")
        return 1

    if faults:
        for f in faults:
            print(f"  \033[31m✘ {f}\033[0m")
        print("\nAn empty list and an unread one are different answers, and only one of them is "
              "about the shop.")
        return 1

    print(f"  \033[32m✔ {checked} user-facing route module(s): none is handed a list that cannot "
          f"say whether it was read\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
