#!/usr/bin/env python3
# =============================================================================
# check_deploy_wiring.py — catch the wiring mistakes that only show up in production.
#
# Every check below exists because the failure it describes actually happened to us, and every one
# of them was invisible until something was already deployed. They are cheap to run and each one
# replaces a debugging session that started with a healthy-looking cluster.
#
#   1. DIGEST PINNED       — a values file must name a sha256 digest, never a tag and never empty.
#                            A tag can be moved, so a tag-pinned rollback is not a rollback: it is
#                            a re-pull of whatever that tag points at today.
#
#   2. DATABASE PROVISIONED — every service with datastore: postgres must appear in pre-deploy.sh's
#                            SERVICES list. Miss it and the service starts, answers /healthz, and
#                            fails on its first real write. Three services were added by hand
#                            before this check existed, and each was noticed only after deploying.
#
#   3. PRIVACY FAN-OUT     — every service that SERVES /internal/privacy/erase must be listed in
#                            compliance's PRIVACY_TARGETS. A service missing from that list is not
#                            "one we skipped": it is a customer told their data was deleted while a
#                            copy kept living. Ours was six services when it should have been
#                            seventeen, and nothing said so.
#
#   4. CRON PATHS EXIST    — every cronJobs[].path must be a real route in that service's source.
#                            A CronJob whose endpoint does not exist runs on schedule and 404s or
#                            422s forever, silently, and the only symptom is work not happening.
#
#   5. SHARED SECRET NAMED — a service that serves /internal/backup/export needs BACKUP_KEK, which
#                            is SHARED. Without it the endpoint answers 503 and the fleet looks
#                            backed up while most of it cannot produce a readable archive. This
#                            checks the values file says so, since the secret itself is not in git.
#
# Stdlib only. Exit 0 = clean, exit 1 = a problem named on its exact file.
# =============================================================================
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VALUES = ROOT / "deploy" / "services"
PRE_DEPLOY = ROOT / "deploy" / "hooks" / "pre-deploy.sh"
COMPLIANCE = VALUES / "compliance-service.values.yaml"
PLATFORM = ROOT / "platform" / "services"

C_G, C_R, C_Y, C_N = "\033[32m", "\033[31m", "\033[33m", "\033[0m"
problems: list[str] = []
notes: list[str] = []


def fail(where: str, msg: str) -> None:
    problems.append(f"{where}: {msg}")


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


def values_files() -> list[Path]:
    return sorted(VALUES.glob("*.values.yaml"))


def scalar(text: str, key: str) -> str:
    """First `key: value` in a values file, quotes stripped. Deliberately not a YAML parse: this
    must run with nothing installed, and the shapes we check are flat."""
    m = re.search(rf"^\s*{re.escape(key)}:\s*(.*?)\s*$", text, re.M)
    if not m:
        return ""
    v = m.group(1).strip()
    # Strip a trailing comment. A values file earns its keep by explaining itself, so `digest: "…"
    # # v0.12.6` is the normal shape — reading the comment as part of the value made this guard
    # reject every correctly-pinned file it was written to protect.
    if '"' in v:
        v = v.split('"')[1]
    elif "'" in v:
        v = v.split("'")[1]
    else:
        v = v.split("#", 1)[0].strip()
    return v


def service_source(svc: str) -> Path:
    """deploy/services/foo-service.values.yaml -> platform/services/foo-service"""
    return PLATFORM / svc


def serves(svc: str, path_fragment: str) -> bool:
    """Does this service's source declare a route containing the fragment?"""
    api = service_source(svc) / "app" / "api"
    if not api.is_dir():
        return False
    for f in api.rglob("*.py"):
        if path_fragment in read(f):
            return True
    return False


# ── 1. every image is pinned to a digest ─────────────────────────────────────────────────────
for f in values_files():
    text = read(f)
    digest = scalar(text, "digest")
    if not digest:
        fail(f.name, "no digest — an unpinned image is not a deployment anyone can reproduce")
    elif not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        fail(f.name, f"digest is not a sha256 ({digest!r}) — a tag can be moved, a digest cannot")

