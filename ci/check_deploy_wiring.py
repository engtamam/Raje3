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
#   5. ENV KEY IS REAL     — every env key must be a field the service's Settings actually declares.
#                            An unknown key is not an error at runtime: pydantic DROPS it. So a typo
#                            is a setting that silently never applies, and the service runs happily
#                            on the default you thought you had overridden. This is the single
#                            cheapest check here and the one that catches the quietest failure.
#
#   6. EGRESS MATCHES USE  — a service configured to reach the object store or the open internet
#                            must have the NetworkPolicy to match. Get this wrong and the pod
#                            answers /healthz, hangs on /readyz, logs NOTHING, and sits at 0/1 while
#                            its packets are blackholed. That cost an evening.
#
#   7. SECURITY INVARIANTS — the posture we decided once and must not drift from: audit fail-closed,
#                            a real token verifier, the frozen issuer, and never a wildcard origin
#                            on a surface that also allows credentials.
#
#   8. SHARED SECRET NAMED — a service that serves /internal/backup/export needs BACKUP_KEK, which
#                            is SHARED. Without it the endpoint answers 503 and the fleet looks
#                            backed up while most of it cannot produce a readable archive. This
#                            checks the values file says so, since the secret itself is not in git.
#
# Stdlib only. Exit 0 = clean, exit 1 = a problem named on its exact file.
# =============================================================================
from __future__ import annotations

import ast
import concurrent.futures
import os
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
    """Where a service's source lives — theirs or OURS.

    Our own services sit in `services/`, not in the read-only submodule. Checking only the
    submodule made every guard silently degrade to "unchecked" for exactly the services we wrote
    ourselves — which is the wrong way round: their code is reviewed upstream and gated by
    thirty-nine of their own gates, ours is only gated by these.
    """
    ours = ROOT / "services" / svc
    return ours if ours.is_dir() else PLATFORM / svc


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

    # ── AND THE OTHER DIRECTION, WHICH NOTHING CHECKED (د-4) ──────────────────────────────────
    #
    # PRIVACY_TARGETS is what compliance CAN reach. TENANT_DATA_MAP is what operations REGISTERS
    # for a shop at signup — and the fan-out goes to the registered targets, not to the reachable
    # ones. So a service could sit in PRIVACY_TARGETS, serve the erase route, answer correctly if
    # asked — and never be asked, because nobody ever put it on any shop's map.
    #
    # Seven were in exactly that state: job, wallet, analytics, webhook, connector, feature-flag
    # and backup. Every erasure fanned out to the others, every one of THOSE acknowledged, and
    # `derive_completion` closed the request COMPLETED. The customer was told his data was gone
    # while seven stores still held it — and the check above was green the whole time, because it
    # only ever looked the other way.
    ops = ROOT / "deploy" / "services" / "operations.values.yaml"
    map_line = ""
    for line in read(ops).splitlines():
        if line.strip().startswith("TENANT_DATA_MAP:"):
            map_line = line.split(":", 1)[1].strip().strip('"')
            break
    mapped = {e.split(":", 1)[0].strip() for e in map_line.split(",") if ":" in e}
    if not mapped:
        fail("operations.values.yaml",
             "TENANT_DATA_MAP is empty or unreadable — no shop has a data map, so every erasure "
             "reaches nobody and closes COMPLETED")
    for svc in sorted(listed):
        if svc in ("api-gateway", "compliance-service"):
            continue
        if svc not in mapped:
            fail("operations.values.yaml",
                 f"{svc} is in PRIVACY_TARGETS but NOT in TENANT_DATA_MAP — no shop registers it, "
                 f"so no erasure ever reaches it and the request still closes COMPLETED")

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

# ── 5. every env key is a field the service actually declares ────────────────────────────────
def settings_fields(svc: str) -> set[str]:
    cfg = service_source(svc) / "app" / "config.py"
    if not cfg.exists():
        return set()
    # `    NAME: type = default` inside the Settings class. Upper-case only: those are the env-bound
    # knobs, and lower-case names are derived properties, not settings.
    return set(re.findall(r"^\s{4}([A-Z][A-Z0-9_]*)\s*:", read(cfg), re.M))


for f in values_files():
    svc = f.name.removesuffix(".values.yaml")
    declared = settings_fields(svc)
    if not declared:
        notes.append(f"{svc}: no config.py found — env keys unchecked")
        continue
    text = read(f)
    marker = "\nenv:"
    env = text.split(marker, 1)[1] if marker in text else ""
    env = re.split(r"^\S", env, maxsplit=1, flags=re.M)[0]     # stop at the next top-level key
    for key in re.findall(r"^\s{2}([A-Z][A-Z0-9_]*)\s*:", env, re.M):
        if key not in declared:
            fail(f.name, f"{key} is not a setting {svc} declares — pydantic DROPS unknown keys, so "
                         f"this silently never applies and the service runs on the default")

# ── 6. the network policy matches what the service is configured to reach ────────────────────
for f in values_files():
    text = read(f)
    svc = f.name.removesuffix(".values.yaml")
    wants_objectstore = scalar(text, "OBJECTSTORE_DRIVER") == "s3"
    has_objectstore = re.search(r"objectStore:\s*\n\s*enabled:\s*true", text) is not None
    if wants_objectstore and not has_objectstore:
        fail(f.name, "OBJECTSTORE_DRIVER is s3 but networkPolicy.egress.objectStore is not enabled "
                     "— the pod will answer /healthz, hang on /readyz, log nothing, and sit at 0/1")
    hosts = scalar(text, "EGRESS_ALLOWED_HOSTS")
    internet = re.search(r"^\s*internet:\s*true", text, re.M) is not None
    if hosts and not internet:
        fail(f.name, f"EGRESS_ALLOWED_HOSTS names {hosts!r} but networkPolicy.egress.internet is "
                     f"false — the application allows a host the network will never let it reach")

