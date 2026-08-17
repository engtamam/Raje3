"""A scheduled run's worst case must fit inside the timeout of the thing that calls it.

WHAT IT COST, AND IT IS THE PUREST FORM OF A DEFECT NO SINGLE-FILE REVIEW FINDS (ي-7). The
CronJob's body is `urlopen(..., timeout=300)`. The run it starts walks a batch, each item with its
own timeout. Both numbers are written down — one in this repository, one in the platform's chart —
and nobody had ever multiplied them together. Every side is correct on its own.

Measured on the live fleet: backup-service registers 20 targets at `BACKUP_TARGET_TIMEOUT_SECONDS:
120`, which is 2400 seconds against a caller that waits 300.

WHAT HAPPENS WHEN THE PRODUCT EXCEEDS THE PATIENCE is the worst outcome available: the work
SUCCEEDS and is reported FAILED. The caller gives up, the Job exits non-zero, the alert fires, and
somebody spends a morning on a backup that worked. Then the second reading arrives — «it always
fails, ignore it» — and that is how a real failure gets missed.

THIS GATE READS THE REPOSITORY ONLY, and that is deliberate: the batch size and the per-item
timeout are both declared here, so the arithmetic is available on every push, long before anybody
is standing in front of a cluster. `deploy/verify-fleet.sh` does the live half, using the count of
targets actually registered rather than the declared maximum.

NOT EVERY MEMBER IS EQUALLY URGENT, AND THE OUTPUT SAYS SO. A tick reaches its worst case only if
EVERY peer call times out — and a run where every call times out is failing on its own merits
rather than being misreported. `concurrencyPolicy: Forbid` already stops a slow tick overlapping
the next, and a killed tick retries on the following schedule with its work intact. The backup is
different: 120 seconds per target is a plausible NORMAL duration for copying a collection, so it
is the one where a healthy run is misreported today.

All of them are reported because the invariant does not hold for any of them, and the remedy for
all of them is the same single escalation — the 300 in `platform/deploy/chart/templates/
cronjob.yaml`, which this repository may not edit.
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVICES = ROOT / "deploy" / "services"
CHART_CRON = ROOT / "platform" / "deploy" / "chart" / "templates" / "cronjob.yaml"

#: How long the CronJob body waits for the route it POSTs to. Read from the chart rather than
#: written here, so the day somebody raises it this gate agrees without being edited.
CALLER = re.compile(r"urlopen\([^)]*timeout=(\d+)")

#: A per-item budget: how long one unit of the run may take.
A_TIMEOUT = re.compile(r"^\s+([A-Z0-9_]*TIMEOUT[A-Z0-9_]*): *\"?(\d+)\"?", re.M)

#: How many units one run may process.
A_BATCH = re.compile(r"^\s+([A-Z0-9_]*BATCH[A-Z0-9_]*): *\"?(\d+)\"?", re.M)


def main() -> int:
    if not SERVICES.is_dir():
        print("no deploy/services — this gate cannot answer, so it refuses to")
        return 1
    if not CHART_CRON.is_file():
        # A GATE THAT CANNOT READ ITS AUTHORITY MUST FAIL LOUDLY. The caller's patience is the
        # number everything here is compared against; inventing a default would put it in a third
        # place, which is the defect this gate exists to catch.
        print("platform/deploy/chart/templates/cronjob.yaml is missing — the caller's timeout "
              "cannot be read, so no window can be judged")
        return 1

    m = CALLER.search(CHART_CRON.read_text(encoding="utf-8"))
    if not m:
        print("the CronJob body no longer spells its timeout as `urlopen(..., timeout=N)` — this "
              "gate is reading for a shape that changed and will not guess")
        return 1
    caller = int(m.group(1))

    files = sorted(SERVICES.glob("*.values.yaml"))
    if not files:
        # SILENCE IS NOT AGREEMENT.
        print("no values files found — this gate needs re-pointing")
        return 1

    over: list[str] = []
    judged = 0
    for path in files:
        text = path.read_text(encoding="utf-8")
        if "cronJobs:" not in text:
            continue
        timeouts = {k: int(v) for k, v in A_TIMEOUT.findall(text)}
        batches = {k: int(v) for k, v in A_BATCH.findall(text)}
        if not timeouts or not batches:
            continue                      # nothing declared to multiply; not this gate's business
        # THE SMALLEST TIMEOUT AND THE LARGEST BATCH — the pair a run is most likely to hit, and
        # the pair a reader would reach for. Taking the largest timeout would flatter the number.
        pk = min(timeouts, key=lambda k: timeouts[k])
        bk = max(batches, key=lambda k: batches[k])
        worst = timeouts[pk] * batches[bk]
        judged += 1
        if worst > caller:
            svc = path.stem.replace(".values", "")
            over.append(f"{svc}: {batches[bk]} x {timeouts[pk]}s = {worst}s, caller waits "
                        f"{caller}s  ({bk} x {pk})")

    if over:
        print(f"{len(over)} of {judged} scheduled run(s) can outlast the caller that started them:")
        for line in over:
            print("  " + line)
        print(f"\nA run that finishes after {caller}s is reported FAILED whether or not it worked.")
        print("The alert fires, somebody investigates a success, and the next real failure is read")
        print("as more of the same.")
        print("\nThe caller's timeout lives in platform/deploy/chart/templates/cronjob.yaml, which")
        print("this repository does not edit: raise it there, or make the route answer immediately")
        print("and report through its own runs endpoint.")
        return 1

    print(f"{judged} scheduled run(s): every worst case fits inside the caller's {caller}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
