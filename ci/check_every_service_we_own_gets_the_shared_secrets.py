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

#: A service minted by its OWN hardcoded block rather than through one of the named lists above —
#: written down with the reason, same idiom as every other "found, judged, and it's fine" allow-list
#: in this repository (NOT_FOR_A_SCREEN, SOLD_UNBUILT, FROM_A_PEER). Checked by literal string
#: presence in the minting script, not by parsing its shell — this file does not need to.
HANDLED_SEPARATELY: dict[str, str] = {
    "secrets-admin": "has no database and holds no pseudonym — it gets its own two-value block "
                     "(INTERNAL_SERVICE_TOKEN, TOKEN_PUBLIC_KEY only), never PII_SALT/DATASTORE_DSN "
                     "it has no use for; see mint-our-secrets.sh's own comment on why lumping it "
                     "into a list built for a service WITH a database would be wrong, not just "
                     "differently-shaped",
}


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
    for path, text in minters:
        rel = path.relative_to(ROOT).as_posix()
        # THE UNION, NOT EACH LIST ALONE. What this gate's own docstring actually asks — "every
        # service we own gets minted somewhere in this file" — is a coverage question, not a demand
        # that any ONE list be complete by itself. A script legitimately splits provisioning into
        # complementary phases (a full create-then-patch loop for services with their own database,
        # a patch-only loop for two whose secret and DSN gen-secrets.py already owns) — checking
        # each list for 100% coverage would fail the very design that keeps a shared value from
        # ever clobbering a DSN it must not touch.
        lists = [(name, set(val.split())) for name, val in LIST.findall(text)
                 if set(val.split()) & ours]
        if not lists and not any(f"{svc}-secrets" in text for svc in HANDLED_SEPARATELY):
            bad.append(f"{rel}: mints shared secrets but names no service — nobody receives them")
            continue

        named_union: set[str] = set()
        for name, named in lists:
            named_union |= named
            extra = named - ours
            if extra:
                bad.append(f"{rel}: {name} names {' '.join(sorted(extra))}, which is not a service "
                           f"in this repository")

        # A service this file's own comments say is handled by a hardcoded block rather than one of
        # the named lists — credited only if that block is genuinely present (the literal secret
        # name it creates/patches), never assumed from the allow-list entry alone.
        for svc, _reason in HANDLED_SEPARATELY.items():
            if f"{svc}-secrets" in text:
                named_union.add(svc)

        missing = ours - named_union
        if missing:
            bad.append(f"{rel}: no list (and no documented separate block) covers "
                       f"{' '.join(sorted(missing))} — that service is never minted, and boots "
                       f"without PII_SALT")

    if bad:
        print(f"{len(bad)} problem(s) with the services that receive our shared secrets:")
        for line in bad:
            print("  " + line)
        print("\nA service missing here is not refused and not reported. It boots with a different")
        print("PII_SALT, computes a different pseudonym for the same person, and the customer")
        print("becomes two people — surfacing at an erasure that reports success over nothing.")
        return 1

    print(f"every one of {len(ours)} services is minted somewhere — by a named list or a "
         f"documented separate block")
    return 0


if __name__ == "__main__":
    sys.exit(main())
