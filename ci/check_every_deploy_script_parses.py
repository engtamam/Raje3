"""Every script under deploy/ must parse — all of them, found rather than listed.

WHAT IT COST, TWICE, IN ONE WEEK. `seed-backup-targets.sh` was saved with CRLF line endings, and a
shebang followed by `\r` makes the kernel look for an interpreter called `bash\r`. The error it
prints is «bash: No such file or directory» — about bash itself — which sends whoever reads it to
check whether bash is installed. And `check-posture.sh` defined a helper named `head`, so every
`... | head -1` in the file stopped filtering and called the helper; two security reads died of it
and each printed a verdict rather than a failure. Neither was a syntax error, but both are the same
shape: nothing ever asked these files a question before a cluster did.

WHY THE EXISTING HARNESS DID NOT CATCH THEM. `ci/test_deploy_scripts.sh` exercises four scripts —
`bring-up`, `install`, `ship`, `verify-fleet` — chosen because they were the ones being changed at
the time. It is a good harness and it stays. But there are forty-seven scripts here, and the other
forty-three include `pack.sh`, `uninstall.sh`, `publish-images.sh`, all eight seeders, and the
EIGHTEEN `prove-*.sh` — the scripts by which we satisfy ourselves that the product works. A
harness naming four is a harness whose coverage is a fact about somebody's afternoon.

WHAT THIS CLAIMS, AND IT IS DELIBERATELY THE WEAKEST USEFUL ONE. That every script PARSES. Not that
it is correct, not that it is exercised — that it is a shell program at all. A syntax error in a
seeder is discovered when an installer is halfway through a fleet, and the half already changed
does not roll itself back.

DISCOVERED, NEVER ENUMERATED. The set comes from the filesystem, so a script written tomorrow is
covered the moment it is saved rather than the moment somebody remembers this file.
"""
from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEPLOY = ROOT / "deploy"


def main() -> int:
    bash = shutil.which("bash")
    if bash is None:
        # A GATE THAT CANNOT RUN MUST SAY SO. Passing here would report «every script parses» from
        # a machine that parsed none.
        print("bash is not on PATH — this gate cannot answer, so it refuses to")
        return 1
    if not DEPLOY.is_dir():
        print("no deploy/ directory — this gate cannot answer, so it refuses to")
        return 1

    scripts = sorted(DEPLOY.rglob("*.sh"))
    if not scripts:
        # SILENCE IS NOT AGREEMENT: parsing nothing is not the same as everything parsing.
        print("no deploy scripts found — this gate needs re-pointing")
        return 1

    bad: list[tuple[str, str]] = []
    for path in scripts:
        rel = path.relative_to(ROOT).as_posix()

        # A CARRIAGE RETURN IS NOT A SYNTAX ERROR, AND THAT IS WHY IT IS CHECKED SEPARATELY.
        # `bash -n` accepts a CRLF file. The kernel does not: `#!/usr/bin/env bash\r` sends it
        # looking for `bash\r`, and the failure names bash rather than the file.
        try:
            raw = path.read_bytes()
        except OSError as exc:
            bad.append((rel, f"cannot be read: {exc}"))
            continue
        if b"\r\n" in raw:
            bad.append((rel, "CRLF line endings — the shebang fails on the server with "
                             "«No such file or directory» about bash itself"))
            continue

        out = subprocess.run([bash, "-n", str(path)], capture_output=True, text=True)
        if out.returncode != 0:
            bad.append((rel, (out.stderr or "").strip().splitlines()[-1] if out.stderr
                        else f"bash -n exited {out.returncode}"))

    if bad:
        print(f"{len(bad)} deploy script(s) do not parse:")
        for rel, why in bad:
            print(f"  {rel}: {why}")
        print("\nA script that cannot parse fails when an installer is already halfway through a "
              "fleet, and the half it changed does not roll itself back.")
        return 1

    print(f"{len(scripts)} deploy scripts: every one parses, and every one has unix endings")
    return 0


if __name__ == "__main__":
    sys.exit(main())