# ── 7. the security posture we decided once ──────────────────────────────────────────────────
for f in values_files():
    text = read(f)
    # `in text` would match the key inside a COMMENT — and these files explain themselves at
    # length, so prose about a setting is everywhere. Presence must mean "the key is set".
    def is_set(key: str) -> bool:
        return re.search(rf"^\s{{2}}{key}:", text, re.M) is not None
    if is_set("AUDIT_SINK_DRIVER"):
        if scalar(text, "AUDIT_SINK_DRIVER") == "null":
            fail(f.name, "AUDIT_SINK_DRIVER is null — the service records NOTHING, and an empty "
                         "hash chain looks like a working control while answering nothing")
        # Absent is fine: the default is True. Only an explicit weakening is a problem.
        if is_set("AUDIT_FAIL_CLOSED") and scalar(text, "AUDIT_FAIL_CLOSED") != "true":
            fail(f.name, "AUDIT_FAIL_CLOSED is not true — a privileged action would proceed "
                         "unwitnessed whenever the log is unreachable")
    # "rs256" (a static PEM, TOKEN_PUBLIC_KEY) and "jwks" (identity's own key set, fetched live,
    # TOKEN_JWKS_URL — supports key rotation with no redeploy) are BOTH asymmetric verify-only
    # drivers (see app/adapters/token_verifier/{rs256,jwks}.py); this check used to accept only
    # the first name and flagged 25 services running the second as a downgrade, which they were
    # not — found live the day a full sweep actually read what "jwks" does instead of assuming.
    # "hs256" (a shared secret — a second trust model, the real thing this guards against) and
    # "null" (no verification at all) are the only two that should ever fail here.
    if is_set("TOKEN_VERIFIER_DRIVER") and scalar(text, "TOKEN_VERIFIER_DRIVER") not in ("rs256", "jwks"):
        fail(f.name, "TOKEN_VERIFIER_DRIVER is neither rs256 nor jwks — identity signs, everyone "
                     "else verifies asymmetrically; anything else means a second trust model")
    if is_set("TOKEN_ISSUER") and scalar(text, "TOKEN_ISSUER") != "raje3":
        fail(f.name, "TOKEN_ISSUER is not 'raje3' — the issuer is frozen; a token minted under a "
                     "different one is rejected by every peer")
    origins = scalar(text, "CORS_ALLOWED_ORIGINS")
    if "*" in origins and scalar(text, "CORS_ALLOW_CREDENTIALS") == "true":
        fail(f.name, "a wildcard CORS origin together with credentials — that combination lets any "
                     "site on the internet make authenticated calls as a logged-in user")

# ── 8. a peer this service actually calls must have an address ───────────────────────────────
#
# THE FAILURE. `reminders` sends a customer his PDPL identity-verification code by asking
# compliance for it. `COMPLIANCE_SERVICE_URL` was declared with a default of "" and set in no
# values file, so the handler returned {"sent": false, "reason": "no compliance url configured"} —
# a refusal it told nobody. Every DSAR verification in production failed that way, permanently,
# while the subject's legal clock kept running. Check 5 could not see it: the key is REAL, it is
# simply absent, and an absent key is indistinguishable from a defaulted one.
#
# SCOPED TO A LIVE DEREFERENCE, and that scoping is the whole difficulty. Every service declares
# `COMPLIANCE_SERVICE_URL` for its consent-gate ADAPTER, which is selected by a driver key and
# whose null variant says out loud what it needs — an unset URL there is a configuration choice,
# not a silent failure. So `adapters/` and the container's driver table are excluded, and what
# remains is code that reaches for a peer on a request path.
#
# WHAT IT CANNOT SEE: a URL read through getattr(settings, "..."), and a peer addressed by any
# key not ending in _SERVICE_URL.
for svc_dir in sorted((ROOT / "services").iterdir()):
    if not (svc_dir / "app").is_dir():
        continue
    live: dict[str, str] = {}
    for p in sorted((svc_dir / "app").rglob("*.py")):
        rel = p.relative_to(svc_dir / "app").as_posix()
        # core/booking_assignment.py is an adapter in everything but location: which peer it
        # calls is chosen by BOOKING_PROVIDER_DRIVER ("config" | "real"), and its own build()
        # fail-fasts loudly if "real" is picked without BOOKINGS_SERVICE_URL set — the same
        # driver-gated, says-out-loud-what-it-needs shape the adapters/ exclusion above exists
        # for, just not under that directory name.
        if (rel == "config.py" or rel == "container.py" or rel.startswith("adapters/")
                or rel == "core/booking_assignment.py"):
            continue
        for key in sorted(set(re.findall(r"\b([A-Z][A-Z0-9_]*_SERVICE_URL)\b", read(p)))):
            live.setdefault(key, rel)
    vf = ROOT / "deploy" / "services" / f"{svc_dir.name}.values.yaml"
    text = read(vf) if vf.exists() else ""
    for key, where in live.items():
        if not re.search(rf"^\s*{key}\s*:", text, re.M):
            fail(f"{svc_dir.name}.values.yaml",
                 f"app/{where} calls a peer through {key}, which no values file sets — the call "
                 f"is skipped and the caller reports a reason nobody reads")

