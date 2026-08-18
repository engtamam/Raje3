#!/usr/bin/env python3
"""Every schedule this fleet ships carries the clock its hour was chosen on.

Measured on the live cluster on 2026-08-18: not one of the 31 CronJobs declared a `timeZone` and the
node kept Asia/Shanghai, so every hour argued for in the life of a Saudi workshop fired five hours
away from that argument — the retention sweep documented as running «when no operator has a customer
standing in front of them» at 20:17 Riyadh, and the weekly digest written for 09:00 at 04:00, a
WhatsApp message to an owner before dawn. A value reasoned about carefully, written down in prose,
and read by nothing.

THAT WAS ESCALATED AND ANSWERED. platform v0.16.20 renders `spec.timeZone` from a deployment-wide
`timeZone` (chart default Asia/Riyadh) and REFUSES an unknown zone at template time. So the question
this gate asks changed with it, and got stronger: it used to check that a file existed and agreed
with itself, because nothing could carry the zone anywhere. Now it RENDERS the chart and reads what
each CronJob would actually ship with.

WHAT IS COMPARED. `deploy/fleet-clock.env` is where we say which clock our hours are written on;
the rendered manifests are what the cluster is asked to keep. Those two being equal is the whole
property — a declaration nothing renders is a receipt for a change that never happened, and a
rendered zone nobody declared is the node's accident wearing a value's clothes.

NO EXCEPTIONS TABLE. Every CronJob in every values file that declares one, or the gate fails naming
the job. A schedule that opts out with `timeZone: ""` renders no field at all, and would be caught
here — deliberately: on THIS fleet, «follow the node» is the defect, so choosing it must be argued
in front of somebody rather than passed silently.
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHART = ROOT / "platform" / "deploy" / "chart"
CLOCK = ROOT / "deploy" / "fleet-clock.env"


def declared_zone():
    if not CLOCK.exists():
        return None, "deploy/fleet-clock.env does not exist — the fleet declares no clock"
    zones = re.findall(r"^CRON_TIMEZONE=([A-Za-z_]+/[A-Za-z_]+)\s*$", CLOCK.read_text(encoding="utf-8"), re.M)
    if not zones:
        return None, "deploy/fleet-clock.env names no CRON_TIMEZONE — the file exists and says nothing"
    if len(set(zones)) > 1:
        return None, f"deploy/fleet-clock.env names more than one clock: {', '.join(sorted(set(zones)))}"
    return zones[0], ""


def rendered_cronjobs(helm, values):
    """(name, timeZone) for every CronJob the chart renders from this values file."""
    out = subprocess.run([helm, "template", values.name.split(".")[0], str(CHART), "-f", str(values)],
                         capture_output=True, text=True)
    if out.returncode != 0:
        return None
    jobs, name, kind = [], "", ""
    for line in out.stdout.splitlines():
        if line.startswith("kind:"):
            kind = line.split(":", 1)[1].strip()
        elif line.startswith("  name:") and kind == "CronJob" and not name:
            name = line.split(":", 1)[1].strip()
        elif line.startswith("  timeZone:") and kind == "CronJob":
            jobs.append((name, line.split(":", 1)[1].strip().strip('"')))
            name, kind = "", ""
        elif line.startswith("---"):
            if kind == "CronJob" and name:
                jobs.append((name, ""))
            name, kind = "", ""
    if kind == "CronJob" and name:
        jobs.append((name, ""))
    return jobs


def main():
    want, why = declared_zone()
    if want is None:
        print(f"x {why}", file=sys.stderr)
        return 1

    helm = shutil.which("helm")
    if helm is None:
        print("x helm is not on PATH — what the fleet would actually ship cannot be read, so this "
              "gate refuses to report success", file=sys.stderr)
        return 1
    if not CHART.is_dir():
        print(f"x no chart at {CHART.relative_to(ROOT).as_posix()} — the submodule is not checked out",
              file=sys.stderr)
        return 1

    checked, bad = 0, []
    for f in sorted((ROOT / "deploy" / "services").glob("*.values.yaml")):
        if not re.search(r"^cronJobs:", f.read_text(encoding="utf-8"), re.M):
            continue
        jobs = rendered_cronjobs(helm, f)
        if jobs is None:
            bad.append((f.name, "", "does not render at all"))
            continue
        if not jobs:
            bad.append((f.name, "", "declares cronJobs and renders none"))
            continue
        for name, got in jobs:
            checked += 1
            if got != want:
                bad.append((f.name, name,
                            f"ships timeZone {got or '(none — the node decides)'}, "
                            f"and this fleet's hours are written on {want}"))

    for values, job, why in bad:
        where = f"{values} · {job}" if job else values
        print(f"  x {where}\n      {why}", file=sys.stderr)
    if bad:
        print(f"\n{len(bad)} scheduled job(s) do not ship the clock their hours were chosen on.",
              file=sys.stderr)
        return 1

    # ZERO IS A FAILURE. If the values files are renamed or the chart stops rendering CronJobs, this
    # would otherwise find nothing, print a cheerful line, and guard a rule with no subject left.
    if not checked:
        print("x no CronJob rendered from any values file — this gate checked NOTHING and will not "
              "report success", file=sys.stderr)
        return 1
    print(f"ok {checked} scheduled job(s) ship timeZone {want}, the clock their hours are written on")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
