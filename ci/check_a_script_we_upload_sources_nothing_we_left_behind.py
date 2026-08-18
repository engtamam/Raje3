"""A script we upload to the server must not source a file we did not upload with it.

WHAT THIS WAS WRITTEN AFTER, AND IT HAD NEVER WORKED. `ship.sh` rolls the cluster by uploading a
small bundle — the service's values file, `deploy/hooks`, `deploy/server`, the chart — and running
`deploy/server/update.sh` inside it. That script's first executable line is

    . "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../cluster.sh"

and `deploy/cluster.sh` was not in the bundle. So every roll died on line 48 with

    /root/raje3/deploy/server/../cluster.sh: No such file or directory

before it rolled anything at all. Six services were «shipped» in one run and not one of them moved.

WHY IT SURVIVED. The step printed «✔ declaration synced» first — which was true, the values file
really did arrive — and the failure that followed was one line of stderr in the middle of a long
report. `set -e` is deliberately off in `ship.sh`, so the run continued to the verify step, which
caught the mismatch and refused. The proof held; the operation under it had simply never happened.

THE RULE, AND IT NEEDS NO EXCEPTIONS TABLE. Every `.`/`source` in a file we upload must name a path
that is itself uploaded. It is a fact about two lists — what the tar carries and what the scripts
read — and neither list has an honest reason to disagree.

AND SILENCE IS NOT AGREEMENT: a run that parsed no bundle, or found no sourcing at all, has failed
to read `ship.sh` and says so rather than printing OK.

    python ci/check_a_script_we_upload_sources_nothing_we_left_behind.py
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SHIP = ROOT / "deploy/ship.sh"

#: The upload itself: `tar czf - -C "$ROOT" <path> <path> … | ssh …`. The paths between the `-C`
#: argument and the pipe are the whole bundle.
BUNDLE = re.compile(r'tar\s+czf\s+-\s+-C\s+"\$ROOT"\s+(.*?)\|', re.S)
#: `. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/<relative>"` — the one form these scripts use.
SOURCES = re.compile(r'^\s*(?:\.|source)\s+"\$\(cd\s+"\$\(dirname[^)]*\)[^)]*\)"?/([^"]+)"', re.M)

#: AND WHAT THEY RUN, NOT ONLY WHAT THEY READ. `$ROOT/deploy/sweep.sh`, invoked as `bash "$sweeper"`
#: after an `[[ -f … ]] ||  return 0` guard — the shape that made this half necessary. The guard is
#: right (a missing sweeper must not fail a rollout) and it is exactly why the absence is silent:
#: the roll reported success while the seats it was supposed to reclaim stayed booked, and the
#: cluster went on refusing to schedule. A file we RUN is as much a dependency as one we READ.
RUNS = re.compile(r'"?\$(?:\{)?ROOT(?:\})?/([A-Za-z0-9_./-]+\.sh)"?')


def bundle_paths() -> list[str]:
    text = SHIP.read_text(encoding="utf-8")
    found: list[str] = []
    for chunk in BUNDLE.findall(text):
        for raw in chunk.split():
            token = raw.strip().strip('"').strip("\\")
            # `$svc` and friends stand for one file inside a directory we already list.
            if not token or token.startswith("-") or "$" in token:
                continue
            found.append(token)
    return found


def carried(path: pathlib.Path, bundle: list[str]) -> bool:
    rel = path.relative_to(ROOT).as_posix()
    return any(rel == b or rel.startswith(b.rstrip("/") + "/") for b in bundle)


def main() -> int:
    if not SHIP.is_file():
        print(f"FAIL: {SHIP} is missing — this gate read nothing")
        return 1
    bundle = bundle_paths()
    if not bundle:
        print("FAIL: no upload found in deploy/ship.sh — the gate could not read the bundle, "
              "and silence is not agreement")
        return 1

    read_count, guilty = 0, []
    for entry in bundle:
        base = ROOT / entry
        files = [base] if base.is_file() else sorted(base.rglob("*.sh")) if base.is_dir() else []
        for f in files:
            text = f.read_text(encoding="utf-8")
            # Sourced: relative to the script's own directory. Run: relative to the repo root the
            # script computed for itself. Two spellings, one question — is it in the bundle?
            wanted = [((f.parent / t).resolve(), "sources") for t in SOURCES.findall(text)]
            wanted += [((ROOT / t).resolve(), "runs") for t in RUNS.findall(text)]
            for resolved, verb in wanted:
                read_count += 1
                if not carried(resolved, bundle):
                    guilty.append((f.relative_to(ROOT).as_posix(), verb,
                                   resolved.relative_to(ROOT).as_posix()))
    if not read_count:
        print("FAIL: no uploaded script sources or runs anything — the gate read nothing")
        return 1
    for script, verb, missing in guilty:
        consequence = ("the roll dies before it rolls" if verb == "sources"
                       else "the step is skipped in silence and the run reports success anyway")
        print(f"FAIL: {script} {verb} {missing}, and the bundle does not carry it — {consequence}")
    if guilty:
        print("\nAdd the file to the tar list in deploy/ship.sh — do not exempt it here.")
        return 1
    print(f"{read_count} dependency line(s) across the uploaded bundle, every one of them carried")
    return 0


if __name__ == "__main__":
    sys.exit(main())
