#!/usr/bin/env python3
"""Every scheduled route accepts the EMPTY POST its own scheduler sends.

WHAT THIS COSTS WHEN IT IS MISSING, measured on the live cluster on 2026-08-18: the nightly
`backup-service-run` had failed on three consecutive nights. The CronJob POSTs an empty body with a
JSON content type; the route declared a REQUIRED model, so FastAPI answered 422 before the handler
ran a single line. Nothing anywhere said so — the health-check cron completed green every hour, the
prune cron completed, `verify-fleet.sh` printed «backup targets: N registered», and the only record
of three unprotected nights was an exit code in a Job nobody reads. The archive is the one thing
whose whole value is being there on the day everything else is gone.

THE RULE HAS NO EXCEPTIONS TABLE. A scheduler that sends no body and a route that demands one is a
contradiction between two files in this repo, and it is decidable from those two files alone:
  - `deploy/services/<svc>.values.yaml` declares `cronJobs: [- path: /internal/...]`
  - `services/<svc>/app/api/**.py` declares the handler for that path

TWO WAYS TO FAIL, and both are red:
  1. the handler demands a body (no default, and `None` not in its annotation)
  2. the path resolves to NO handler at all — a schedule firing at a route that does not exist is
     the same silence in a different costume, and a check that shrugs at what it cannot find is the
     defect family this gate exists to end.

PLATFORM SERVICES ARE CHECKED TOO, from the vendored source under `platform/`. They are the ones
this actually happened to, and leaving them out would have made this gate a monument to a failure it
could not see. `platform/` is read-only, so a finding there is an escalation and a version pin, not
an edit — which is exactly how it was closed: v0.16.19 carries the fix.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def cron_paths():
    """(service, path) for every cronJob declared in a deploy values file."""
    out = []
    for f in sorted((ROOT / "deploy" / "services").glob("*.values.yaml")):
        txt = f.read_text(encoding="utf-8")
        if "cronJobs:" not in txt:
            continue
        for m in re.finditer(r"^\s*path:\s*(\S+)", txt.split("cronJobs:", 1)[1], re.M):
            out.append((f.name.split(".")[0], m.group(1)))
    return out


def body_param(service, route):
    """The `body` parameter of the POST handler for `route`, or None if no handler is found.

    Returns ("", ...) for a handler that takes no body at all, which is trivially empty-POST-safe.
    """
    roots = [ROOT / "services" / service / "app" / "api",
             ROOT / "platform" / "services" / service / "app" / "api"]
    for f in sorted(f for r in roots if r.is_dir() for f in r.rglob("*.py")):
        src = f.read_text(encoding="utf-8")
        # The decorator carries a `dependencies=[...]` list, so scan to the `def` rather than to
        # the first `)`. An earlier draft of this gate stopped at that paren and found NOTHING,
        # then reported success — the shape it is here to forbid.
        m = re.search(r'@router\.post\(\s*"' + re.escape(route) + r'"[\s\S]*?\n(?:async )?def \w+\(([\s\S]*?)\)\s*->', src)
        if not m:
            continue
        sig = " ".join(m.group(1).split())
        b = re.search(r"\bbody\s*:\s*([^,=]+?)(?:\s*=\s*([^,]+))?(?:,|$)", sig)
        return ("", "", f) if not b else (b.group(1).strip(), (b.group(2) or "").strip(), f)
    return None


def main():
    prefix = "/internal"
    ours, bad = [], []
    for service, path in cron_paths():
        ours.append((service, path))
        found = body_param(service, path[len(prefix):] if path.startswith(prefix) else path)
        if found is None:
            bad.append((service, path, "no POST handler declares this route"))
            continue
        ann, default, _ = found
        if ann and not default and "None" not in ann:
            bad.append((service, path, f"body: {ann} is REQUIRED — the empty POST is answered 422"))

    for service, path, why in bad:
        print(f"  x {service:12} {path}\n      {why}", file=sys.stderr)
    if bad:
        print(f"\n{len(bad)} scheduled route(s) refuse the empty POST their own scheduler sends.",
              file=sys.stderr)
        print("A cron-driven route must accept `body: Model | None = None`.", file=sys.stderr)
        return 1

    # THE SUBJECT IS PRINTED, AND ZERO OF IT IS A FAILURE. A gate that scanned nothing and said
    # «all clear» is the defect this repo keeps finding; `checked` is what makes the sentence true.
    checked = len(ours)
    if not checked:
        print("x no scheduled routes were found in deploy/services/*.values.yaml — this gate "
              "checked NOTHING and will not report success", file=sys.stderr)
        return 1
    print(f"ok {checked} scheduled route(s) accept the empty POST their scheduler sends")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
