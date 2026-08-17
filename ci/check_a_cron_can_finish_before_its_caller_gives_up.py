"""One tenant's slice of a scheduled run must fit inside the timeout of the thing that calls it.

READ THE SECOND SECTION BEFORE THE FIRST. This gate's first version asked a bigger question — «does
the WHOLE run fit» — got the arithmetic wrong by a factor of two hundred, and a batch size was
lowered on the strength of the wrong number. What follows records both the original finding and the
correction, because the correction is the more useful of the two.

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

THE CORRECTION, AND WHY IT CHANGED THE QUESTION THIS GATE ASKS. The first version multiplied ONE
batch by ONE per-item timeout and reported `reminders: 100 x 8s = 800s`. But the tick is NESTED:
`services/reminders/app/api/internal.py` walks `for tenant in tenants[:TICK_MAX_TENANTS]` — 200 —
and inside each tenant runs a SEQUENTIAL pass over `TICK_BATCH_SIZE` rows, each row a live send
(`services/reminders/app/core/tick.py`). The real bound is 200 x 30 x 8s = 48000s. Thirteen hours
against a caller that waits five minutes.

WHICH MEANS NO VALUE IN THIS REPOSITORY MAKES THE WHOLE RUN FIT. Even one row per tenant is
200 x 8s = 1600s. The run's SHAPE exceeds the caller, not its batch size, and both remedies are
outside this tree: raise the 300 in `platform/deploy/chart/templates/cronjob.yaml`, or make the
route answer immediately and report through its own runs endpoint. That is a standing escalation,
and it is printed on every run of this gate below — including on the green ones.

SO THE GATE JUDGES THE HALF THAT IS OURS: one tenant's slice. `inner batch x per-item timeout` is
made entirely of numbers we own, it is the thing that decides WHO GETS SERVED before the caller's
guillotine falls, and it holds today at 30 x 8s = 240s. Raise a batch to 100 and it goes red — which
is exactly the edit that would otherwise quietly starve every tenant after the first.

A GATE THAT CAN ONLY EVER BE RED IS A GATE PEOPLE LEARN TO SCROLL PAST, and this repository already
carries two of those waiting on a platform release. Failing forever on a number we may not edit
would have taught the same habit against a real invariant. The escalation is louder as text that
prints every time than as a red mark that becomes furniture.
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

#: THE INNER BOUND — how many units one tenant's slice touches. This half is ours to judge.
#:
#: THE FIRST VERSION OF THIS GATE MULTIPLIED ONE BATCH BY ONE TIMEOUT AND CALLED IT THE RUN, AND
#: WAS WRONG BY A FACTOR OF TWO HUNDRED.
#:
#: THE FIRST VERSION OF THIS GATE MULTIPLIED ONE BATCH BY ONE TIMEOUT AND WAS WRONG BY A FACTOR OF
#: TWO HUNDRED. reminders' tick is `for tenant in tenants[:TICK_MAX_TENANTS]` with, inside it, a
#: sequential pass over `TICK_BATCH_SIZE` rows — so the run's worst case is the PRODUCT of both
#: bounds and the per-item timeout, not of the inner pair. The gate reported 800s for a loop whose
#: bound is 160,000, and I lowered a batch size on the strength of that number.
#:
#: A service with no inner bound declared has a slice of one unit, which is the honest reading:
#: `operations` walks tenants and does one sync each.
#:
#: `_LIMIT` IS IN HERE BECAUSE THE FLEET SPELLS THE SAME IDEA THREE WAYS, AND I ONLY KNEW TWO.
#: `BACKUP_TARGET_LIMIT`, `EXPIRY_SWEEP_LIMIT`, `NOTIFY_DRAIN_LIMIT`, `SNAPSHOT_VISIT_LIMIT` — all
#: of them cap how many units one run touches, exactly as `BATCH` does, and this gate was blind to
#: every one. It reported `insights` as fitting comfortably while a 5000-visit bound sat in the
#: same file, under a comment about being killed at 300s. A pattern that encodes one vocabulary
#: for a concept the codebase spells several ways is a gate that answers about the half it knows.
A_INNER = re.compile(r"^\s+([A-Z0-9_]*(?:BATCH|_LIMIT)[A-Z0-9_]*): *\"?(\d+)\"?")

#: THE DECLARATION THAT MAKES A BOUND MULTIPLIABLE, WRITTEN ABOVE THE BOUND ITSELF.
#:
#: PER BOUND, NOT PER FILE, BECAUSE ONE FILE CAN HOLD BOTH KINDS. `insights` declares
#: `SNAPSHOT_BATCH` — thirty tenants, one peer call each — AND `SNAPSHOT_VISIT_LIMIT`, five
#: thousand rows INSIDE one of those calls. A file-level marker would have multiplied both and
#: reported 40240s, or neither and ignored a real peer loop. Both readings would have been wrong.
#:
#: AND IT MAY NAME ITS OWN COST. `each-unit-is-a-remote-call: HTTP_TIMEOUT_SECONDS` pins which
#: timeout applies; without a name the gate falls back to the smallest declared, which is the
#: conservative guess and NOT always the true one — notification-service declares a 3s consent
#: timeout beside a 15s HTTP one, and it is the HTTP one a delivery actually costs.
PAIRED = re.compile(r"each-unit-is-a-remote-call(?::\s*([A-Z0-9_]+))?")

#: The counter-declaration: this bound counts rows inside one call, so multiplying it by a per-call
#: timeout says nothing. Reported nowhere, because the question has been answered.
LOCAL = re.compile(r"each-unit-is-a-local-read")

#: A BOUND THAT IS A RUNAWAY CEILING RATHER THAN A WORKING VALUE. `BACKUP_TARGET_LIMIT: 500` is the
#: upstream default over a fleet of about eighteen services — lowering it until the arithmetic fits
#: would mean backing up two collections and calling it a backup. A service that says this is
#: reported WITH the escalation rather than as a knob somebody should turn, because turning it is
#: the wrong repair. The file already said exactly this in prose; this is that sentence made
#: machine-readable, so the gate stops demanding an edit nobody should make.
CEILING = re.compile(r"a-ceiling-not-a-tuning-knob")

#: THE OUTER BOUND — how many tenants the run walks. Not ours to fit inside 300s at any value, so
#: it is not judged; it is multiplied into the escalation line so the true number is on screen.
A_OUTER = re.compile(r"^\s+([A-Z0-9_]*MAX_TENANTS[A-Z0-9_]*): *\"?(\d+)\"?", re.M)


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
    escalate: list[str] = []
    unpaired: list[str] = []
    judged = 0
    for path in files:
        text = path.read_text(encoding="utf-8")
        if "cronJobs:" not in text:
            continue
        timeouts = {k: int(v) for k, v in A_TIMEOUT.findall(text)}
        if not timeouts:
            continue                      # nothing declared to multiply; not this gate's business
        svc = path.stem.replace(".values", "")
        # EACH BOUND IS READ WITH THE COMMENT BLOCK ABOVE IT, because the declaration belongs to
        # the bound and not to the file: see the note on PAIRED for the insights pair that proves
        # a file-level answer is wrong in both directions.
        inner: dict[str, int] = {}
        named_cost: str | None = None
        block: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                block.append(stripped)
                continue
            hit = A_INNER.match(line)
            if hit:
                nearby = "\n".join(block)
                if LOCAL.search(nearby):
                    pass                       # answered: rows inside one call, nothing to multiply
                elif (m2 := PAIRED.search(nearby)):
                    inner[hit.group(1)] = int(hit.group(2))
                    named_cost = m2.group(1) or named_cost
                else:
                    unpaired.append(f"{svc}: {hit.group(1)}={hit.group(2)}")
            block = []
        outer = {k: int(v) for k, v in A_OUTER.findall(text)}
        if not inner and not outer:
            continue
        # THE COST THE DECLARATION NAMED, or the smallest declared — the conservative guess, which
        # is not the same as the right one, so a bound that knows its own cost says so.
        pk = named_cost if named_cost in timeouts else min(timeouts, key=lambda k: timeouts[k])

        # A BOUND ALONE IS NOT AN ARGUMENT. Multiplying it by the smallest declared timeout only
        # says anything if ONE UNIT REALLY COSTS THAT — true of the reminders tick, where each row
        # is a live send, and false of `loyalty`'s expiry sweep, which reads five hundred rows from
        # its own store and calls nobody. Widening the vocabulary without checking this produced
        # three findings in one run, one of them provably wrong.
        #
        # So the pairing is DECLARED in the values file beside the bound, and an undeclared bound
        # is reported below rather than multiplied. Reported, not ignored: it was invisible before,
        # which is how `insights` carried a 5000-row bound this gate called comfortable.
        units = sum(inner.values()) if inner else 1
        slice_worst = timeouts[pk] * units
        judged += 1
        if slice_worst > caller:
            shape = " x ".join(f"{k}={v}" for k, v in sorted(inner.items()))
            if CEILING.search(text):
                escalate.append(f"{svc}: {units} units x {timeouts[pk]}s = {slice_worst}s "
                                f"({shape}, {pk}={timeouts[pk]})")
            else:
                over.append(f"{svc}: one tenant is {units} units x {timeouts[pk]}s = "
                            f"{slice_worst}s, caller waits {caller}s\n      ({shape}, "
                            f"{pk}={timeouts[pk]})")

        tenants = 1
        for v in outer.values():
            tenants *= v
        if tenants > 1 and slice_worst * tenants > caller:
            shape = " x ".join(f"{k}={v}" for k, v in sorted({**outer, **inner}.items()))
            escalate.append(f"{svc}: {tenants} tenants x {units} x {timeouts[pk]}s = "
                            f"{slice_worst * tenants}s ({shape}, {pk}={timeouts[pk]})")

    # PRINTED WHETHER OR NOT THIS GATE FAILS. It is the bigger number and it is not ours to fix;
    # attaching it to a red mark we could never clear would have taught people to skip both.
    if escalate:
        print("STANDING ESCALATION — these runs cannot fit in any case, at any batch size:")
        for line in escalate:
            print("  " + line)
        print(f"  the caller waits {caller}s: platform/deploy/chart/templates/cronjob.yaml, which")
        print("  this repository does not edit. Raise it there, or make the route answer")
        print("  immediately and report through its own runs endpoint. Tracked in #340.\n")

    if over:
        print(f"{len(over)} of {judged} scheduled run(s) give ONE tenant more than the whole "
              f"window:")
        for line in over:
            print("  " + line)
        print(f"\nWith a {caller}s guillotine the question is no longer «does it finish» but «who is")
        print("served before it falls». A slice this size lets the first establishment consume the")
        print("entire window, and every shop behind it waits for the next tick — every tick.")
        return 1

    if unpaired:
        print()
        print(f"{len(unpaired)} run(s) declare a bound whose per-unit cost is NOT declared:")
        for line in unpaired:
            print("  " + line)
        print("  Read the run and say what one unit costs. If it is a remote call, write")
        print("  `each-unit-is-a-remote-call` beside the bound and this gate will judge it; if it")
        print("  is a local read, say so there. Neither is assumed here.")

    print()
    print(f"{judged} scheduled run(s): no tenant's slice exceeds the caller's {caller}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
