#!/usr/bin/env python3
"""Raje3's own first-party services — self-contained secret generation for a server install.

THE GAP THIS CLOSES. `platform/deploy/server/gen-secrets.py` mints secrets for
every BASE service (`platform/services/*`) on a fresh install. It has never known about `services/*`
at the top of THIS repo — operations, campaigns, and now affiliate-service — because its own
`SERVICES` constant is anchored two levels above ITSELF, inside the submodule
(`platform/deploy/server/gen-secrets.py` → `platform/services`), and a submodule has no business
reaching outside its own boundary to find ours. So every one of our own services has needed a
secret somebody created by hand the day it first went live — undocumented, unrepeatable, and
exactly the kind of manual step this session has already found missing more than once. affiliate-
service's own first deploy sat at "no ready pod after 10 minutes" for precisely this reason.

SAME SCHEMA, SAME SHARED VALUES, SAME REUSE DISCIPLINE — deliberately a close mirror of the
platform's own script rather than a reinvention, so a person who has read one already understands
this one. The one real difference: this NEVER MINTS a shared value itself. `INTERNAL_SERVICE_TOKEN`,
`PII_SALT`, `TOKEN_HS256_SECRET`, `SECRETS_KEK`, `BACKUP_KEK` and the postgres password must be
BYTE-IDENTICAL to what base-services' own gen-secrets.py already wrote — a second, independently-
minted PII_SALT would pseudonymise the same person two different ways across services, which is a
data-integrity bug, not a cosmetic one. So this script REFUSES to run before that one has, rather
than minting its own (wrong) copies (see `_load_existing()` below).

A RE-RUN NEVER TOUCHES A KEY AN EXISTING SECRET ALREADY HAS — learned the expensive way, the same
day this script was written. Its first version rebuilt every `DATASTORE_DSN` from ONE shared `PG_DB`
default on every run, which is correct only the FIRST time a service's secret is minted; a service
that already has its own database (this cluster's operations/campaigns/bookings/insights/loyalty/
reminders each do, sitting on the same postgres instance under their own name) had its real,
data-holding database silently swapped for the near-empty shared one the moment this script ran a
second time — no error, no crash, the pod came up fine and simply looked at an empty database where
its customers and bookings used to be. `generate_and_apply` now PRESERVES an existing secret's keys
verbatim and only FILLS IN what is missing (a field newly added to that service's own config.py);
a fresh DSN is only ever minted for a key that has never existed before.

Modes, same as the platform's own:
  python3 deploy/gen-secrets.py --build     # (dev) regenerate deploy/secrets.schema.json
  python3 deploy/gen-secrets.py             # (server) generate + kubectl apply, reusing what
                                              # base-services' gen-secrets.py already minted
"""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                              # repo root (deploy/ -> ..)
SERVICES = ROOT / "services"                     # OUR OWN first-party services, never platform/services
SCHEMA = HERE / "secrets.schema.json"

NS = os.environ.get("NS", os.environ.get("NAMESPACE", "base-services"))
PG_HOST = os.environ.get("PG_HOST", "pgbouncer:6432")
PG_DB = os.environ.get("PG_DB", "base_services")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "base_services")
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")

# Non-sensitive constants — same values base-services' own services already carry.
CONSTANTS = {
    "CACHE_URL": REDIS_URL, "EVENTBUS_URL": REDIS_URL, "QUEUE_URL": REDIS_URL, "RATELIMIT_URL": REDIS_URL,
    "POSTGRES_DB": PG_DB, "POSTGRES_USER": POSTGRES_USER,
}
# Keys that must be BYTE-IDENTICAL to what base-services already minted — REUSED, never generated
# here. See the module docstring on why a second mint would be a real bug, not a style choice.
SHARED = ["INTERNAL_SERVICE_TOKEN", "PII_SALT", "TOKEN_HS256_SECRET", "POSTGRES_PASSWORD",
          "SECRETS_KEK", "BACKUP_KEK"]
ALIASES = {"TOKEN_SIGNING_SECRET": "TOKEN_HS256_SECRET"}

