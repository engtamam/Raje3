"""A day or a month a PERSON lives in must be computed in Riyadh, never in UTC.

WHAT IT COST, AND IT WAS INVISIBLE BY CONSTRUCTION.

`statements_run.last_closed_month` cut the month with `time.gmtime`, so a month began at 03:00
Riyadh. Every partner settlement landing between midnight and 03:00 on the first was counted into
the month BEFORE. And nothing ever disagreed: both statements were built from the same wrong
boundary, so they reconciled with each other perfectly. The only ledger that disagreed was the
partner's own, and neither side had a line to point at.

`till_budget._day` keyed a per-day lookup allowance the same way, so a till's budget reset at 03:00
rather than midnight — a shop open past midnight lost its allowance mid-shift, and the forty-lookup
morning floor arrived three hours into the next day's work.

Meanwhile the rest of the product already knew: quiet hours, an offer's last day, the busiest-hour
chart and the campaign day-boundary are all Riyadh. Two places were not, and both were about money.

SCOPE IS BY USE, NOT BY SPELLING — WHICH IS THE WHOLE DIFFICULTY. `datetime.now(timezone.utc)` in
a log line is CORRECT: an instant has no timezone opinion, and an `updated_at` compared by machines
must never move with a locale. What is wrong is deriving a CALENDAR ANSWER from UTC — «which day
was this», «which month did this fall in» — because that answer is read by somebody who lives in
one. So this gate looks for a UTC call whose result is turned into a date, and says nothing about
the ones turned into instants.

A gate that banned `timezone.utc` outright would be wrong about most of its hits, and a gate wrong
about most of its hits is a gate people learn to scroll past.
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVICES = ROOT / "services"

#: A UTC clock read: `time.gmtime(...)`, `datetime.utcfromtimestamp(...)`, `fromtimestamp(x, utc)`,
#: `datetime.now(timezone.utc)`, `calendar.timegm(...)`.
UTC_CALL = re.compile(
    r"time\.gmtime\b|\butcfromtimestamp\b|\butcnow\b|calendar\.timegm\b"
    r"|fromtimestamp\([^)]*timezone\.utc|now\(\s*(?:_dt\.)?timezone\.utc\s*\)")

#: What turns an instant into a CALENDAR ANSWER — a day, a month, a year. `%Y-%m-%d` with nothing
#: after it is a date; `%Y-%m-%dT%H:%M:%SZ` is an instant and is none of this gate's business.
A_DATE = re.compile(r"""["']%Y-%m-%d["']|["']%Y-%m["']|\.date\(\)|\btm_mon\b|\btm_year\b"""
                    r"""|["']%Y-%m-%d\s+%H""")


def main() -> int:
    if not SERVICES.is_dir():
        # A GATE THAT CANNOT READ MUST FAIL LOUDLY.
        print("no services/ directory — this gate cannot answer, so it refuses to")
        return 1

    files = [f for f in sorted(SERVICES.rglob("*.py")) if "test" not in f.parts]
    if not files:
        # SILENCE IS NOT AGREEMENT: reading nothing is not the same as finding nothing.
        print("no service source found — this gate needs re-pointing")
        return 1

    hits: list[str] = []
    checked = 0
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"cannot read {rel}: {exc}")
            return 1

        # PROSE DECIDES NOTHING. Every file that lost this defect explains it in a comment naming
        # `time.gmtime`, and a gate reading raw text is then satisfied — or accused — by the note
        # describing the bug rather than by the code. This is the fifth gate this week to need it.
        lines = text.split("\n")
        code = "\n".join("" if ln.lstrip().startswith("#") else ln for ln in lines)
        code = re.sub(r'"""(?:[^"\\]|\\.|"(?!""))*"""',
                      lambda m: re.sub(r"[^\n]", " ", m.group()), code)

        for n, line in enumerate(code.split("\n"), start=1):
            if not UTC_CALL.search(line):
                continue
            checked += 1
            # The date conversion may sit on this line or on the one that consumes it, so a small
            # window is read rather than the single line — `t = time.gmtime(...)` then `t.tm_mon`.
            window = "\n".join(code.split("\n")[n - 1:n + 4])
            if A_DATE.search(window):
                hits.append(f"{rel}:{n}: {line.strip()[:90]}")

    if hits:
        print(f"{len(hits)} place(s) compute a person's day or month from UTC:")
        for h in hits:
            print("  " + h)
        print("\nUTC is three hours behind Riyadh, so a boundary drawn there cuts the day at 03:00.")
        print("Use services/operations/app/core/riyadh.py — `day_key` and `last_closed_month`.")
        print("\nAn instant is different and stays UTC: a log line, an `updated_at`, an ISO stamp")
        print("handed to a peer. What must be local is the answer to «which day was this».")
        return 1

    print(f"{checked} UTC clock reads across {len(files)} files: none of them draws a person's "
          f"day or month")
    return 0


if __name__ == "__main__":
    sys.exit(main())