# ── 2. every postgres service has a database provisioned ─────────────────────────────────────
pre = read(PRE_DEPLOY)
m = re.search(r'^SERVICES="([^"]*)"', pre, re.M)
if not m:
    fail("pre-deploy.sh", "no SERVICES list found — cannot verify databases are provisioned")
else:
    provisioned = set(m.group(1).split())
    for f in values_files():
        text = read(f)
        if scalar(text, "datastore") != "postgres":
            continue
        svc = f.name.removesuffix(".values.yaml")
        # The database name is the service's short name, and it is not always a mechanical
        # transform: api-gateway's database is `gateway`. Accept any of the plausible spellings
        # rather than encoding one rule that a future service breaks.
        stem = svc.removesuffix("-service")
        short = stem.replace("-", "")
        candidates = {svc, stem, short, stem.split("-")[-1]}
        if not (candidates & provisioned):
            fail("pre-deploy.sh",
                 f"{svc} uses postgres but {short!r} is not in SERVICES — it will start, pass "
                 f"/healthz, and fail on its first write")

# ── 3. the erasure fan-out reaches every service that answers it ─────────────────────────────
comp = read(COMPLIANCE)
targets_line = scalar(comp, "PRIVACY_TARGETS")
if not comp:
    notes.append("compliance-service.values.yaml not found — privacy fan-out unchecked")
else:
    listed = {t.split("=", 1)[0] for t in targets_line.split(",") if "=" in t}
    for f in values_files():
        svc = f.name.removesuffix(".values.yaml")
        # api-gateway   routes only; it owns no store, so its ack would assert nothing.
        # compliance     is the ORCHESTRATOR of the fan-out, not a target of it. Its own records are
        #                the EVIDENCE that the request was served — consent proof is kept 7 years on
        #                purpose, because it is what answers a complaint years later. Erasing the
        #                proof along with the data would destroy the only defence we have.
        if svc in ("api-gateway", "compliance-service"):
            continue
        if serves(svc, "/privacy/erase") and svc not in listed:
            fail("compliance-service.values.yaml",
                 f"{svc} serves /internal/privacy/erase but is NOT in PRIVACY_TARGETS — a deletion "
                 f"request will never reach it, and the customer will be told it was honoured")

# ── 4. every scheduled job points at a route that exists ─────────────────────────────────────
for f in values_files():
    text = read(f)
    svc = f.name.removesuffix(".values.yaml")
    src = service_source(svc)
    if not src.is_dir():
        notes.append(f"{svc}: no source under platform/services — cron paths unchecked")
        continue
    for path in re.findall(r"^\s*path:\s*(\S+)\s*$", text, re.M):
        # A route is declared as a decorator suffix: @router.post("/backup/run") under a router
        # with prefix="/internal". Match on the tail so the prefix does not have to be resolved.
        tail = path.split("/internal", 1)[-1] or path
        if not serves(svc, f'"{tail}"'):
            fail(f.name, f"cronJob path {path} has no matching route in {svc} — it will run on "
                         f"schedule and fail on every run, silently")

# ── 5. export-capable services must say BACKUP_KEK is required ───────────────────────────────
for f in values_files():
    svc = f.name.removesuffix(".values.yaml")
    if not serves(svc, "/backup/export"):
        continue
    if "BACKUP_KEK" not in read(f):
        fail(f.name, f"{svc} serves /internal/backup/export but this file never mentions "
                     f"BACKUP_KEK — it is a SHARED secret, and without it the endpoint answers 503 "
                     f"while the fleet looks backed up")

# ── report ───────────────────────────────────────────────────────────────────────────────────
for n in notes:
    print(f"{C_Y}  ~ {n}{C_N}")
if problems:
    print(f"\n{C_R}  ✗ {len(problems)} wiring problem(s):{C_N}")
    for p in problems:
        print(f"    {C_R}{p}{C_N}")
    sys.exit(1)
print(f"{C_G}  ✔ deploy wiring is consistent — digests pinned, databases provisioned, "
      f"erasure fan-out complete, cron paths real, shared secrets named{C_N}")
