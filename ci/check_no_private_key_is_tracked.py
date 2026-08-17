"""No private key may be tracked by git (ج2-أ).

WHAT HAPPENED. `pilot.pem` — the SSH key to the pilot server — was committed and pushed. The
repository is private, so the exposure is bounded by who can read it; but a key that has been in a
history cannot be un-shared, and deleting the file today does not remove it from the commit that
carries it. The containment is ROTATION on the server. This gate is only the second half: making
sure the next one never gets in.

WHY A GATE RATHER THAN `.gitignore` ALONE. An ignore rule is advice — `git add -f` walks straight
past it, and the file that gets forced in is precisely the one somebody was in a hurry about. This
reads what git ACTUALLY TRACKS, which is the only fact that matters.

BY CONTENT, NOT BY NAME. A key renamed `pilot.txt` is still a key; the PEM header is the thing that
cannot be disguised. The extension list is kept as well, so an unreadable or binary key is still
caught by its name.

No exceptions table. There is no such thing as a private key this repository ought to carry.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

# ASSEMBLED, NOT WRITTEN OUT. A gate that spells the header it hunts for is a file that trips
# itself — which it did on the first run, and it was right to: it must judge every tracked file by
# the same rule, with no name of its own on an exceptions list.
_HEAD = "-----" + "BEGIN "
# `ENCRYPTED` WAS MISSING, AND THAT IS THE ONE PEOPLE FEEL SAFE COMMITTING. A passphrase-protected
# key reads as «it is encrypted, so it is fine» — but the passphrase is guessable, crackable
# offline at leisure, and usually written in the same runbook as the key. It is a private key and
# it is banned like the rest.
MARKERS = tuple(_HEAD + kind + " PRIVATE KEY"
                for kind in ("RSA", "OPENSSH", "EC", "DSA", "PGP", "ENCRYPTED")) \
    + (_HEAD + "PRIVATE KEY",)
SUFFIXES = (".pem", ".key", ".p12", ".pfx")
NAMES = ("id_rsa", "id_ed25519", "id_ecdsa", "id_dsa")


def main() -> int:
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, text=True,
                             check=True).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        # NOT A PASS. A gate that cannot read the index has not checked anything.
        print(f"could not list tracked files: {exc}")
        return 1

    bad = []
    for name in out.split("\0"):
        if not name:
            continue
        path = ROOT / name
        # A public key is not a secret, and `.pub` next to a private one is the normal shape.
        if name.endswith(".pub"):
            continue
        if path.suffix.lower() in SUFFIXES or path.name in NAMES:
            bad.append(f"{name} · a private-key filename")
            continue
        # THE WHOLE FILE, NOT ITS FIRST 4KB. The window was an optimisation against a claim that
        # does not survive it: a key appended to the end of a long config, a .env, or a notes file
        # sits past byte 4096 and this gate declared the repository clean. Nothing about «is a
        # private key tracked» is answerable from a prefix, and the file this gate exists because
        # of — `pilot.pem` — was only ever caught by its NAME.
        # A GITLINK IS NOT A FILE. `git ls-files` lists a submodule (`platform`) as one entry whose
        # content is a commit id, not bytes — so opening it raises, and that raise is not a finding.
        # It is skipped BY KIND rather than by name, which is why there is still no exceptions
        # table: any submodule is handled, and a file called `platform` would not be.
        if path.is_dir():
            continue
        try:
            body = path.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            # AND A FILE IT COULD NOT OPEN IS A FILE IT DID NOT CHECK. `continue` here turned an
            # unreadable file into a clean one, silently, in the gate whose entire output is the
            # sentence «no private key is tracked».
            bad.append(f"{name} · could not be read ({exc}) — so it was NOT checked")
            continue
        for marker in MARKERS:
            if marker in body:
                bad.append(f"{name} · carries «{marker}»")
                break

    if bad:
        print("A PRIVATE KEY IS TRACKED BY GIT:")
        for line in bad:
            print("  " + line)
        print("\nRemove it from the index (`git rm --cached <file>`), keep it out with .gitignore,")
        print("and ROTATE it — a key that reached a history is a key that must be replaced.")
        return 1
    print("no private key is tracked")
    return 0


if __name__ == "__main__":
    sys.exit(main())
