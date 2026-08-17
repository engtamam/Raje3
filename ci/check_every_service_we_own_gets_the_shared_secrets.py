"""The script that mints our shared secrets must mint them for every service we own.

WHAT THE LIST DECIDES. `deploy/mint-our-secrets.sh` writes each of our services a `-secrets` object
carrying `PII_SALT`, `INTERNAL_SERVICE_TOKEN`, the datastore DSN and the object-store credentials.
The services it loops over are named in a hand-written string. A service missing from that string is
not refused and not reported: it is simply never minted, and it fails at a distance —

  * with no `INTERNAL_SERVICE_TOKEN` it cannot call a peer, so its half of the product is dead;
  * with no `PII_SALT` — or, worse, a DIFFERENT one — it computes a different `subject_ref` for the
    same person. Nothing crashes. The customer becomes TWO PEOPLE across the fleet, and the first
    place that surfaces is an erasure that reports success over rows it never matched. That is
    exactly the د-2 failure this repository has already paid for once, arriving by a second road.

WHY A GATE AND NOT A CAREFUL READER. The list is a transcription of a fact the filesystem already
holds — `services/*/` — and a transcription drifts the day the thing it copies moves. That is not
hypothetical here: the sibling table in `verify-fleet.sh` drifted within a day of being written,
and the only reason this one has not is that no seventh service has been added yet. The gate is
what makes the seventh service safe, and it is worth having before rather than after.

SCOPED BY WHAT THE SCRIPT DECLARES, NOT BY ITS NAME. The minting script is found by looking for the
one that declares the SHARED secret names, so renaming or moving the file keeps it in scope while a
gate holding a path would quietly stop checking anything.

AND NOT EVERY LIST OF SERVICES IS THIS ONE. `pre-deploy.sh` names five of the six deliberately —
portal's datastore is `memory`, so it has no database to provision, and `check_deploy_wiring.py`
already holds that list to its own (different) rule. A gate that demanded every list name every
service would be wrong about that one, which is why this asks only about the list whose meaning is
«every service we own».
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVICES = ROOT / "services"
DEPLOY = ROOT / "deploy"

#: The declaration that identifies the minting script: the shared secret names it distributes.
SHARED = re.compile(r'^\s*SHARED="([^"]+)"', re.M)

#: A shell string listing service names, in the same file.
LIST = re.compile(r'^\s*([A-Za-z_][A-Za-z0-9_]*)="([a-z0-9 _-]+)"\s*$', re.M)


def main() -> int:
    if not SERVICES.is_dir() or not DEPLOY.is_dir():
        print("services/ or deploy/ is missing — this gate cannot answer, so it refuses to")
        return 1

    ours = {p.name for p in SERVICES.iterdir() if p.is_dir() and (p / "app").is_dir()}
    if not ours:
        # SILENCE IS NOT AGREEMENT.
        print("no services found under services/*/app — this gate needs re-pointing")
        return 1

    minters = []
    for path in sorted(DEPLOY.rglob("*.sh")):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"cannot read {path.relative_to(ROOT).as_posix()}: {exc} — so it was NOT checked")
            return 1
        if SHARED.search(text):
            minters.append((path, text))

    if not minters:
        print("no script declares SHARED secrets — either the minting moved or this gate is "
              "reading for a shape that changed. It will not assume the fleet is fine.")
        return 1

    bad: list[str] = []
    checked = 0
    for path, text in minters:
        rel = path.relative_to(ROOT).as_posix()
        # The list of recipients: the assignment in this file that names services and nothing else.
        lists = [(name, set(val.split())) for name, val in LIST.findall(text)
                 if set(val.split()) & ours]
        if not lists:
            bad.append(f"{rel}: mints shared secrets but names no service — nobody receives them")
            continue
        for name, named in lists:
            checked += 1
            missing = ours - named
            extra = named - ours
            if missing:
                bad.append(f"{rel}: {name} omits {' '.join(sorted(missing))} — that service is "
                           f"never minted, and boots without PII_SALT")
            if extra:
                bad.append(f"{rel}: {name} names {' '.join(sorted(extra))}, which is not a service "
                           f"in this repository")

    if bad:
        print(f"{len(bad)} problem(s) with the services that receive our shared secrets:")
        for line in bad:
            print("  " + line)
        print("\nA service missing here is not refused and not reported. It boots with a different")
        print("PII_SALT, computes a different pseudonym for the same person, and the customer")
        print("becomes two people — surfacing at an erasure that reports success over nothing.")
        return 1

    print(f"{checked} shared-secret recipient list(s): every one names all {len(ours)} services")
    return 0


if __name__ == "__main__":
    sys.exit(main())
