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
            for target in SOURCES.findall(f.read_text(encoding="utf-8")):
                read_count += 1
                resolved = (f.parent / target).resolve()
                if not carried(resolved, bundle):
                    guilty.append((f.relative_to(ROOT).as_posix(),
                                   resolved.relative_to(ROOT).as_posix()))
    if not read_count:
        print("FAIL: no uploaded script sources anything — the gate read nothing")
        return 1
    for script, missing in guilty:
        print(f"FAIL: {script} sources {missing}, and the bundle does not carry it — "
              f"the roll dies before it rolls")
    if guilty:
        print("\nAdd the file to the tar list in deploy/ship.sh — do not exempt it here.")
        return 1
    print(f"{read_count} source line(s) across the uploaded bundle, every one of them carried")
    return 0


if __name__ == "__main__":
    sys.exit(main())