# ── 9. western digits only, everywhere ───────────────────────────────────────────────────────
# Deliberately scoped to what WE author. platform/ is upstream's and read-only, and .git is not
# prose. The check is on codepoints, not a regex: a byte-range grep gives false matches on other
# Arabic characters, which is how a first attempt reported clean English shell scripts as failures.
_ARABIC_INDIC = [(0x0660, 0x0669), (0x06F0, 0x06F9)]
# THE REAL REMAINING COST, FOUND BY PROFILING (cProfile) AFTER THE WALK/THREADING FIXES ABOVE
# BARELY MOVED THE NUMBER: not I/O at all, but a per-CHARACTER pure-Python loop —
# `{c for c in text if any(...)}` — run against the full text of every candidate file. On this
# repo that is 137 MILLION `ord()` calls, and it holds the GIL throughout, which is exactly why
# threading the read step (above) helped only a little: the bottleneck was never the syscall.
# A compiled regex character class does the identical scan inside the `re` module's C
# implementation instead of a Python-level loop — same two Unicode ranges, `finditer` in place of
# the comprehension, no other change to what counts as a hit.
_ARABIC_INDIC_RE = re.compile("[" + "".join(f"{chr(lo)}-{chr(hi)}" for lo, hi in _ARABIC_INDIC) + "]")
# PRUNED DURING THE WALK, NOT FILTERED AFTER IT — found live chasing this gate's own ~42s runtime
# on Windows, where each filesystem call is expensive: `Path.rglob("*")` has no way to skip a
# directory before descending into it, so the old version fully walked every `.venv`
# (thousands of files each, times ~15 Python services), every `node_modules`, the whole `platform`
# submodule (possibly duplicated again under a parallel worker's `.claude/worktrees/<id>/`), and
# `.git`'s own object store — before ever checking whether a given file belonged to any of those.
# `os.walk`'s own `topdown=True` contract (the default) makes `dirnames[:] = ...` actually prune:
# mutating the list in place before the loop yields those subdirectories tells the walk never to
# descend into them at all, not merely to skip acting on what it finds there. Same skip set as
# before (node_modules/platform/.venv/__pycache__/dist at ANY depth, .git and .claude at the root),
# same body below — only how the file list is produced changed.
_SKIP_DIR_NAMES = {"node_modules", "platform", ".venv", "__pycache__", "dist"}


def _arabic_indic_hits(p: Path) -> tuple[Path, str] | None:
    """Read + check ONE file — the unit of work handed to the thread pool below. Reading is what
    actually blocks (a syscall per file, and there can be tens of thousands of candidates even
    after pruning); CPython releases the GIL for the duration of that syscall, so threads here
    genuinely overlap I/O wait instead of only trading off against each other."""
    try:
        text = p.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None                                   # binary, or unreadable: not prose
    # ── the one legitimate reason to WRITE these characters ──────────────────────────────────
    # Code that REFUSES or CONVERTS Arabic-Indic digits has to name them: the plate normaliser
    # maps them to 0-9, the renderer refuses «٢٠%» as a discount, and their tests feed exactly
    # those strings in. This gate flagged all five, so it failed on every run — and a gate that
    # is always red is a gate nobody reads, which is worse than not having one. A file opts out
    # by SAYING SO, once, in a comment; no path list here to drift.
    if "arabic-indic-digits: intentional" in text:
        return None
    hits = sorted(set(_ARABIC_INDIC_RE.findall(text)))
    return (p, "".join(hits)) if hits else None


_candidates: list[Path] = []
for _dirpath, _dirnames, _filenames in os.walk(ROOT):
    _dirnames[:] = [d for d in _dirnames if d not in _SKIP_DIR_NAMES]
    _rel_parts = Path(_dirpath).relative_to(ROOT).parts
    if _rel_parts and _rel_parts[0] in (".git", ".claude"):
        _dirnames[:] = []
        continue
    _candidates.extend(Path(_dirpath) / _fname for _fname in _filenames)

# THE WALK ITSELF STAYS SEQUENTIAL (it is fast now — see the pruning note above); only the part
# that was still slow — opening and scanning tens of thousands of individual files — is threaded.
# Results are collected into a plain list from the pool's own `map`, in the SAME order `_candidates`
# was built, and `fail()` is called back on the main thread afterward — `problems`/`notes` are
# never appended to from more than one thread, so the ordering and thread-safety this gate's
# output has always had are both unchanged, only how the reading is scheduled is different.
with concurrent.futures.ThreadPoolExecutor(max_workers=32) as _pool:
    for _result in _pool.map(_arabic_indic_hits, _candidates):
        if _result is not None:
            _p, _hits = _result
            fail(str(_p.relative_to(ROOT)),
                 f"Arabic-Indic digits {_hits} — every number in this product is 0-9, "
                 f"including in Arabic text")

# ── 10. every advertised capability is actually enforced by a route ──────────────────────────
for f in values_files():
    svc = f.name.removesuffix(".values.yaml")
    src = service_source(svc)
    # OURS ONLY. Upstream's manifests are gated by thirty-nine of their own gates and platform/ is
    # read-only, so a finding there is noise we cannot act on. And their manifests legitimately
    # advertise capabilities a route cannot REQUIRE — `identity.login` is granted by logging in,
    # and a login route obviously cannot demand it of a caller who has not logged in yet. Scoped
    # to our services, where every capability we advertise is one we enforce.
    if not (ROOT / "services" / svc).is_dir():
        continue
    mani = src / "app" / "manifest.py"
    if not mani.exists():
        continue
    text = read(mani)
    m = re.search(r'"capabilities":\s*\[(.*?)\]', text, re.S)
    if not m:
        continue
    advertised = set(re.findall(r'"([a-z][a-z0-9_.]*)"', m.group(1)))
    # A route can enforce a capability through a named constant (e.g. affiliate-service's
    # `AFFILIATE_SELF = "affiliates.self"` in app/core/models.py, `require_capability(AFFILIATE_SELF)`
    # in app/api/v1/affiliate_self.py) rather than the literal string inline — so app/core is part of
    # the search too, not just app/api. Found live: 40+ real routes required "affiliates.self" this
    # way and the gate flagged it as dead anyway because it only ever grepped app/api.
    api = src / "app" / "api"
    core = src / "app" / "core"
    enforced = ""
    if api.is_dir():
        enforced += "".join(read(p) for p in api.rglob("*.py"))
    if core.is_dir():
        enforced += "".join(read(p) for p in core.rglob("*.py"))
    for cap in sorted(advertised):
        if f'"{cap}"' not in enforced:
            fail(f"{svc}/app/manifest.py",
                 f"capability {cap!r} is advertised but no route requires it — an operator can "
                 f"grant it, believe it opened something, and it opened nothing")

