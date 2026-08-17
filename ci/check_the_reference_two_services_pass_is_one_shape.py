"""The reference reminders writes into a link is the reference portal reads out of one.

WHAT THIS CAUGHT. portal mints the customer's reference as `f"{tenant}.{subject_ref}"` and splits
it back on the first dot (portal/app/core/reference.py). reminders composes the address a customer
taps (reminders/app/core/links.py) — and its pattern excluded the dot entirely, so every URL it
could ever have produced would have been REFUSED at render: the customer page, the grant screen,
and the one-tap stop that §8.3 makes mandatory for every marketing message.

Nothing was red, and nothing could have been. No template in the library declared a link slot, so
the producer and the consumer had never once met. The day the first template carried a link would
have been the day every send in the product started failing — or, with a laxer pattern, the day
every customer of every shop received an address that opens a page belonging to nobody.

AND THE COST OF FINDING IT LATE IS NOT A DEPLOY. The link is inside the body of a template Meta has
approved. A template's text is frozen at approval and its name cannot be reused, so correcting a
separator after launch means resubmitting the entire library under new names and waiting out a
second review, per establishment.

THE RULE, WITH NO EXCEPTIONS TABLE. Both services agree on the separator, and each writes it
exactly once. portal's `build()` joins on it; reminders' `reference_for()` joins on it; and
reminders' `SAFE_REFERENCE` — the pattern that decides whether a composed URL is allowed out —
must accept what `build()` produces.

WHAT IT CANNOT SEE, said plainly:
  · whether the reference names a real customer. portal's `parse()` is the authority on that, and
    reminders deliberately does not re-derive it — a producer stricter than its consumer refuses
    work that would have been served;
  · a third service composing its own link. This compares the two that exist; a new one is a new
    line here, and the failure it would otherwise cause is the one described above.

    python ci/check_the_reference_two_services_pass_is_one_shape.py
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PORTAL = ROOT / "services" / "portal" / "app" / "core" / "reference.py"
REMINDERS = ROOT / "services" / "reminders" / "app" / "core" / "links.py"

#: How each side spells the join. Read from the source rather than imported: these are two
#: deployables with two dependency sets, and a gate that needs either installed stops running.
JOIN = re.compile(r'return f"\{tenant\}(?P<sep>.)\{subject_ref\}"')

#: The pattern reminders applies to a composed reference before letting it into a URL.
SAFE = re.compile(r"^SAFE_REFERENCE = re\.compile\(r?\"(?P<pattern>.+)\"\)$", re.M)


def main() -> int:
    for path in (PORTAL, REMINDERS):
        if not path.is_file():
            # SILENCE IS NOT AGREEMENT. A missing file makes every comparison below vacuous, and a
            # gate that passes for having found nothing is the defect it exists to catch.
            print(f"FAIL: {path.relative_to(ROOT).as_posix()} is missing — this gate compared "
                  f"nothing, which is not the same as the two services agreeing")
            return 1

    portal_src = PORTAL.read_text(encoding="utf-8")
    reminders_src = REMINDERS.read_text(encoding="utf-8")

    seps = {}
    for name, src in (("portal", portal_src), ("reminders", reminders_src)):
        found = JOIN.search(src)
        if not found:
            print(f"FAIL: no `f\"{{tenant}}<sep>{{subject_ref}}\"` join found in {name} — either "
                  f"the reference stopped being built there, or it stopped being built in a shape "
                  f"this gate can read. Both leave the seam unchecked.")
            return 1
        seps[name] = found.group("sep")

    if seps["portal"] != seps["reminders"]:
        print(f"FAIL: the two services join the reference differently — portal uses "
              f"{seps['portal']!r} and reminders uses {seps['reminders']!r}.\n"
              f"  Every link a customer taps would open a page that knows nobody, and the link is "
              f"inside a template Meta has already approved.")
        return 1

    pattern = SAFE.search(reminders_src)
    if not pattern:
        print("FAIL: no module-level SAFE_REFERENCE in reminders/core/links.py — the pattern that "
              "decides whether a composed URL may go out is the thing this gate checks")
        return 1

    # THE PROOF IS A COMPOSED VALUE, NOT A READING OF THE REGEX. Two patterns can look compatible
    # and disagree on one character; the only honest test is to build a reference the way portal
    # builds it and ask reminders whether it would allow it out.
    sep = seps["portal"]
    sample = f"tnt_page{sep}sub_{'a' * 32}"
    if not re.compile(pattern.group("pattern")).fullmatch(sample):
        print(f"FAIL: reminders refuses the reference portal mints.\n"
              f"    portal builds:      {sample}\n"
              f"    reminders allows:   {pattern.group('pattern')}\n"
              f"  So every address composed for a customer — the page, the grant screen, and the "
              f"mandatory one-tap stop (§8.3) — is refused at render and no message goes out.")
        return 1

    print(f"OK: both services join the reference on {sep!r}, and reminders lets the result out")
    return 0


if __name__ == "__main__":
    sys.exit(main())
