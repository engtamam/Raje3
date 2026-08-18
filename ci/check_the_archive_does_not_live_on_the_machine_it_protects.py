"""The archive must not live on the machine it is protecting.

WHAT IS TRUE TODAY, MEASURED RATHER THAN FEARED. One node. One disk. `postgres-data` and
`objectstore-data` are both bound to it, and `backup-service` writes its archives to
`http://objectstore:9000` — the same in-cluster store every other service uses. So the shop's data
and the copy taken to survive losing that data sit on one piece of hardware. Losing the node loses
both at the same instant, with the nightly run reporting success until the moment it cannot.

THAT IS NOT A BACKUP. It protects against the second-likeliest failure — a bad write, a wrong
migration, a deletion — and against nothing at all in the case the word «backup» exists for.

WHY A CHECK AND NOT A NOTE. Nothing anywhere said this. The values file names an endpoint, the
runs go green, the retention policy is thoughtful, and every piece of evidence a reader meets says
the archives are handled well. The one fact that decides whether they are worth anything — WHERE
THEY PHYSICALLY ARE — was written nowhere and asked by nobody.

THE RULE, AND IT HAS NO EXCEPTIONS TABLE: `backup-service` must not send its archives to a host
this deployment runs itself.

AND THE FIRST DRAFT OF THIS CHECK PASSED, WRONGLY. It read the in-fleet names from
`deploy/services/*.values.yaml` and `objectstore` is not among them — it is a datastore, declared
in the network policy rather than as a service values file. So the check compared the destination
against a list that could never contain it and printed ok over the exact arrangement it exists to
refuse. The names now come from `deploy/k3s/datastores-netpol.yaml`, which is where this
deployment declares what it runs for itself, plus the service values files. A guard whose evidence
cannot contain the answer is the defect this project keeps finding in its own guards.

WHAT CLOSES IT: an endpoint outside the fleet — object storage from the provider, in the same
region for residency and latency. `OBJECTSTORE_DRIVER` is already `s3`; only the destination
changes, and no code moves.

WHAT THIS CHECK CANNOT SEE: whether the external destination shares a failure domain with the node
— a bucket in the same datacentre survives a lost disk but not a lost datacentre. That is a
decision about how much loss is acceptable, and it belongs to whoever pays for it.
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy"
SERVICES = DEPLOY / "services"
NETPOL = DEPLOY / "k3s" / "datastores-netpol.yaml"
BACKUP = SERVICES / "backup-service.values.yaml"

ENDPOINT = re.compile(r'^\s*OBJECTSTORE_ENDPOINT_URL:\s*"?([^"\n]*)"?\s*$', re.M)
HOST = re.compile(r'^\w+://([^:/]+)')
ROLE = re.compile(r'^\s*base-services/role:\s*(\S+)\s*$', re.M)


def in_fleet_hosts() -> set[str]:
    """Every name this deployment serves for itself — read, never listed here.

    TWO SOURCES BECAUSE THERE ARE TWO KINDS. The services have values files; the datastores they
    depend on are declared by the network policy that isolates them, and `objectstore` is one of
    those. Reading only the first is what made the first draft of this check pass over the very
    arrangement it refuses.
    """
    hosts = {p.name[: -len(".values.yaml")] for p in SERVICES.glob("*.values.yaml")}
    if NETPOL.exists():
        text = NETPOL.read_text(encoding="utf-8")
        hosts |= set(ROLE.findall(text))
        # The roles are `datastore` and `objectstore`; the SERVICE names they cover are named in
        # the same file's prose and policy names. Take both, so a rename on either side is caught.
        hosts |= set(re.findall(r"`(postgres|redis|objectstore)`", text))
        hosts |= {m.split("-")[0] for m in re.findall(r"^\s*name:\s*(\S+)$", text, re.M)}
    return {h for h in hosts if h}


def main() -> int:
    if not BACKUP.exists():
        print("  \033[31m✗ backup-service.values.yaml is missing — this check lost its subject\033[0m")
        return 1
    hosts = in_fleet_hosts()
    if not NETPOL.exists():
        print("  \033[31m✗ datastores-netpol.yaml is missing — the list of what this deployment "
              "runs for itself cannot be read\033[0m")
        return 1
    if not hosts:
        print("  \033[31m✗ read no in-fleet hosts at all — this check no longer knows where to "
              "look\033[0m")
        return 1

    found = ENDPOINT.findall(BACKUP.read_text(encoding="utf-8"))
    if not found:
        print("  \033[31m✗ backup-service declares no OBJECTSTORE_ENDPOINT_URL — the archive has "
              "no stated destination at all\033[0m")
        return 1

    endpoint = found[-1].strip()
    m = HOST.match(endpoint)
    host = m.group(1) if m else endpoint

    if host in hosts or host in {"localhost", "127.0.0.1"}:
        print(f"  \033[31m✗ the archive is written to «{endpoint}» — a host this deployment runs "
              f"itself\033[0m")
        print("\nThe data and the copy taken to survive losing the data are then on one machine. "
              "Losing it loses both at the same instant, and the nightly run reports success "
              "until the moment it cannot. Point OBJECTSTORE_ENDPOINT_URL at storage outside the "
              "fleet — the driver is already `s3`, only the destination changes.")
        return 1

    # THE NAME THAT IS PRINTED IS THE NAME THAT IS REFUSED, and `check_a_check_that_found_nothing_
    # says_so` caught the first version of this line for exactly that: it reported `len(hosts)`
    # while the emptiness guard above tested `hosts`, so a reader — and that check — could not tell
    # the count came from a set anything had verified was non-empty.
    known = len(hosts)
    if not known:
        print("  [31m✗ read no in-fleet hosts at all — this check no longer knows where to "
              "look[0m")
        return 1
    print(f"ok the archive goes to «{host}», which is not among the {known} hosts this "
          f"deployment runs itself")
    return 0


if __name__ == "__main__":
    sys.exit(main())