# ── 11. a value another namespace will read must be fully qualified ──────────────────────────
# Scoped to what we author and to the shape that actually bit us: a bare in-cluster hostname in a
# value that is copied across a namespace. Inside base-services the short name is correct, so this
# only looks at OUR scripts, which are where the copying happens.
for p in sorted((ROOT / "deploy").rglob("*.sh")):
    text = read(p)
    if "monitoring" not in text and "NS_MON" not in text:
        continue                                   # nothing here crosses a namespace
    for m in re.finditer(r"@(postgres|redis|objectstore):\d+", text):
        line = text[:m.start()].count(chr(10)) + 1
        # Skip comments. These files argue their own choices at length, so the very passage
        # explaining this trap contains the string it warns about — the fifth time today that
        # reading a file as text answered a question that was about structure.
        line_text = text.split(chr(10))[line - 1].lstrip()
        if line_text.startswith("#"):
            continue
        if "svc.cluster.local" not in text[max(0, m.start() - 200):m.end() + 200]:
            fail(str(p.relative_to(ROOT)),
                 f"line {line}: `{m.group(0)}` is a bare in-cluster name being carried across a "
                 f"namespace — it resolves only where it was written, and the consumer will go "
                 f"Ready and produce nothing")


# ── 12. a service that declares actions is a service the gateway must ask ─────────────────────
#
# The gateway aggregates every service's `admin_actions` and `user_actions` into ONE catalog the
# console calls — and it only asks the services named in ADMIN_SERVICES. Four of ours declared
# forty actions between them and were not in that list: the services were healthy, the
# declarations were correct, and the panel would have rendered EMPTY with nothing failing.
#
# "Declared but never aggregated" is the same species as the erasure endpoint nobody calls and the
# capability no route enforces. Both halves right, the seam missing, and no error anywhere.
gateway_values = ROOT / "deploy" / "services" / "api-gateway.values.yaml"
if gateway_values.exists():
    listed = set(re.findall(r"([a-z][a-z0-9-]*)=https?://", scalar(read(gateway_values),
                                                                  "ADMIN_SERVICES")))
    for p in values_files():
        svc = p.name.replace(".values.yaml", "")
        src = service_source(svc)
        if not (src / "app").is_dir():
            continue
        declared = 0
        for fname, var in (("admin_actions", "ADMIN_ACTIONS"), ("user_actions", "USER_ACTIONS")):
            f_ = src / "app" / f"{fname}.py"
            if not f_.is_file():
                continue
            try:
                tree = ast.parse(read(f_))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", "") == var:
                    declared += len(getattr(node.value, "elts", []))
        if declared and svc not in listed:
            fail("api-gateway.values.yaml",
                 f"{svc} declares {declared} action(s) but is not in ADMIN_SERVICES — the console "
                 f"never asks for them, so the panel renders empty with nothing failing anywhere")


# ── 13. every user-facing route is an action the console can show ─────────────────────────────
#
# A route an owner uses that declares no action is a feature the console cannot render. It is not
# broken — it is invisible, which is worse: the service works, the tests pass, and the owner never
# finds the screen.
#
# Found by counting: forty-two routes across four services had no action. Seven were the template
# library and the partner registry that our OWN console edits; six were the settings tree built
# that same day; three were the partner's console, which would have rendered empty for a company
# we had just promised a dashboard to.
#
# Ours only. Upstream's services are theirs to declare, and a gap there is a report, not a build
# failure on our side.
for svc_dir in sorted((ROOT / "services").iterdir()) if (ROOT / "services").is_dir() else []:
    if not (svc_dir / "app" / "manifest.py").is_file():
        continue
    svc = svc_dir.name
    try:
        tree = ast.parse(read(svc_dir / "app" / "manifest.py"))
    except SyntaxError:
        continue
    routes = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            try:
                d = ast.literal_eval(node)
            except Exception:                                   # noqa: BLE001
                continue
            if isinstance(d, dict) and d.get("tier") in ("user", "public") and "path" in d:
                p = re.sub(r"\{[^}]*\}", "{}", d["path"])
                if p in ("/healthz", "/readyz", "/metrics") or p.startswith("/api/v1/whoami"):
                    continue
                routes.add((p, d.get("method", "GET")))
    declared = set()
    for fname, var in (("admin_actions", "ADMIN_ACTIONS"), ("user_actions", "USER_ACTIONS")):
        f_ = svc_dir / "app" / f"{fname}.py"
        if not f_.is_file():
            continue
        try:
            atree = ast.parse(read(f_))
        except SyntaxError:
            continue
        for node in ast.walk(atree):
            if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", "") == var:
                for el in getattr(node.value, "elts", []):
                    try:
                        a = ast.literal_eval(el)
                    except Exception:                           # noqa: BLE001
                        continue
                    declared.add((re.sub(r"\{[^}]*\}", "{}", a.get("path", "")),
                                  a.get("method", "GET")))
    # EXEMPTED WITH A REASON — THE PLATFORM'S OWN MECHANISM, not one invented here. Every
    # base-service declares an `UNDECLARED_ROUTES` list for routes that are real and deliberately
    # not app controls; compliance-service uses it for the legal gate the shell drives rather than
    # a user clicks. Ours needs it for the two signup routes: the catalogue is fetched WITH a
    # token, so a route that exists precisely because there is no token yet cannot appear in a list
    # of what its holder may do.
    #
    # THE `why` IS REQUIRED. Without it this is a skip-list, and a skip-list is how a forgotten
    # route stops being a fault and starts being a habit.
    exempt = set()
    uf = svc_dir / "app" / "user_actions.py"
    if uf.is_file():
        try:
            utree = ast.parse(read(uf))
        except SyntaxError:
            utree = None
        for node in ast.walk(utree) if utree else []:
            if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", "") == "UNDECLARED_ROUTES":
                for el in getattr(node.value, "elts", []):
                    try:
                        row = ast.literal_eval(el)
                    except Exception:                           # noqa: BLE001
                        continue
                    if not row.get("why"):
                        fail(f"{svc}/app",
                             f"UNDECLARED_ROUTES lists {row.get('method')} {row.get('path')} "
                             f"with no `why` — an exemption without a reason is a skip-list")
                        continue
                    exempt.add((re.sub(r"\{[^}]*\}", "{}", row.get("path", "")),
                                row.get("method", "GET")))

    for path, method in sorted(routes - declared - exempt):
        fail(f"{svc}/app", f"{method} {path} is a user-facing route with no declared action — "
                           f"the console cannot render it, and nothing fails")


