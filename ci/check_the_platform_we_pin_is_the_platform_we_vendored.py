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

THE RULE, AND IT HAS NO EXCEPTIONS TABLE. Every values file pinning a platform image must pin the
DIGEST that the submodule's release resolves to. Not «a recent one», not «one of the approved
set» — that one.

AND IT IS THE DIGEST, NOT THE NOTE BESIDE IT. This gate spent its first life reading the trailing
`# vX` comment, which was the only release name a values file carried. That was wrong in a way
that only showed up under a real upgrade: a release rebuilds only what changed, so on the move to
v0.16.16 twelve images came back byte-identical and repin-platform.sh left their notes reading
v0.16.4. Every one of those pins was correct. This gate called all twelve drift and said the
cluster would answer 404 — about the exact images the release ships. So the authority moved to
`deploy/platform-release.json`, written by the repin at the moment it asked the registry, and a
digest is now compared to a digest. The note is still checked, and a stale one is PRINTED rather
than failed: untidy is not dangerous, and a gate that cannot tell the two apart teaches people to
ignore it.

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

import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
VALUES = ROOT / "deploy" / "services"
SUBMODULE = ROOT / "platform"
MANIFEST = ROOT / "deploy" / "platform-release.json"

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


def release_manifest() -> tuple[dict | None, str]:
    """What the last real repin resolved, image by image — the only authority on a pin.

    THIS FILE EXISTS BECAUSE A COMMENT IS NOT EVIDENCE. This gate used to read the `# vX` note
    beside each digest, and a release rebuilds only what changed: twelve images were byte-identical
    from v0.16.4 to v0.16.16, so their notes stayed at v0.16.4 while the pins were exactly right.
    The gate then announced that the cluster would run v0.16.4 and answer 404 — about the very
    images v0.16.16 ships. Twelve false accusations, and a gate that is wrong twelve times is one
    nobody reads the thirteenth time.
    """
    if not MANIFEST.is_file():
        return None, (f"{MANIFEST.name} is missing — it is written by repin-platform.sh, and "
                      f"without it there is nothing to compare a digest to")
    try:
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, f"{MANIFEST.name} cannot be parsed — {exc}"
    if not isinstance(data.get("images"), dict) or not RELEASE.fullmatch(str(data.get("release"))):
        return None, f"{MANIFEST.name} has no release and images — it is not a manifest"
    if not data["images"]:
        return None, f"{MANIFEST.name} lists no images, and an empty manifest agrees with anything"
    return data, ""


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

    manifest, why_not = release_manifest()
    if manifest is None:
        print(f"{C_R}the release manifest cannot be read{C_N}\n  {why_not}")
        print("\n  A pin that cannot be checked is not a pin. This does not pass by default.")
        return 1
    if manifest["release"] != release:
        print(f"{C_R}the manifest is not the platform we vendored{C_N}")
        print(f"  {MANIFEST.name} was written for {manifest['release']}, but platform/ is checked "
              f"out at {release}. The submodule moved and the pins were never re-resolved, so "
              f"every digest below belongs to the older release.")
        print(f"\n  GHCR_TOKEN=… bash deploy/repin-platform.sh {release}")
        return 1

    bad: list[str] = []
    stale: list[str] = []
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
        image = repo.rsplit("/", 1)[-1]
        want = manifest["images"].get(image)
        if want is None:
            bad.append(
                f"{rel}:{line_no}: {image} is not in {MANIFEST.name}, which was written by the "
                f"repin of {manifest['release']}. Either the image is new since that repin, or it "
                f"is no longer part of the release — and either way nothing here knows what it "
                f"should be pinned to")
        elif m.group("digest") != want:
            bad.append(
                f"{rel}:{line_no}: pins {m.group('digest')[:19]}…, but {release} resolved this "
                f"image to {want[:19]}…. The cluster will run code that is not the platform this "
                f"repository's source, tests and scripts are written against")

        # THE NOTE IS CHECKED, AND ITS FAILURE IS NOT THE DIGEST'S. A stale `# vX` beside a correct
        # digest is untidy, not dangerous — twelve of them once made this gate cry drift about pins
        # that were exactly right, because it judged the comment and reported the deployment. So it
        # is reported as what it is: a note to bring up to date, by name.
        note = (m.group("note") or "").strip()
        found = RELEASE.search(note)
        if not found or found.group(0) != release:
            stale.append(f"{rel}:{line_no}: note says {found.group(0) if found else 'nothing'}, "
                         f"the release is {release}")

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

    for line in stale:
        # NOT A FAILURE. The digest is right; the note beside it is behind. Said out loud so the
        # next repin tidies it, and never mixed in with a pin that would actually ship wrong code.
        print(f"  note  {line}")

    print(f"{C_G}ok{C_N}  {checked} platform pins, every digest matching what {release} resolved to"
          + (f" ({len(stale)} note(s) to tidy on the next repin)" if stale else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
