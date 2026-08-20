#!/usr/bin/env python3
"""Raje3's own first-party services — self-contained secret generation for a server install.

THE GAP THIS CLOSES (Tamam, 2026-08-20). `platform/deploy/server/gen-secrets.py` mints secrets for
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
PG_HOST = os.environ.get("PG_HOST", "postgres:5432")
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


def _load_existing() -> tuple[dict[str, str], dict[str, str]]:
    """Recover the shared pool base-services' OWN gen-secrets.py already minted into the cluster —
    NEVER a fresh mint here. Returns (shared_values, role_passwords); both empty means base-
    services has not run yet, and `generate_and_apply` refuses rather than inventing its own."""
    r = subprocess.run(["kubectl", "-n", NS, "get", "secret", "-o", "json"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return {}, {}
    shared: dict[str, str] = {}
    role_pw: dict[str, str] = {}
    for item in json.loads(r.stdout or "{}").get("items", []):
        for key, val in (item.get("data") or {}).items():
            dec = _b64d(val)
            if key in SHARED and key not in shared:
                shared[key] = dec
            elif key.endswith("_DSN") and "://" in dec:
                try:
                    role, tail = dec.split("://", 1)[1].split(":", 1)
                    role_pw.setdefault(role, tail.split("@", 1)[0])
                except (ValueError, IndexError):
                    pass
    return shared, role_pw


def generate_and_apply() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    if not schema:
        print("no first-party service needs a minted secret — nothing to do")
        return
    reuse_shared, reuse_role_pw = _load_existing()
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
        if role == pool["POSTGRES_USER"]:
            pw = pool["POSTGRES_PASSWORD"]
        else:
            pw = role_pw.setdefault(role, _secrets.token_hex(32))
        return f"postgresql://{role}:{pw}@{PG_HOST}/{PG_DB}"

    for name, spec in schema.items():
        data: dict[str, str] = {}
        for key, meta in spec["keys"].items():
            t = meta["t"]
            if t == "const":
                data[key] = pool[key]
            elif t == "alias":
                data[key] = pool[meta["of"]]
            elif t == "shared":
                data[key] = pool[key]
            elif t == "dsn":
                data[key] = dsn_for(meta["role"])
        _apply_secret(name, data)
    print(f"✔ generated + applied {len(schema)} secret(s) to {NS}")


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