# ── 13b. a promise of delivery matches a channel that can deliver ─────────────────────────────
#
# THE FAILURE THIS EXISTS FOR, and it is the quietest one in the product. notification-service's
# `console` WhatsApp driver writes a log line and returns True. identity therefore answers
# `delivered: true`, our signup answers "we sent you a code", and the person waits for a message no
# part of the system ever attempted. Every component is honest; the sum is a lie.
#
# The only place that knows is the one that CHOSE the driver. So operations declares
# SIGNUP_OTP_DELIVERABLE, and this ties that declaration to the channel actually configured — in
# both directions: claiming deliverability on a console chain fails the build, and forgetting to
# flip it when Meta is wired in leaves signup refusing a code it could have sent, which is also a
# failure and also caught.
_ops = read(VALUES / "operations.values.yaml")
_notif = read(VALUES / "notification-service.values.yaml")
if _ops and _notif:
    _claims = scalar(_ops, "SIGNUP_OTP_DELIVERABLE").lower() == "true"
    _chain = scalar(_notif, "WHATSAPP_CHAIN")
    # A chain is a comma-separated fallback list; `meta` anywhere in it means a real send is
    # possible. `console` and `webhook` are development shapes that report success regardless.
    _real = any(link.strip() == "meta" for link in _chain.split(","))
    if _claims and not _real:
        fail("operations.values.yaml",
             f"SIGNUP_OTP_DELIVERABLE is true but notification-service's WHATSAPP_CHAIN is "
             f"{_chain!r} — the console driver returns success without sending, so every layer "
             f"would report a delivered code that does not exist")
    if _real and not _claims:
        fail("operations.values.yaml",
             "WHATSAPP_CHAIN can reach Meta but SIGNUP_OTP_DELIVERABLE is false — signup refuses "
             "to send a code it could actually deliver, and blames itself for it")
    # AND THE COMBINATION THAT CANNOT EVER BE RIGHT: demanding a proof that cannot be sent. It is
    # a locked door with no key, and the person on the wrong side of it did nothing wrong.
    if str(scalar(_ops, "SIGNUP_REQUIRE_OTP")).lower() == "true" and not _claims:
        fail("operations.values.yaml",
             "SIGNUP_REQUIRE_OTP is true while SIGNUP_OTP_DELIVERABLE is false — every new owner "
             "would be told to confirm a number, and no code would ever be sent to confirm it")


# ── 14. the owner holds everything, and the two lanes never mix ───────────────────────────────
#
# THE OWNER'S SET IS WRITTEN OUT, NOT A WILDCARD. A wildcard grants every capability added in
# future to somebody nobody asked; naming them means shipping a capability includes deciding who
# gets it. The cost of that decision is this check: a capability our services declare that the
# owner does not hold is a feature its own owner cannot reach — shipped, working, and invisible.
#
# AND NO platform.* IN A TENANT ROLE. authz strips them at mint, so this is the second defence
# rather than the only one — but the first defence is that nobody wrote one down, and that is what
# this reads.
seed_dir = ROOT / "deploy" / "seed"
# THE FILE THE SIGNUP PATH ACTUALLY READS is baked into the operations image at
# `/app/data/roles.seed.json` (operations.values.yaml `SIGNUP_ROLES_FILE`), which is
# `services/operations/data/roles.seed.json` in the repository. This check read
# `deploy/seed/roles.json` — a second copy of the same meaning, seeded by hand into authz. The two
# say the same thing today and nothing whatsoever holds them together, so every rule below was
# being enforced against a file the running system never opens (ل-9). Both are read now, and they
# must agree role for role and capability for capability.
tenant_roles = ROOT / "services" / "operations" / "data" / "roles.seed.json"
hand_seeded_roles = seed_dir / "roles.json"
operator_roles = seed_dir / "operator-roles.json"
if tenant_roles.is_file():
    import json as _json
    roles = _json.loads(read(tenant_roles)).get("roles", [])

    # ── AND THE HAND-SEEDED COPY SAYS THE SAME THING ─────────────────────────────────────────
    # Two files, one meaning: the image bakes one and `seed-roles.sh` pushes the other into
    # authz. A capability added to one and forgotten in the other is a role that behaves
    # differently depending on whether the tenant was created by the saga or by the seeder —
    # and nothing would fail, on either path, at any layer.
    if hand_seeded_roles.is_file():
        def _shape(rows):
            return {r.get("name"): sorted(set(r.get("capabilities") or [])) for r in rows}
        _live = _shape(roles)
        _hand = _shape(_json.loads(read(hand_seeded_roles)).get("roles", []))
        if _live != _hand:
            _names = sorted(set(_live) ^ set(_hand)) or [
                n for n in sorted(set(_live) & set(_hand)) if _live[n] != _hand[n]]
            fail("services/operations/data/roles.seed.json",
                 f"disagrees with deploy/seed/roles.json on: {', '.join(_names)} — the saga and "
                 f"the seeder would grant different capabilities for the same role name")
    owner = next((r for r in roles if r.get("name") == "owner"), None)
    if owner is None:
        fail("deploy/seed/roles.json", "no `owner` role — a tenant whose roles arrive without one "
                                       "is a tenant nobody can administer")
    else:
        held = set(owner.get("capabilities", []))
        # Only OUR capabilities: upstream's are theirs to enumerate, and a gap there is a report.
        ours = set()
        for svc_dir in sorted((ROOT / "services").iterdir()) if (ROOT / "services").is_dir() else []:
            m = svc_dir / "app" / "manifest.py"
            if not m.is_file():
                continue
            try:
                tree = ast.parse(read(m))
            except SyntaxError:
                continue
            # THE VALUE OF THE `capabilities` KEY, not the whole dict. `literal_eval` on the
            # manifest fails — it contains `settings.SERVICE_NAME` — so the first version of this
            # check silently collected NOTHING and passed by examining an empty set. A guard that
            # passes because it read nothing is the exact species it was written to catch, and it
            # was found by deliberately breaking the owner role and watching it stay green.
            for node in ast.walk(tree):
                if not isinstance(node, ast.Dict):
                    continue
                for k, v in zip(node.keys, node.values):
                    if (isinstance(k, ast.Constant) and k.value == "capabilities"
                            and isinstance(v, ast.List)):
                        ours |= {e.value for e in v.elts
                                 if isinstance(e, ast.Constant) and isinstance(e.value, str)}
        # platform.*, the partner's, and the affiliate marketer's are deliberately NOT the
        # owner's: platform.* is ours, partner.read belongs to a till company, and
        # affiliates.self belongs to a marketer promoting shops — none of the three is a role an
        # establishment's own owner ever holds.
        expected = {c for c in ours
                    if not c.startswith("platform.") and c not in ("partner.read", "affiliates.self")}
        for cap in sorted(expected - held):
            fail("deploy/seed/roles.json",
                 f"`{cap}` is declared by a service but the owner role does not hold it — a "
                 f"feature its own owner cannot reach")

    for r in roles:
        for cap in r.get("capabilities", []):
            if str(cap).startswith("platform."):
                fail("deploy/seed/roles.json",
                     f"tenant role `{r.get('name')}` carries `{cap}` — platform capabilities are "
                     f"ours, and an establishment must never be able to hold one")

