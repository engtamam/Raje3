#!/usr/bin/env python3
"""THE PLATFORM RELEASE IN `platform/` AND THE ONE IN THE VALUES FILES ARE ONE NUMBER, OR NEITHER
IS TRUE.

WHAT THIS FOUND, AND IT HAD BEEN TRUE FOR TEN RELEASES.

The submodule sat at v0.16.14. Seventeen of the twenty platform values files pinned digests
labelled v0.16.4. Both facts were committed, both were visible, and nothing anywhere compared them.

Every check we own passed while that was true, and each of them was right to. `verify-fleet.sh`
asks «is the cluster running what the repository pins» — it was, exactly. `verify-pinned.sh` asks
the same of the server's own copies. `repin-platform.sh --check` asks it of a tag you hand it, so
it only ever answers the question you already knew to ask. Not one of them asks the question that
matters: IS WHAT THE REPOSITORY PINS THE PLATFORM THE REPOSITORY CONTAINS?

THE COST WAS NOT THEORETICAL. `deploy/seed/seed-backup-targets.sh` registers every service with
backup-service through `PUT /api/v1/backup/targets`, a route that arrived after v0.16.4. The pin
said v0.16.4, so the cluster ran v0.16.4, so all twenty registrations answered 404 — and the fleet
had ZERO backup targets while every green tick in the repository agreed it was healthy. We read
the platform source to write that script: the route is there, in `platform/`, in this tree. It was
simply never the code we were running.

That is the shape: a value read from one place and pinned in another, with no line of code holding
the two together. It does not decay loudly. It decays by staying exactly as correct as it was on
the day it was written.

THE RULE, AND IT HAS NO EXCEPTIONS TABLE. Every values file pinning a platform image must label
its digest with the release the submodule is checked out at. Not «a recent one», not «one of the
approved set» — that one.

WHAT IS A PLATFORM IMAGE, AND WHY THE PATH DEPTH DECIDES. Theirs are `ghcr.io/OWNER/<image>`;
ours are `ghcr.io/OWNER/raje3/<image>`, published by `deploy/publish-images.sh` from this
repository's own commits and carrying a commit hash rather than a release. One slash is the whole
difference, and `repin-platform.sh` learned it the hard way — a `*` glob spans slashes, so our six
services were once looked up under the platform's release tag and the release refused as
incomplete. The same distinction is made here, the same way, for the same reason.

IF THE RELEASE CANNOT BE READ, THIS FAILS. A submodule at a commit that carries no tag is not a
release we can verify pins against, and «could not tell» must never print green — that is the
identical silence this gate exists to end.
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
VALUES = ROOT / "deploy" / "services"
SUBMODULE = ROOT / "platform"

C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"

# `  digest: "sha256:…"   # v0.16.4`  — the trailing comment is the human-readable half of the pin,
# and the only place a values file says which release its digest came from.
DIGEST = re.compile(r'^\s*digest:\s*"(?P<digest>sha256:[0-9a-f]{64})"\s*(?:#\s*(?P<note>.*?))?\s*$')
REPOSITORY = re.compile(r"^\s*repository:\s*(?P<repo>\S+)\s*$")
RELEASE = re.compile(r"\bv\d+\.\d+\.\d+\b")


def vendored_release() -> tuple[str, str]:
    """The release `platform/` is checked out at, or an explanation of why it cannot be known."""
    if not (SUBMODULE / ".git").exists():
        return "", ("platform/ is not a checked-out submodule — run `git submodule update --init`")
    try:
        out = subprocess.run(
            ["git", "-C", str(SUBMODULE), "describe", "--tags", "--exact-match", "HEAD"],
            capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        return "", f"could not run git against platform/ — {exc}"
    tag = out.stdout.strip()
    if out.returncode != 0 or not RELEASE.fullmatch(tag):
        return "", ("platform/ is at a commit that carries no release tag "
                    f"({(out.stderr or out.stdout).strip()[:120] or 'no tag'}) — so what the "
                    "values files pin cannot be checked against anything")
    return tag, ""


def main() -> int:
    release, why_not = vendored_release()
    if not release:
        print(f"{C_R}the vendored platform release cannot be read{C_N}\n  {why_not}")
        print("\n  A pin that cannot be checked is not a pin. This does not pass by default.")
        return 1

    if not VALUES.is_dir():
        print(f"{C_R}no deploy/services — this gate checked nothing, and an empty set is not "
              f"agreement{C_N}")
        return 1

    bad: list[str] = []
    checked = 0

    for path in sorted(VALUES.glob("*.values.yaml")):
        rel = path.relative_to(ROOT).as_posix()
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError) as exc:
            bad.append(f"{rel}: cannot read it — {exc}")
            continue

        repo = next((m.group("repo") for line in lines
                     if (m := REPOSITORY.match(line))), "")
        if not repo.startswith("ghcr.io/"):
            continue
        # ghcr.io/OWNER/<image> is theirs; ghcr.io/OWNER/raje3/<image> is ours, pinned to one of
        # our commits by publish-images.sh and no business of a platform release.
        if repo.count("/") != 2:
            continue

        pin = next(((i + 1, m) for i, line in enumerate(lines)
                    if (m := DIGEST.match(line))), None)
        if pin is None:
            bad.append(f"{rel}: names a platform image and pins no digest — nothing here is "
                       f"verifiable, and a values file with no pin still renders and still runs")
            continue

        line_no, m = pin
        checked += 1
        note = (m.group("note") or "").strip()
        found = RELEASE.search(note)
        if not found:
            bad.append(
                f"{rel}:{line_no}: the digest names no release ({note or 'no comment'!r}). A bare "
                f"digest cannot be compared to the platform in this tree, which is how a pin ten "
                f"releases stale reads as deliberate")
        elif found.group(0) != release:
            bad.append(
                f"{rel}:{line_no}: pinned to {found.group(0)}, but platform/ is checked out at "
                f"{release}. The cluster will run {found.group(0)} and every route added since "
                f"answers 404 — while this repository's source, tests and scripts are all written "
                f"against {release}")

    if bad:
        print(f"{C_R}the platform we pin is not the platform we vendored{C_N}")
        for line in bad:
            print(f"  {line}")
        print(f"\n  GHCR_TOKEN=… bash deploy/repin-platform.sh {release}")
        return 1

    if checked == 0:
        print(f"{C_R}no platform pins found — either the images moved registry or this gate no "
              f"longer recognises them, and an empty set is not agreement{C_N}")
        return 1

    print(f"{C_G}ok{C_N}  {checked} platform pins, every one of them on {release}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
