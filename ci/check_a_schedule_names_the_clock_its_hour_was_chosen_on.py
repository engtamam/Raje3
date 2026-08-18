#!/usr/bin/env python3
"""The fleet declares the clock its schedules are written on, and it is one clock.

Measured on the live cluster on 2026-08-18: NOT ONE of the 31 CronJobs declares a `timeZone`, and
the node keeps Asia/Shanghai. Every hour in `deploy/services/*.values.yaml` is argued for in the
life of a Saudi workshop — «nightly», «off-hour», «when no operator has a customer standing in
front of them» — and every one of them fires five hours away from that argument:

    retention sweep     17 1  ->  20:17 Riyadh, the busiest hour of a workshop's evening
    nightly archive     42 2  ->  21:42 Riyadh
    weekly digest    0 9 * * 0 -> 04:00 Riyadh, a WhatsApp message to an owner before dawn

A value reasoned about and then dropped: the hour was chosen with care, written down in prose, and
read by nothing.

ONE DECLARATION FOR THE FLEET, in deploy/fleet-clock.env. Not one per values file — that is an
exceptions table wearing a different hat, and it invites the worse failure of half a fleet on one
clock and half on another. It also cannot live in the values files at all: the chart's schema
refuses keys it does not render, so `cronTimeZone:` there breaks every deploy instead of sitting
quietly. (That is how this shape was found — `check_every_values_file_renders_against_the_chart`
caught the first attempt.)

THIS DOES NOT MOVE ANY SCHEDULE. The chart renders a bare `schedule` with no `timeZone`
(platform/deploy/chart/templates/cronjob.yaml, read-only to us; escalated with #321). Until that
ships, the declaration is what `verify-fleet.sh` compares against the cluster's real clock so the
drift is named on every deploy. Saying that plainly is the point: a check that implied it had
ALIGNED the clocks would be the same defect wearing the fix's clothes.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLOCK = ROOT / "deploy" / "fleet-clock.env"


def main():
    scheduling = [f.name for f in sorted((ROOT / "deploy" / "services").glob("*.values.yaml"))
                  if re.search(r"^cronJobs:", f.read_text(encoding="utf-8"), re.M)]

    # ZERO IS A FAILURE, NOT A PASS. If the values files move or are renamed this check would
    # otherwise find nothing, print a cheerful line, and guard a rule with no subject left.
    if not scheduling:
        print("x no deploy values file declares cronJobs — this check found NOTHING to check and "
              "will not report success", file=sys.stderr)
        return 1

    if not CLOCK.exists():
        print(f"x {len(scheduling)} file(s) schedule work and deploy/fleet-clock.env does not exist —\n"
              f"      every one of those hours is decided by whatever zone the node happens to keep",
              file=sys.stderr)
        return 1

    zones = re.findall(r"^CRON_TIMEZONE=([A-Za-z_]+/[A-Za-z_]+)\s*$", CLOCK.read_text(encoding="utf-8"), re.M)
    if not zones:
        print("x deploy/fleet-clock.env names no CRON_TIMEZONE — the file exists and says nothing",
              file=sys.stderr)
        return 1
    if len(set(zones)) > 1:
        print(f"x deploy/fleet-clock.env names more than one clock: {', '.join(sorted(set(zones)))}\n"
              f"      one fleet, one zone", file=sys.stderr)
        return 1

    # AND NO VALUES FILE MAY CARRY ITS OWN. A second home for this fact is how one fleet becomes
    # two clocks, and the chart would reject it anyway — better refused here, with the reason.
    stray = [f.name for f in sorted((ROOT / "deploy" / "services").glob("*.values.yaml"))
             if "cronTimeZone" in f.read_text(encoding="utf-8")]
    if stray:
        for name in stray:
            print(f"  x {name} carries its own cronTimeZone — the fleet's clock lives in "
                  f"deploy/fleet-clock.env", file=sys.stderr)
        return 1

    print(f"ok {len(scheduling)} file(s) schedule work, all of it timed in {zones[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