# THE MINTABLE VOCABULARY — identical to the platform's own, because every one of our services was
# scaffolded from the SAME `platform/services/_template` (create_service.py) and carries the same
# field names. A service's own key set is still the INTERSECTION of this with what its config.py
# actually declares, exactly like the platform's own script — a service with no KEK gets no KEK.
MINTABLE: dict[str, dict] = {
    "DATASTORE_DSN": {"t": "dsn", "role": POSTGRES_USER},
    "CACHE_URL": {"t": "const"}, "EVENTBUS_URL": {"t": "const"},
    "QUEUE_URL": {"t": "const"}, "RATELIMIT_URL": {"t": "const"},
    "INTERNAL_SERVICE_TOKEN": {"t": "shared"}, "PII_SALT": {"t": "shared"},
    "TOKEN_HS256_SECRET": {"t": "shared"}, "TOKEN_SIGNING_SECRET": {"t": "alias", "of": "TOKEN_HS256_SECRET"},
    "SECRETS_KEK": {"t": "shared"}, "BACKUP_KEK": {"t": "shared"},
}

_FIELD = re.compile(r"^\s+([A-Z][A-Z0-9_]+)\s*:\s*(?:str|int|bool|float)", re.MULTILINE)


def _b64d(v: str) -> str:
    return base64.b64decode(v).decode("utf-8", "replace")


def _config_fields(svc: Path) -> set[str]:
    cfg = svc / "app" / "config.py"
    if not cfg.is_file():
        return set()
    return set(_FIELD.findall(cfg.read_text(encoding="utf-8")))


def build_schema() -> None:
    """Regenerate the committed, secret-free schema from each of OUR services' config.py."""
    out: dict[str, dict] = {}
    for svc in sorted(p for p in SERVICES.iterdir() if p.is_dir() and p.name != "_template"):
        fields = _config_fields(svc)
        keys = {k: dict(MINTABLE[k]) for k in MINTABLE if k in fields}
        if keys:
            out[f"{svc.name}-secrets"] = {"keys": keys}
    SCHEMA.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    total = sum(len(s["keys"]) for s in out.values())
    print(f"wrote {SCHEMA} — {len(out)} secrets, {total} keys, no sensitive values")


