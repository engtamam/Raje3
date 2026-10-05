#!/usr/bin/env python3
"""The whole product on one laptop — the stack the demo seed (index.mjs beside this) runs against.

WHY THIS EXISTS. The demo seed has to go through the REAL HTTP API, the same doors the console
calls, and that means a real gateway in front of real services that really talk to each other:
signup really provisions a tenant at tenant-service and an owner at identity, a visit really
publishes on the event bus that loyalty earns points from, a trial is really a billing row. There
is no docker-compose for this product (the cluster is k3s), so this assembles it by hand — once,
in code, instead of once per person per afternoon.

EVERY SERVICE'S ENV IS ITS PRODUCTION ENV. Read straight out of `deploy/services/<name>.values.yaml`
— the exact file the cluster deploys from — with `http://<service>:8000` rewritten to the local
port that service listens on here. A hand-written local env would drift from production the first
time somebody adds a setting there and not here; this one cannot, because it is not a copy. Only
what genuinely cannot hold on one laptop is overridden (`_LOCAL_OVERRIDES` below), each with its
reason. A peer this stack does not run (notification-service, audit, wallet…) is pointed at a
local responder that answers 503 at once (`_absent_peer`), so it fails the way an outage fails —
fast, and through the code path the service already has for it — rather than hanging on a
hostname that does not resolve.

THE SCHEDULED JOBS RUN TOO. job-service is not run here either, so the launcher fires every
route in deploy/hooks/provision-cron-migrations.sh on its own schedule (`_scheduler`), signed the
way job-service signs them — insights snapshots, reminders' tick, loyalty's recovery and the rest
keep happening exactly as they do in the cluster. `run-job <name>` fires one immediately.

PERSISTENT. Postgres and Redis run as named-volume Docker containers, so a seeded demo shop
survives a restart of this script, of Docker, of the machine. The shared secrets (PII_SALT above
all: change it and every stored pseudonym stops matching) are minted once into the gitignored
state directory and reused on every later start for the same reason.

`platform/` IS ONLY EVER READ. Its services run from their own source tree with this stack's own
venv; nothing is installed into, written under, or edited in it (`PYTHONDONTWRITEBYTECODE` keeps
even `__pycache__` out of it).

Usage:
  python media/tours/seed-demo-apps/local_stack.py up      # start everything, Ctrl-C stops it all
  python media/tours/seed-demo-apps/local_stack.py down    # stop the Postgres/Redis containers
  python media/tours/seed-demo-apps/local_stack.py reset   # wipe all local data (stack stopped first)
  python media/tours/seed-demo-apps/local_stack.py run-job insights-tick   # fire a scheduled job now
  PLATFORM_DIR=/path/to/platform python …/local_stack.py up # a platform checkout elsewhere

The gateway listens on 127.0.0.1:8090 — the port apps/console's own vite proxy already targets by
default — so `npm run dev` in apps/console serves the real console against this stack unchanged.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
VALUES = ROOT / "deploy" / "services"
STATE = HERE.parent / ".local-stack"            # media/tours/.local-stack — gitignored
PLATFORM = Path(os.environ.get("PLATFORM_DIR") or ROOT / "platform")

PG_CONTAINER, PG_PORT, PG_VOLUME = "raje3-demo-pg", 55432, "raje3-demo-pg"
REDIS_CONTAINER, REDIS_PORT, REDIS_VOLUME = "raje3-demo-redis", 56379, "raje3-demo-redis"
PG_USER = PG_PASSWORD = "demo"
REDIS_URL = f"redis://127.0.0.1:{REDIS_PORT}/0"
GATEWAY_PORT = 8090

# Started in this order — the platform core first, because operations' boot reads billing's plans
# and every token anyone holds is minted by identity. The gateway last: it is the front door, and a
# door that opens onto services still booting answers 502 to the first request through it.
SERVICES: list[tuple[str, str, int]] = [
    ("identity-service", "platform", 8101),
    ("tenant-service", "platform", 8102),
    ("authz-service", "platform", 8103),
    ("billing-service", "platform", 8104),
    ("search-service", "platform", 8106),
    ("operations", "ours", 8201),
    ("bookings", "ours", 8202),
    ("loyalty", "ours", 8203),
    ("campaigns", "ours", 8204),
    ("reminders", "ours", 8205),
    ("insights", "ours", 8206),
    ("coworking", "ours", 8207),
    ("referrals", "ours", 8208),
    ("api-gateway", "platform", GATEWAY_PORT),
]
PORTS = {name: port for name, _, port in SERVICES}
# WHERE A PEER THIS STACK DOES NOT RUN IS POINTED: a tiny responder (`_absent_peer` below) that
# answers every request 503 at once. A plain closed port was the first idea and measured wrong on
# Windows — a refused loopback connect is retried by the OS for ~2s, so every call to an absent
# peer cost two seconds and a signup (data map + trials, a dozen such calls) outlived the
# gateway's own 15s upstream timeout. A 503 is still exactly an outage to the caller, just a fast one.
ABSENT_PEER_PORT = 8099
UNREACHABLE = f"http://127.0.0.1:{ABSENT_PEER_PORT}"

# Venv packages: the union of every started service's own `[project].dependencies`, plus the two
# drivers production selects (postgres, redis). Read from the pyproject files at start, not listed
# here, so a dependency a service adds tomorrow is installed tomorrow.
_EXTRA_PACKAGES = ["asyncpg>=0.29,<1.0", "redis>=5.0,<6.0", "pyyaml"]


def _src(name: str, origin: str) -> Path:
    return (PLATFORM / "services" / name) if origin == "platform" else (ROOT / "services" / name)


def _db(name: str) -> str:
    return name.replace("-", "_")


# ── what one laptop cannot do the cluster's way ──────────────────────────────────────────────────
def _local_overrides(name: str, secret: dict[str, str]) -> dict[str, str]:
    over = {
        # DEVELOPMENT, NOT PRODUCTION — production's boot guards (rightly) refuse a null audit sink,
        # an HS256 verifier, an http:// peer; every one of those is a deliberate local trade below.
        "ENV": "development",
        "HOST": "127.0.0.1",
        "PORT": str(PORTS[name]),
        "LOG_LEVEL": "warning",
        # ONE SHARED HS256 SECRET instead of identity's rotating RS256 key + JWKS. The verifier
        # still checks every signature, issuer and audience for real; what changes is only which
        # algorithm, and it removes a key-rotation job and a JWKS fetch-allowlist from a laptop.
        "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": secret["TOKEN_HS256_SECRET"],
        "TOKEN_ISSUER": "raje3",
        "TOKEN_AUDIENCE": "raje3",
        "INTERNAL_SERVICE_TOKEN": secret["INTERNAL_SERVICE_TOKEN"],
        # The same value under the names some services read it by — the aliases gen-secrets.py
        # mints in the cluster (envFrom cannot key-remap, so the pod needs each name). Harmless on
        # a service that declares none of them: settings only bind fields they declare.
        "AUTHZ_INTERNAL_TOKEN": secret["INTERNAL_SERVICE_TOKEN"],
        "COMPLIANCE_INTERNAL_TOKEN": secret["INTERNAL_SERVICE_TOKEN"],
        "PII_SALT": secret["PII_SALT"],
        "SECRETS_KEK": secret["SECRETS_KEK"],
        "BACKUP_KEK": secret["BACKUP_KEK"],
        # audit-service is not run here. Fail-closed auditing against a peer that does not exist
        # would refuse every audited write in the product, which is a fact about this laptop, not
        # about the code under test.
        "AUDIT_SINK_DRIVER": "null",
        "AUDIT_FAIL_CLOSED": "false",
        # The seed runs real concurrency through a single IP; production's per-IP ceilings are for
        # the internet, not for one script on loopback.
        "RATELIMIT_MAX": "100000",
        "RATELIMIT_ROUTES": "[]",
        "CORS_ALLOWED_ORIGINS": "",
        "CORS_ALLOW_CREDENTIALS": "false",
        "EGRESS_ALLOWED_HOSTS": "127.0.0.1,localhost",
        "OBJECTSTORE_DRIVER": "local",
        "OBJECTSTORE_ROOT": str(STATE / "objectstore" / name),
        # The NLLB translation model lives on a cluster volume; nothing the demo seeds needs it.
        "TRANSLATION_ENGINE_DRIVER": "null",
        "PUBLIC_BASE_URL": "http://localhost:5174",
    }
    if name == "identity-service":
        over.update({
            "TOKEN_ISSUER_DRIVER": "hs256",
            "TOKEN_SIGNING_SECRET": secret["TOKEN_HS256_SECRET"],
            "TOKEN_KEY_ROTATION_ENABLED": "false",
            "OTP_SALT": secret["OTP_SALT"],
            "EMAIL_VERIFICATION_PEPPER": secret["EMAIL_VERIFICATION_PEPPER"],
            # compliance-service is not run here; the legal gate's own configured fail mode in
            # production is already "open", so turning enforcement off changes no outcome.
            "IDENTITY_LEGAL_ENFORCEMENT": "off",
            "NOTIFIER_DRIVER": "null",
        })
    if name == "api-gateway":
        over["TENANT_GATE_DRIVER"] = "tenant"
        # The action catalog fans out to every ADMIN_SERVICES entry, each with a fresh httpx client,
        # under a 3s deadline. On Windows building a client's SSL context costs ~0.2s ON the event
        # loop, so thirty targets serialise past the deadline and the LATER ones (operations among
        # them) silently vanish from the catalog. Measured, not guessed. Listing only what this
        # stack runs, with a roomier deadline, keeps every running service's actions in it.
        over["CATALOG_FETCH_TIMEOUT_SECONDS"] = "15"
    return over


def _only_running_admin_services(env: dict[str, str]) -> None:
    if "ADMIN_SERVICES" in env:
        keep = [p for p in env["ADMIN_SERVICES"].split(",") if p.split("=", 1)[0].strip() in PORTS]
        env["ADMIN_SERVICES"] = ",".join(keep)


def _rewrite(value: str, svc_dir: Path) -> str:
    def host(m: re.Match) -> str:
        port = PORTS.get(m.group(1))
        return f"http://127.0.0.1:{port}" if port else UNREACHABLE
    value = re.sub(r"http://([a-z][a-z0-9-]*):8000", host, value)
    # Container paths in the values files (`/app/data/roles.seed.json`) → the same file in the tree.
    return value.replace("/app/data/", f"{(svc_dir / 'data').as_posix()}/")


def build_env(name: str, origin: str, secret: dict[str, str]) -> dict[str, str]:
    import yaml
    svc_dir = _src(name, origin)
    values = yaml.safe_load((VALUES / f"{name}.values.yaml").read_text(encoding="utf-8")) or {}
    env = {k: _rewrite("" if v is None else str(v), svc_dir) for k, v in (values.get("env") or {}).items()}
    # THE CHART TURNS `drivers:` INTO *_DRIVER ENV — mirrored, so a service runs on exactly the
    # datastore/bus/cache kinds it runs on in the cluster (the event bus being Redis is what makes
    # a visit recorded at operations reach loyalty, reminders and insights at all).
    drivers = values.get("drivers") or {}
    for kind, var in (("datastore", "DATASTORE_DRIVER"), ("cache", "CACHE_DRIVER"),
                      ("eventbus", "EVENTBUS_DRIVER"), ("queue", "QUEUE_DRIVER"),
                      ("ratelimiter", "RATELIMITER_DRIVER")):
        if drivers.get(kind):
            env[var] = str(drivers[kind])
    if env.get("DATASTORE_DRIVER") == "postgres":
        env["DATASTORE_DSN"] = f"postgresql://{PG_USER}:{PG_PASSWORD}@127.0.0.1:{PG_PORT}/{_db(name)}"
    for var in ("CACHE_URL", "EVENTBUS_URL", "QUEUE_URL", "RATELIMIT_URL"):
        env[var] = REDIS_URL
    env.update(_local_overrides(name, secret))
    _only_running_admin_services(env)
    return env


# ── infrastructure ──────────────────────────────────────────────────────────────────────────────
def _docker(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], capture_output=True, text=True, check=check)


def _container_up(name: str, run_args: list[str]) -> None:
    state = _docker("inspect", "-f", "{{.State.Running}}", name, check=False)
    if state.returncode != 0:
        _docker("run", "-d", "--name", name, *run_args)
    elif state.stdout.strip() != "true":
        _docker("start", name)


def infra_up() -> None:
    _container_up(PG_CONTAINER, [
        "-e", f"POSTGRES_USER={PG_USER}", "-e", f"POSTGRES_PASSWORD={PG_PASSWORD}",
        "-p", f"127.0.0.1:{PG_PORT}:5432", "-v", f"{PG_VOLUME}:/var/lib/postgresql/data",
        "postgres:16-alpine", "-c", "max_connections=400"])
    _container_up(REDIS_CONTAINER, [
        "-p", f"127.0.0.1:{REDIS_PORT}:6379", "-v", f"{REDIS_VOLUME}:/data",
        "redis:7-alpine", "redis-server", "--appendonly", "yes"])
    # A REAL QUERY, TWICE IN A ROW — not `pg_isready`. On a brand-new volume the image's entrypoint
    # runs a temporary server for initdb, answers ready, then restarts into the real one; the first
    # query after a lone `pg_isready` landed in that restart and failed the whole boot (seen live).
    ok = 0
    for _ in range(120):
        q = _docker("exec", PG_CONTAINER, "psql", "-U", PG_USER, "-tAc", "SELECT 1", check=False)
        ok = ok + 1 if q.returncode == 0 else 0
        if ok >= 2:
            break
        time.sleep(1)
    else:
        raise SystemExit("postgres never became ready")
    have = _docker("exec", PG_CONTAINER, "psql", "-U", PG_USER, "-tAc",
                   "SELECT datname FROM pg_database").stdout.split()
    for name, _, _ in SERVICES:
        if _db(name) not in have:
            _docker("exec", PG_CONTAINER, "psql", "-U", PG_USER, "-c", f"CREATE DATABASE {_db(name)}")


def infra_down() -> None:
    for name in (PG_CONTAINER, REDIS_CONTAINER):
        _docker("stop", name, check=False)


def infra_reset() -> None:
    """Every local row gone — both containers AND their volumes — plus the demo-apps session files,
    which would otherwise name a shop that no longer exists and make the next seed fail its sign-in
    instead of opening a fresh one. The stack's own secrets are kept: nothing sealed with them
    survives the wipe, so there is no reason to mint new ones."""
    for name in (PG_CONTAINER, REDIS_CONTAINER):
        _docker("rm", "-f", name, check=False)
    for volume in (PG_VOLUME, REDIS_VOLUME):
        _docker("volume", "rm", volume, check=False)
    for f in (".demo-session.apps.json", ".demo-credentials.apps.json",
              ".demo-session.apps-partner.json", ".demo-credentials.apps-partner.json"):
        (HERE.parent / f).unlink(missing_ok=True)


def load_secrets() -> dict[str, str]:
    path = STATE / "secrets.json"
    keys = ("INTERNAL_SERVICE_TOKEN", "PII_SALT", "TOKEN_HS256_SECRET", "SECRETS_KEK", "BACKUP_KEK",
            "OTP_SALT", "EMAIL_VERIFICATION_PEPPER")
    have = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    # FILL, NEVER REPLACE — a key that already exists keeps its value for the life of the data
    # it pseudonymised or sealed (the same rule deploy/gen-secrets.py holds in the cluster).
    for k in keys:
        have.setdefault(k, secrets.token_hex(32))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(have, indent=2), encoding="utf-8")
    return have


def ensure_python() -> str:
    if os.environ.get("PYTHON"):
        return os.environ["PYTHON"]
    venv = STATE / "venv"
    py = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not py.exists():
        uv = shutil.which("uv")
        if not uv:
            raise SystemExit("needs `uv` on PATH (or PYTHON=<a python 3.12 with the services' deps>)")
        subprocess.run([uv, "venv", "--python", "3.12", str(venv)], check=True)
        import tomllib
        deps: set[str] = set(_EXTRA_PACKAGES)
        for name, origin, _ in SERVICES:
            proj = tomllib.loads((_src(name, origin) / "pyproject.toml").read_text(encoding="utf-8"))
            deps.update(proj.get("project", {}).get("dependencies", []))
        subprocess.run([uv, "pip", "install", "--python", str(py), *sorted(deps)], check=True)
    return str(py)


# ── the services ────────────────────────────────────────────────────────────────────────────────
def _absent_peer() -> None:
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Refuse(BaseHTTPRequestHandler):
        def _answer(self) -> None:
            body = b'{"detail":"this peer is not run by local_stack.py"}'
            self.send_response(503)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = _answer

        def log_message(self, *_: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", ABSENT_PEER_PORT), Refuse)
    threading.Thread(target=server.serve_forever, daemon=True).start()


def _healthy(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=2) as r:
            return r.status == 200
    except (urllib.error.URLError, OSError):
        return False


def seed_plans(secret: dict[str, str]) -> None:
    """deploy/seed/plans.json into billing — the same HTTP calls deploy/seed/seed-plans.sh makes in
    the cluster (a `_platform` token holding platform.billing, POST /api/v1/billing/plans), so the
    price list a local shop subscribes from is the real one, never a fixture. Create-only, like
    that script's default: an existing plan is left exactly as it is."""
    import jwt
    lib = json.loads((ROOT / "deploy" / "seed" / "plans.json").read_text(encoding="utf-8"))
    now = int(time.time())
    token = jwt.encode({"sub": "seed-plans", "tenant": "_platform",
                        "caps": ["platform.billing", "billing.manage"],
                        "iss": "raje3", "aud": "raje3", "iat": now, "exp": now + 300},
                       secret["TOKEN_HS256_SECRET"], algorithm="HS256")
    base = f"http://127.0.0.1:{PORTS['billing-service']}"

    def call(path: str, body: dict | None = None) -> tuple[int, dict]:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(base + path, data=data, method="POST" if data else "GET",
                                     headers={"Authorization": f"Bearer {token}",
                                              "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            return e.code, {"detail": e.read().decode()[:300]}

    status, out = call("/api/v1/billing/plans?include_hidden=true")
    if status >= 400:
        raise SystemExit(f"could not read billing's plans: {status} {out}")
    have = {p.get("name") for p in out.get("plans") or []}
    for plan in lib["plans"]:
        if plan["name"] in have:
            continue
        body = {"name": plan["name"], "limits": plan["limits"],
                "trial_days": plan.get("trial_days", 0),
                "credit_percent_of_price": bool(plan.get("credit_percent_of_price", False)),
                "prices": [{"interval": "month", "amount_minor": plan["amount"],
                            "currency": lib["currency"], "type": "flat", "includes_tax": True}]}
        status, res = call("/api/v1/billing/plans", body)
        if status >= 400:
            raise SystemExit(f"plan {plan['name']!r} refused: {status} {res}")
        if plan.get("listed") is False:
            call(f"/api/v1/billing/plans/{res['id']}/availability", {"listed": False})
        print(f"  + plan {plan['name']}")


# ── the scheduled jobs — what job-service does in the cluster ────────────────────────────────────
#
# THE PRODUCT HAS A HEARTBEAT, and a stack without it is quietly a different product: insights'
# snapshots, reminders' tick, loyalty's recovery of points whose visit event was missed — all of it
# runs because job-service fires these routes on a schedule. job-service is not run here, so this
# fires them instead, from the SAME table the cluster provisions them from
# (deploy/hooks/provision-cron-migrations.sh's ROUTES), signed the way job-service's dispatcher
# signs a push (HMAC over "<ts>.<body>", falling back to the shared internal token, which is what
# every receiver verifies against). A route whose service this stack does not run is skipped.
CRON_TABLE = ROOT / "deploy" / "hooks" / "provision-cron-migrations.sh"


def scheduled_jobs() -> list[dict[str, str]]:
    rows = re.findall(r'^\s*"([^"|]+)\|([^"|]+)\|([^"|]+)\|([^"|]+)\|([^"|:]+):\d+\|([^"|]+)"',
                      CRON_TABLE.read_text(encoding="utf-8"), re.MULTILINE)
    return [{"name": n, "cron": c, "queue": q, "type": t, "service": s, "path": p}
            for n, c, q, t, s, p in rows if s in PORTS]


def _cron_field(spec: str, value: int) -> bool:
    for part in spec.split(","):
        rng, _, step = part.partition("/")
        if rng == "*":
            lo, hi = 0, 10_000
        elif "-" in rng:
            lo, hi = (int(x) for x in rng.split("-"))
        else:
            lo = hi = int(rng)
            if step:                       # "6/10" means 6, 16, 26… — a start, then a step
                hi = 10_000
        if lo <= value <= hi and (value - lo) % int(step or 1) == 0:
            return True
    return False


def cron_due(cron: str, t: time.struct_time) -> bool:
    minute, hour, dom, month, dow = cron.split()
    return (_cron_field(minute, t.tm_min) and _cron_field(hour, t.tm_hour)
            and _cron_field(dom, t.tm_mday) and _cron_field(month, t.tm_mon)
            and _cron_field(dow, (t.tm_wday + 1) % 7))


def fire_job(job: dict[str, str], secret: dict[str, str]) -> int:
    import hashlib
    import hmac
    ts = int(time.time())
    body = json.dumps({"job": {"id": f"local-{job['name']}-{ts}", "queue": job["queue"],
                               "type": job["type"], "payload": {}}},
                      separators=(",", ":")).encode()
    sig = hmac.new(secret["INTERNAL_SERVICE_TOKEN"].encode(), f"{ts}.".encode() + body,
                   hashlib.sha256).hexdigest()
    req = urllib.request.Request(f"http://127.0.0.1:{PORTS[job['service']]}{job['path']}",
                                 data=body, method="POST", headers={
                                     "Content-Type": "application/json",
                                     "X-Internal-Token": secret["INTERNAL_SERVICE_TOKEN"],
                                     "X-Job-Signature": sig, "X-Job-Signature-Timestamp": str(ts)})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except (urllib.error.URLError, OSError):
        return 0


def _scheduler(secret: dict[str, str]) -> None:
    import threading

    def loop() -> None:
        jobs = scheduled_jobs()
        last = None
        reported: set[str] = set()
        while True:
            now = time.localtime()   # the cluster's crons run on the node clock; so does this one
            stamp = now[:5]
            if stamp != last:
                last = stamp
                for job in jobs:
                    if cron_due(job["cron"], now):
                        code = fire_job(job, secret)
                        # ONCE PER JOB, NOT EVERY MINUTE — the `*-jobs-run` drainers claim from
                        # job-service, which this stack does not run, so they fail by construction.
                        if (code >= 400 or code == 0) and job["name"] not in reported:
                            reported.add(job["name"])
                            print(f"  · job {job['name']} answered {code} (reported once)")
            time.sleep(5)

    threading.Thread(target=loop, daemon=True).start()


# THE SAME THROWAWAY PLATFORM ACCOUNT the tour scripts already sign in with (seed-demo-affiliate.mjs,
# admin-home tours) — a local-and-dev-only operator, not a secret. The demo seed signs in with it to
# do what only a platform operator may: settle a shop's invoice paid by transfer, show a hidden app.
ADMIN_PHONE = os.environ.get("ADMIN_PHONE", "0500000902")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "HomeTour2026Demo!")


def seed_platform_admin(secret: dict[str, str]) -> None:
    """Our operator roles under `_platform`, then one owner holding `platform-owner` — the calls
    deploy/seed/seed-roles.sh and deploy/seed/seed-admin.sh make in the cluster (authz's
    POST /api/v1/roles with a platform token; identity's /internal/tenancy/seed-owner), so the
    admin this stack has is shaped exactly like production's. Both are create-only."""
    import jwt
    now = int(time.time())
    token = jwt.encode({"sub": "seed-roles", "tenant": "_platform",
                        "caps": ["platform.authz", "authz.manage"],
                        "iss": "raje3", "aud": "raje3", "iat": now, "exp": now + 300},
                       secret["TOKEN_HS256_SECRET"], algorithm="HS256")

    def call(url: str, body: dict | None, headers: dict[str, str]) -> tuple[int, dict]:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method="POST" if data else "GET",
                                     headers={**headers, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            return e.code, {"detail": e.read().decode()[:300]}

    authz = f"http://127.0.0.1:{PORTS['authz-service']}/api/v1/roles"
    auth = {"Authorization": f"Bearer {token}"}
    status, out = call(authz, None, auth)
    have = {r.get("name") for r in (out.get("roles") or [])} if status < 400 else set()
    roles = json.loads((ROOT / "deploy" / "seed" / "operator-roles.json").read_text(encoding="utf-8"))["roles"]
    for role in roles:
        if role["name"] in have:
            continue
        status, out = call(authz, {"name": role["name"], "description": role.get("description", ""),
                                   "capabilities": role["capabilities"]}, auth)
        if status >= 400:
            raise SystemExit(f"platform role {role['name']!r} refused: {status} {out}")
    # ALREADY THERE IS ALREADY DONE — identity answers a second seed-owner on an owned tenant with
    # a refusal (it will not overwrite an owner, rightly), so the question asked first is the one
    # that matters: can the admin sign in?
    status, _ = call(f"http://127.0.0.1:{PORTS['identity-service']}/api/v1/auth/tenant",
                     {"tenant": "_platform", "username": ADMIN_PHONE, "password": ADMIN_PASSWORD}, {})
    if status == 200:
        return
    status, out = call(f"http://127.0.0.1:{PORTS['identity-service']}/internal/tenancy/seed-owner",
                       {"tenant": "_platform", "identifier": ADMIN_PHONE, "roles": ["platform-owner"],
                        "password": ADMIN_PASSWORD, "only_if_empty": True},
                       {"X-Internal-Token": secret["INTERNAL_SERVICE_TOKEN"]})
    if status not in (200, 201, 409):
        raise SystemExit(f"platform admin not seeded: {status} {out}")


def up() -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    (STATE / "logs").mkdir(exist_ok=True)
    print("▸ postgres + redis")
    infra_up()
    secret = load_secrets()
    python = ensure_python()
    _absent_peer()
    procs: list[tuple[str, subprocess.Popen]] = []

    def reap() -> None:
        for _, p in reversed(procs):
            if p.poll() is None:
                p.terminate()
        for _, p in procs:
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()

    def stop(*_: object) -> None:
        reap()
        raise SystemExit(0)

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    # ANY WAY OUT STOPS EVERY CHILD — a refused seed step raising mid-boot used to leave the
    # services already started running with nobody watching them, holding their ports, so the
    # next start found them "already answering" and silently kept the stale code.
    try:
        _boot(procs, python, secret, stop)
    finally:
        reap()


def _boot(procs: list, python: str, secret: dict[str, str], stop) -> None:
    for name, origin, port in SERVICES:
        if _healthy(port):
            print(f"  · {name} already answering on :{port} — left as is")
            continue
        env = {**os.environ, **build_env(name, origin, secret), "PYTHONDONTWRITEBYTECODE": "1",
               "PYTHONUTF8": "1"}
        log = open(STATE / "logs" / f"{name}.log", "a", encoding="utf-8")
        p = subprocess.Popen(
            [python, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port),
             "--app-dir", str(_src(name, origin)), "--no-access-log"],
            cwd=str(_src(name, origin)), env=env, stdout=log, stderr=subprocess.STDOUT)
        procs.append((name, p))
        for _ in range(120):
            if _healthy(port):
                break
            if p.poll() is not None:
                print(f"  ✗ {name} exited during boot — see {STATE / 'logs' / (name + '.log')}")
                raise SystemExit(1)
            time.sleep(0.5)
        else:
            print(f"  ✗ {name} never answered /healthz on :{port}")
            stop()
        print(f"  ✔ {name} on :{port}")
        if name == "billing-service":
            seed_plans(secret)
            seed_platform_admin(secret)

    _scheduler(secret)
    print(f"✔ stack up — gateway http://127.0.0.1:{GATEWAY_PORT}  (Ctrl-C stops everything)")
    while True:
        for name, p in procs:
            if p.poll() is not None:
                print(f"  ✗ {name} exited (code {p.returncode}) — see its log; stopping the stack")
                stop()
        time.sleep(2)


if __name__ == "__main__":
    # Line-buffered even when piped — run in the background, progress must reach the log as it happens.
    sys.stdout.reconfigure(line_buffering=True)
    cmd = sys.argv[1] if len(sys.argv) > 1 else "up"
    if cmd == "up":
        up()
    elif cmd == "down":
        infra_down()
    elif cmd == "reset":
        infra_reset()
    elif cmd == "run-job":
        # One scheduled job, now, against a running stack — e.g. `run-job insights-tick` to refresh
        # the dashboards right after a seed instead of waiting for its next scheduled slot.
        wanted = sys.argv[2:] or [j["name"] for j in scheduled_jobs()]
        secret = load_secrets()
        for job in scheduled_jobs():
            if job["name"] in wanted:
                print(f"{job['name']}: {fire_job(job, secret)}")
    else:
        raise SystemExit("usage: local_stack.py up|down|reset|run-job [name…]")