if operator_roles.is_file():
    import json as _json
    # NOT EVERY OPERATOR CAPABILITY IS `platform.*`, AND THE FILE'S OWN HEADER SAYS WHY: a handful
    # of peer services (identity-service, billing-service, notification-service, tenant-service,
    # ticket-service, webhook-service, onboarding-service) gate their own routes on the literal,
    # bare capability string a tenant role ALSO holds — not on a platform-namespaced one — because
    # that is the name those services' own code checks (see operator-roles.json's own
    # "TWO NAMES THAT LOOK REDUNDANT BUT ARE NOT" and "A THIRD PAIR..." passages). Granting the
    # platform-owner oversight of, say, billing plans/pricing has no `platform.billing_plans`
    # capability to ask for — the only door that exists is `billing.manage`, the tenant's own
    # door, and an operator legitimately needs a key to it too. This is a closed, named list of
    # exactly those documented exceptions — a bare capability NOT on this list is still exactly
    # what this check was written to catch: a real tenant-lane leak into the operator lane.
    _BARE_CAP_OPERATOR_EXCEPTIONS = {
        "billing.manage", "members:read", "members:write", "notifications.templates",
        "onboarding.manage", "service_accounts:read", "service_accounts:write", "tenant.manage",
        "tickets.manage", "webhooks.read",
    }
    for r in _json.loads(read(operator_roles)).get("roles", []):
        for cap in r.get("capabilities", []):
            if not str(cap).startswith("platform.") and cap not in _BARE_CAP_OPERATOR_EXCEPTIONS:
                fail("deploy/seed/operator-roles.json",
                     f"operator role `{r.get('name')}` carries `{cap}`, which is a tenant "
                     f"capability — the operator lane is not the tenant lane")

# ── 16. every platform capability is held by one of OUR roles ─────────────────────────────────
# Guard 14 checks that the OWNER can reach every tenant capability. Nobody was checking the mirror
# of that question about us — and `platform.loyalty` and `platform.insights` shipped declared,
# enforced at their routes, and held by none of our five operator roles. Both surfaces were the
# repair paths: fixing a balance that drifted from its ledger, and recomputing a dashboard a shop
# is asking about. They were closed to the only people who would ever need them, and the first
# symptom would have been a support engineer getting a 403 during an incident.
if operator_roles.is_file():
    import json as _json
    _ops = _json.loads(read(operator_roles)).get("roles", [])
    _held = set().union(*[set(r.get("capabilities") or []) for r in _ops]) if _ops else set()
    _declared: set[str] = set()
    for svc_dir in sorted((ROOT / "services").glob("*/app/manifest.py")):
        tree = ast.parse(read(svc_dir))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            for k, v in zip(node.keys, node.values):
                if (isinstance(k, ast.Constant) and k.value == "capabilities"
                        and isinstance(v, ast.List)):
                    _declared |= {e.value for e in v.elts
                                  if isinstance(e, ast.Constant) and isinstance(e.value, str)}
    for cap in sorted({c for c in _declared if c.startswith("platform.")} - _held):
        fail("deploy/seed/operator-roles.json",
             f"`{cap}` is declared and enforced by a service but no operator role holds it — "
             f"the surface behind it is closed to us, and the first symptom is a 403 during an "
             f"incident")

# ── 17. every declared action points at a route that exists ───────────────────────────────────
# Guard 13 asks whether every user-facing ROUTE has an action, so the console can render it.
# Nobody was asking the reverse — whether every declared ACTION has a route — and `portal` carried
# eight actions copied from another service's scaffold: operator config and secrets paths it does
# not serve, under a capability it does not advertise, with one id declared twice. The console
# would have rendered five buttons that 404, and the panel is the only place that would have
# shown it.
for _svc_dir in sorted((ROOT / "services").glob("*/app/manifest.py")):
    _svc = _svc_dir.parent.parent.name
    _tree = ast.parse(read(_svc_dir))
    _caps: set[str] = set()
    _routes: set[tuple[str, str]] = set()
    for node in ast.walk(_tree):
        if not isinstance(node, ast.Dict):
            continue
        for k, v in zip(node.keys, node.values):
            if not isinstance(k, ast.Constant):
                continue
            if k.value == "capabilities" and isinstance(v, ast.List):
                _caps |= {e.value for e in v.elts if isinstance(e, ast.Constant)}
            if k.value == "endpoints" and isinstance(v, ast.List):
                for e in v.elts:
                    if not isinstance(e, ast.Dict):
                        continue
                    d = {kk.value: vv.value for kk, vv in zip(e.keys, e.values)
                         if isinstance(kk, ast.Constant) and isinstance(vv, ast.Constant)}
                    if d.get("path"):
                        _routes.add((re.sub(r"\{[^}]*\}", "{}", d["path"]),
                                     d.get("method", "GET")))

    for _file, _var in (("admin_actions.py", "ADMIN_ACTIONS"),
                        ("user_actions.py", "USER_ACTIONS")):
        _path = _svc_dir.parent / _file
        if not _path.is_file():
            continue
        _mod = ast.parse(read(_path))
        _actions = []
        for _n in _mod.body:
            _target = (getattr(getattr(_n, "target", None), "id", "")
                       or "".join(getattr(_t, "id", "") for _t in getattr(_n, "targets", [])))
            if _target == _var:
                try:
                    _actions = ast.literal_eval(_n.value)
                except (ValueError, SyntaxError):
                    _actions = []
        _seen: set[str] = set()
        for _a in _actions:
            if not isinstance(_a, dict):
                continue
            _id = str(_a.get("id", ""))
            if _id in _seen:
                fail(f"{_svc}/app/{_file}",
                     f"action `{_id}` is declared twice — the console keys on the id, so one of "
                     f"the two is unreachable and nobody can tell which")
            _seen.add(_id)
            _key = (re.sub(r"\{[^}]*\}", "{}", str(_a.get("path", ""))),
                    _a.get("method", "GET"))
            if _key not in _routes:
                fail(f"{_svc}/app/{_file}",
                     f"action `{_id}` points at {_key[1]} {_key[0]}, which this service's manifest "
                     f"does not declare — the console renders a button that 404s")
            _cap = _a.get("capability")
            if _cap and _cap not in _caps:
                fail(f"{_svc}/app/{_file}",
                     f"action `{_id}` requires `{_cap}`, which this service does not advertise — "
                     f"nobody can ever be granted it here")