def _load_existing() -> tuple[dict[str, str], dict[str, str], dict[str, dict[str, str]]]:
    """Recover the shared pool base-services' OWN gen-secrets.py already minted into the cluster —
    NEVER a fresh mint here — plus every secret's OWN current key/value map, verbatim.

    Returns (shared_values, role_passwords, secrets_by_name). The first two are empty only when
    base-services has not run yet, in which case `generate_and_apply` refuses rather than
    inventing its own. `secrets_by_name` is what makes a RE-RUN safe: see its own note below.
    """
    r = subprocess.run(["kubectl", "-n", NS, "get", "secret", "-o", "json"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return {}, {}, {}
    shared: dict[str, str] = {}
    role_pw: dict[str, str] = {}
    secrets_by_name: dict[str, dict[str, str]] = {}
    for item in json.loads(r.stdout or "{}").get("items", []):
        name = str((item.get("metadata") or {}).get("name") or "")
        decoded = {k: _b64d(v) for k, v in (item.get("data") or {}).items()}
        if name:
            secrets_by_name[name] = decoded
        for key, dec in decoded.items():
            if key in SHARED and key not in shared:
                shared[key] = dec
            elif key.endswith("_DSN") and "://" in dec:
                try:
                    role, tail = dec.split("://", 1)[1].split(":", 1)
                    role_pw.setdefault(role, tail.split("@", 1)[0])
                except (ValueError, IndexError):
                    pass
    return shared, role_pw, secrets_by_name


def generate_and_apply() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    if not schema:
        print("no first-party service needs a minted secret — nothing to do")
        return
    reuse_shared, reuse_role_pw, existing = _load_existing()
    missing = [k for k in SHARED if k not in reuse_shared]
    if missing:
        sys.exit(
            f"refusing to mint {', '.join(missing)} myself — run "
            f"platform/deploy/server/gen-secrets.py FIRST (bring-up.sh already orders it this "
            f"way). A value minted here instead of reused would not match what base-services' "
            f"own services already carry, and a mismatched PII_SALT pseudonymises the same "
            f"person two different ways across services — silently, and only discoverable much "
            f"later from data that no longer joins.")
    print(f"↻ reusing {len(reuse_shared)} shared value(s) already in {NS}")
    pool: dict[str, str] = dict(CONSTANTS)
    pool.update(reuse_shared)
    role_pw: dict[str, str] = dict(reuse_role_pw)

    import secrets as _secrets

    def dsn_for(role: str) -> str:
        # A FRESH DSN IS FOR A BRAND-NEW SERVICE ONLY — `generate_and_apply` below never calls
        # this for a key an existing secret already has. `PG_DB` is the shared database, which is
        # correct exactly because that is where a genuinely new service (nothing has EVER
        # provisioned it a database of its own) already lives — see the two real cases on this
        # cluster the day this was found: affiliate-service and portal, neither of which has ever
        # had its own database, both correctly on `base_services`. A service WITH its own
        # database (operations, campaigns, bookings, insights, loyalty, reminders — each with a
        # same-named database already sitting on this exact postgres instance) never reaches this
        # function at all once its secret exists once, because its DSN is preserved verbatim below.
        if role == pool["POSTGRES_USER"]:
            pw = pool["POSTGRES_PASSWORD"]
        else:
            pw = role_pw.setdefault(role, _secrets.token_hex(32))
        return f"postgresql://{role}:{pw}@{PG_HOST}/{PG_DB}"

    for name, spec in schema.items():
        # PRESERVE, DON'T RECONSTRUCT (the bug that took operations',
        # campaigns', bookings', insights', loyalty's and reminders' own databases OFFLINE the
        # first time this ran against a cluster with real data in them). A re-run used to rebuild
        # EVERY key from the shared pool + a single global `PG_DB`, which silently replaced each
        # service's own already-correct DATASTORE_DSN — pointing every one of them at the
        # (separate, empty) `base_services` database instead of its own, on a running cluster,
        # with no error of any kind: the pod came up fine, connected fine, and simply saw an empty
        # database where its real customers, operators and visits used to be.
        #
        # THE FIX: for a secret that already exists, KEEP EVERY KEY IT ALREADY HAS, verbatim —
        # this script only ever FILLS IN keys the existing secret does not have yet (a field newly
        # added to that service's own config.py since the last run). A key already present is never
        # regenerated, never reconstructed, and never compared against the "expected" shape — it is
        # simply left alone, exactly like the platform's own gen-secrets.py already does for the
        # secrets it mints.
        current = dict(existing.get(name) or {})
        data: dict[str, str] = dict(current)
        for key, meta in spec["keys"].items():
            if key in data:
                continue
            t = meta["t"]
            if t == "const":
                data[key] = pool[key]
            elif t == "alias":
                data[key] = pool[meta["of"]]
            elif t == "shared":
                data[key] = pool[key]
            elif t == "dsn":
                data[key] = dsn_for(meta["role"])
        if data == current:
            print(f"  = {name} (already complete, untouched)")
            continue
        _apply_secret(name, data)
    print(f"✔ generated + applied secrets for {len(schema)} first-party service(s) in {NS}")


def _apply_secret(name: str, data: dict[str, str]) -> None:
    args = ["kubectl", "-n", NS, "create", "secret", "generic", name]
    for k, v in data.items():
        args += [f"--from-literal={k}={v}"]
    args += ["--dry-run=client", "-o", "yaml"]
    y = subprocess.run(args, capture_output=True, text=True, check=True).stdout
    subprocess.run(["kubectl", "-n", NS, "apply", "-f", "-"], input=y, text=True, check=True,
                   stdout=subprocess.DEVNULL)
    print(f"  ✔ {name} ({len(data)} keys)")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "--build":
        build_schema()
    else:
        if not SCHEMA.exists():
            sys.exit(f"no {SCHEMA} — run: python3 {sys.argv[0]} --build")
        generate_and_apply()
