"""Every call that hands a message to WhatsApp names the number it leaves from — #386.

THE DEFECT THIS CLOSES. `sending_identity` decides which credential — which PHONE NUMBER — a
message is sent with, and it defaults to the establishment. A send site that omits it therefore
does not fail: it sends, from the central number, silently, for a shop that has moved to a number
per branch. There is no error, no queue, no red line anywhere; the customer simply receives a
message from the wrong branch of the shop he visited.

Two sites pass it today (`tick.py`, both send paths). This exists because a third is one feature
away, and the failure it would cause is the kind nobody reports because nothing looks broken.

READ, NOT LISTED. It finds the calls by looking for the sender's own method — anything of the form
`<something>.send(` carrying `template_name=`, which is what makes it a WhatsApp send rather than
any other `send` in the language — and requires `sending_identity=` inside the same call. Adding a
send path puts it under this check automatically; nothing has to be remembered.

WHAT IT CANNOT SEE: whether the identity is the RIGHT one. `tick._sending_identity` owns that, and
services/reminders/tests/unit/test_the_branch_decides_which_number_sends.py pins it.
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVICES = ROOT / "services"

# The opening of a send call. The body is taken by paren depth below, because a call that spans
# six lines is the normal shape here and a line-based match would read only its first line.
OPEN = re.compile(r"\.send\(")


def call_body(src: str, start: int) -> str:
    """From the opening paren to its match — the whole argument list, however many lines."""
    depth, i = 0, start
    while i < len(src):
        if src[i] == "(":
            depth += 1
        elif src[i] == ")":
            depth -= 1
            if depth == 0:
                return src[start:i + 1]
        i += 1
    return src[start:]


def main() -> int:
    bad: list[str] = []
    checked = 0
    for path in sorted(SERVICES.rglob("app/**/*.py")):
        if "/tests/" in path.as_posix():
            continue
        src = path.read_text(encoding="utf-8", errors="ignore")
        for m in OPEN.finditer(src):
            body = call_body(src, m.end() - 1)
            # A WhatsApp send names the template it is sending. Every other `.send(` in the
            # fleet — an event bus, a queue — does not, and is not this check's business.
            if "template_name=" not in body:
                continue
            checked += 1
            if "sending_identity=" not in body:
                line = src[:m.start()].count("\n") + 1
                bad.append(f"{path.relative_to(ROOT).as_posix()}:{line}")

    for b in bad:
        print(f"  \033[31m✗ {b}: sends a template without saying which number it leaves from\033[0m")
    if bad:
        print("\nA send with no `sending_identity` leaves from the establishment's number. For a "
              "shop on a number per branch that is the WRONG number, and nothing anywhere "
              "reports it — pass the identity rather than letting it default.")
        return 1
    if not checked:
        # A CLEAN REPO AND AN UNPLUGGED CHECK LOOK IDENTICAL FROM HERE. This finds sends by the
        # shape `.send(` + `template_name=`; rename either and the loop above matches nothing, the
        # count is zero, and this prints ok for ever while the rule it exists for goes unenforced.
        # There ARE template sends in this fleet — the day there are none, that is the news.
        print("  [31m✗ found no template sends at all — this check no longer knows where to "
              "look[0m")
        return 1
    print(f"ok {checked} template sends each name the number they leave from")
    return 0


if __name__ == "__main__":
    sys.exit(main())