# ── 15. the custom-role builder can actually build a role ─────────────────────────────────────
# AUTHZ_TENANT_ASSIGNABLE_CAPS is an ALLOWLIST, and an allowlist with a wrong name in it does not
# fail — it silently refuses. Ours was written by hand in a vocabulary no service ever declared
# (`operations.record.create`), so every owner building a custom role got a 403 that read like
# policy. Nothing caught it: the seeder holds `platform.authz` and skips the check. So the list is
# not allowed to be hand-maintained — it must be the owner's capabilities minus the three that are
# nobody's to hand out, exactly.
_az = ROOT / "deploy" / "services" / "authz-service.values.yaml"
if _az.is_file() and tenant_roles.is_file():
    import json as _json
    _text = read(_az)
    # A `>-` folded block: take the indented lines that follow the key.
    _m = re.search(r"^(\s*)AUTHZ_TENANT_ASSIGNABLE_CAPS:\s*>-\s*$((?:\n\1\s+.*)+)", _text, re.M)
    if not _m:
        fail("deploy/services/authz-service.values.yaml",
             "AUTHZ_TENANT_ASSIGNABLE_CAPS is missing or not a folded block — the owner's custom "
             "role builder (§3.4) needs it, and empty means it refuses everything")
    else:
        allowed = {c.strip() for c in _m.group(2).replace("\n", "").split(",") if c.strip()}
        _owner = next((r for r in _json.loads(read(tenant_roles)).get("roles", [])
                       if r.get("name") == "owner"), {})
        never = {"authz.manage", "tenant.manage"}   # escalation by proxy; §3.2 root protection
        want = {c for c in _owner.get("capabilities", []) if c not in never}
        for cap in sorted(want - allowed):
            fail("deploy/services/authz-service.values.yaml",
                 f"the owner holds `{cap}` but no establishment may put it in a custom role — "
                 f"a capability that exists and cannot be delegated")
        for cap in sorted(allowed - want):
            fail("deploy/services/authz-service.values.yaml",
                 f"`{cap}` is assignable in a custom role but the owner does not hold it — "
                 f"nobody can grant a capability they do not have (§3.2)")

# ── 18. a script we SHIP must not carry Windows line endings ───────────────────────────────────────────
# THE FAILURE IS INVISIBLE AND TOTAL. ship.sh tars the WORKING COPY, not the git index -- so
# a file checked out before .gitattributes existed travels to the server with CRLF, the
# kernel reads the shebang as "/usr/bin/env bash" plus a carriage return, and the answer is
# "No such file or directory" about an interpreter that is plainly there.
#
# FOUND BY RUNNING THE PROOFS RATHER THAN BY READING THEM. Two prove-*.sh had been on the
# box for weeks answering 127 in a place nobody was reading -- and a guard that never runs
# looks exactly like a guard that always passes.
for _sh in sorted(ROOT.glob("deploy/**/*.sh")) + sorted(ROOT.glob("scripts/*.sh")):
    if bytes([13, 10]) in _sh.read_bytes():
        fail(_sh.relative_to(ROOT).as_posix(),
             "CRLF line endings - the shebang fails on the server with 'No such file or "
             "directory' about bash itself. Fix: git config core.autocrlf false, then "
             "re-checkout the file")


# ── every channel still on the bring-up driver, said out loud on every run ───────────────────
#
# `console` is a driver that ALWAYS SUCCEEDS and records what it would have sent. That is right
# during bring-up and fatal after it: a genuine provider outage then looks exactly like a
# delivered message, and the send log agrees.
#
# THE VALUES FILE ALREADY SAYS SO, IN A COMMENT — and a comment is not a mechanism. Proven on the
# cluster today: notification-service answered a real send with 200 and `status: failed,
# provider: ""`, because WHATSAPP_CHAIN is `console`. Nothing in the fleet said that out loud.
#
# A NOTE RATHER THAN A FAILURE, deliberately: this is the correct state until Meta credentials
# exist (#167), and a guard that blocks every ship during bring-up is a guard somebody disables.
# WHATSAPP ONLY, AND THAT IS THE POINT. This product sends over ONE channel: reminders'
# MESSAGE_CHANNEL is whatsapp and no line in any of our services uses email or SMS. Naming those
# two here would put a permanent line in front of the reader about something that cannot affect a
# customer — and a warning that is mostly noise is a warning nobody reads.
_console = []
for _vals in sorted(ROOT.glob("deploy/services/*.values.yaml")):
    _svc = _vals.name.replace(".values.yaml", "")
    for _line in _vals.read_text(encoding="utf-8").splitlines():
        _bare = _line.split("#", 1)[0]
        if "WHATSAPP_CHAIN:" in _bare and "console" in _bare:
            _console.append(f"{_svc}: {_bare.strip()}")
if _console:
    notes.append("WhatsApp is still on the bring-up driver — `console` always succeeds, so a real "
                 "outage reads as delivered and the send log agrees. Remove before real "
                 "customers: " + " · ".join(_console))


# ── 18. every user-facing endpoint has a route that can actually reach it ─────────────────────
# Guard 17 checks that a declared ACTION points at a route the service itself serves — but a
# route the service serves is still unreachable from a browser if api-gateway never proxies it.
# Found live, twice in one session: `/api/v1/secrets` (secrets-admin) and `/api/v1/admin/leads/geo`
# + `/api/v1/platform/branches/locations` (affiliate-service, operations) were all declared,
# deployed, and capability-correct — the catalog found them, the console rendered the button — and
# every one 404'd or 504'd because GATEWAY_ROUTES had no prefix covering them. The service and the
# console both looked fine; the missing piece lived in a third file neither of them checks.
_gw_values = ROOT / "deploy" / "services" / "api-gateway.values.yaml"
if _gw_values.is_file():
    _gw_text = read(_gw_values)
    # BOUNDED BY THE ARRAY'S OWN CLOSING `]`, NOT BY GUESSING WHICH KEY COMES NEXT. An earlier
    # version of this regex matched "any indented line" and kept going straight through
    # UPSTREAM_TIMEOUT_SECONDS into the NEXT env key's own comment block (every top-level env key
    # is indented under `env:` too, so "indented" alone never bounds the block) — it "found" -#
    # comment lines that were never inside GATEWAY_ROUTES at all, a false positive from this
    # gate's own parsing, not a real bug in the file. The block scalar's own content is JSON, so
    # its true end is the line whose stripped text is exactly "]".
    _gw_m = re.search(r"GATEWAY_ROUTES:\s*\|\n", _gw_text)
    _gw_prefixes: list[str] = []
    if _gw_m:
        _gw_body_lines = _gw_text[_gw_m.end():].splitlines()
        _gw_block: list[str] = []
        for _ln in _gw_body_lines:
            _gw_block.append(_ln)
            if _ln.strip() == "]":
                break
        _gw_lines = [ln for ln in _gw_block if ln.strip()]
        # THE SAME CRASH THIS BLOCK'S OWN COMMENTS ELSEWHERE WARN ABOUT: a `#` line inside this
        # block scalar is not a YAML comment, it is part of the JSON value, and api-gateway
        # crash-loops on boot trying to parse it. A gate that silently ignored such a line here
        # would parse "successfully" against corrupted input and never catch the one mistake that
        # has taken the product's own front door down twice.
        _hash_lines = [ln for ln in _gw_lines if ln.lstrip().startswith("#")]
        if _hash_lines:
            fail("deploy/services/api-gateway.values.yaml",
                 f"GATEWAY_ROUTES contains {len(_hash_lines)} line(s) starting with '#' — this is "
                 f"a YAML block scalar, so '#' does NOT start a comment here; it becomes part of "
                 f"the JSON value and crash-loops api-gateway on boot (this has happened twice "
                 f"live). Move any explanation ABOVE the `GATEWAY_ROUTES: |` line instead.")
        else:
            try:
                import json as _json2
                _gw_routes = _json2.loads("\n".join(_gw_lines))
                _gw_prefixes = sorted((r.get("prefix", "") for r in _gw_routes), key=len,
                                      reverse=True)
            except (ValueError, _json2.JSONDecodeError):
                fail("deploy/services/api-gateway.values.yaml",
                     "GATEWAY_ROUTES did not parse as JSON — cannot check route coverage")

    if _gw_prefixes:
        for _svc_dir2 in sorted((ROOT / "services").glob("*/app/manifest.py")):
            _svc2 = _svc_dir2.parent.parent.name
            _tree2 = ast.parse(read(_svc_dir2))
            for _node2 in ast.walk(_tree2):
                if not isinstance(_node2, ast.Dict):
                    continue
                for _k2, _v2 in zip(_node2.keys, _node2.values):
                    if not (isinstance(_k2, ast.Constant) and _k2.value == "endpoints"
                            and isinstance(_v2, ast.List)):
                        continue
                    for _e2 in _v2.elts:
                        if not isinstance(_e2, ast.Dict):
                            continue
                        _d2 = {kk.value: vv.value for kk, vv in zip(_e2.keys, _e2.values)
                              if isinstance(kk, ast.Constant) and isinstance(vv, ast.Constant)}
                        # ONLY "user" — "public" (healthz/readyz/metrics) is probed in-cluster,
                        # never through the gateway, and "internal" is pod-to-pod only (cron
                        # targets, peer calls) by the same convention guard 17 already relies on.
                        if _d2.get("tier") != "user":
                            continue
                        _p2 = str(_d2.get("path", ""))
                        if not _p2 or not any(_p2.startswith(pfx) for pfx in _gw_prefixes if pfx):
                            fail(f"{_svc2}/app/manifest.py",
                                 f"endpoint {_d2.get('method', 'GET')} {_p2!r} is tier=user "
                                 f"(console-reachable) but no GATEWAY_ROUTES prefix in "
                                 f"api-gateway.values.yaml covers it — every request 404s (no "
                                 f"match) or the browser never reaches this service at all")

# ── report ───────────────────────────────────────────────────────────────────────────────────
for n in notes:
    print(f"{C_Y}  ~ {n}{C_N}")
if problems:
    print(f"\n{C_R}  ✗ {len(problems)} wiring problem(s):{C_N}")
    for p in problems:
        print(f"    {C_R}{p}{C_N}")
    sys.exit(1)
print(f"{C_G}  ✔ deploy wiring is consistent — digests pinned, databases provisioned, "
      f"erasure fan-out complete, cron paths real, env keys declared, egress matches use, "
      f"security posture held, shared secrets named, digits western, capabilities "
      f"enforced, cross-boundary values qualified, actions aggregated and complete, "
      f"roles whole and separate, and every user-facing endpoint has a real gateway route{C_N}")
