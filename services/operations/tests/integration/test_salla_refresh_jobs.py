"""Salla token refresh via job-service — the two internal routes (scan + run), same split
campaigns' own `/campaigns/jobs/run` already established. A `_FakeJobService` stands in for
job-service itself (enqueue/claim/ack/nack all held in memory), the same way `_FakePlans` stands
in for billing-service elsewhere in this suite.
"""
from __future__ import annotations

import datetime as dt
import os
import time

import pytest
from fastapi.testclient import TestClient

TOKEN_SECRET = "h" * 40
ISS, AUD = "iss", "aud"
INTERNAL_TOKEN = "t" * 40
TENANT = "tnt_salla_refresh"


class _FakeJobService:
    """A minimal in-memory job-service — enough to prove the SCAN enqueues the right thing and
    RUN claims/acks/nacks correctly, without a real queue's own retry/backoff machinery (that
    machinery is job-service's own, already tested there)."""

    driver = "fake"

    def __init__(self) -> None:
        self.jobs: dict[str, dict] = {}
        self._seq = 0
        self.acked: list[tuple[str, dict]] = []
        self.nacked: list[tuple[str, str]] = []

    async def enqueue(self, *, queue: str, tenant: str, type: str, payload: dict,
                      delay_seconds: float = 0, unique_key: str = "") -> str:
        if unique_key:
            for job in self.jobs.values():
                if job.get("unique_key") == unique_key:
                    return job["id"]
        self._seq += 1
        job_id = f"job_{self._seq}"
        self.jobs[job_id] = {"id": job_id, "lease_token": f"lease_{job_id}", "queue": queue,
                             "tenant": tenant, "type": type, "payload": payload,
                             "unique_key": unique_key, "claimed": False}
        return job_id

    async def claim(self, *, worker: str, queue: str, batch: int = 1) -> list[dict]:
        out = []
        for job in self.jobs.values():
            if job["queue"] == queue and not job["claimed"]:
                job["claimed"] = True
                out.append(dict(job))
                if len(out) >= batch:
                    break
        return out

    async def ack(self, job_id: str, lease_token: str, result: dict | None = None) -> None:
        self.acked.append((job_id, result or {}))
        self.jobs.pop(job_id, None)

    async def nack(self, job_id: str, lease_token: str, error: str = "") -> None:
        self.nacked.append((job_id, error))
        if job_id in self.jobs:
            self.jobs[job_id]["claimed"] = False


def _make_app() -> TestClient:
    from app.config import get_settings

    os.environ.update({
        "ENV": "test",
        "INTERNAL_SERVICE_TOKEN": INTERNAL_TOKEN,
        "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": TOKEN_SECRET,
        "TOKEN_ISSUER": ISS,
        "TOKEN_AUDIENCE": AUD,
        "RATELIMIT_MAX": "1000",
        "PII_SALT": "s" * 32,
        "PUBLIC_BASE_URL": "https://raje3.sa",
        "SALLA_CLIENT_ID": "cid",
        "SALLA_CLIENT_SECRET": "csecret",
        "SALLA_WEBHOOK_SECRET": "wsecret",
    })
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture
def env_guard():
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
    from app.config import get_settings
    get_settings.cache_clear()


@pytest.fixture
def client(env_guard) -> TestClient:
    c = _make_app()
    c.app.state.container.jobs = _FakeJobService()
    return c


def _internal_headers() -> dict:
    """`push_headers(b"")` matches every real call site below: none of the salla routes take a
    body, so the raw request bytes a real POST-with-no-body sends are always empty."""
    import hashlib
    import hmac
    import time

    from app.core.push_verify import SIGNATURE_HEADER, TIMESTAMP_HEADER

    ts = int(time.time())
    sig = hmac.new(INTERNAL_TOKEN.encode("utf-8"), f"{ts}.".encode("utf-8"),
                   hashlib.sha256).hexdigest()
    return {"X-Internal-Token": INTERNAL_TOKEN, SIGNATURE_HEADER: sig,
           TIMESTAMP_HEADER: str(ts)}


def _connect(client: TestClient, *, tenant: str, expires_in: int, merchant_id: str = "42") -> None:
    import asyncio
    asyncio.run(client.app.state.container.salla.save_connection(
        tenant=tenant, merchant_id=merchant_id, store_name="متجري",
        access_token="at_old", refresh_token="rt_old",
        expires_at=int(time.time()) + expires_in, scope="offline_access"))


# ── the scan ─────────────────────────────────────────────────────────────────────────────────
def test_scan_enqueues_a_connection_expiring_soon(client):
    _connect(client, tenant=TENANT, expires_in=3600)   # one hour left — well inside the margin
    r = client.post("/internal/operations/salla/refresh-scan", headers=_internal_headers())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["scanned"] == 1
    assert body["enqueued"] == 1

    jobs = client.app.state.container.jobs.jobs
    assert len(jobs) == 1
    job = next(iter(jobs.values()))
    assert job["tenant"] == TENANT
    assert job["queue"] == "salla"
    assert job["type"] == "salla.refresh_token"


def test_scan_never_enqueues_a_connection_with_plenty_of_time_left(client):
    _connect(client, tenant=TENANT, expires_in=30 * 24 * 3600)   # 30 days — well outside margin
    r = client.post("/internal/operations/salla/refresh-scan", headers=_internal_headers())
    assert r.json() == {"scanned": 0, "enqueued": 0, "unavailable": 0}


def test_scan_is_idempotent_for_the_same_connection_state(client):
    """Running the scan twice before anything refreshes must not enqueue a second job — the
    unique_key is scoped to the connection's current expires_at."""
    _connect(client, tenant=TENANT, expires_in=3600)
    client.post("/internal/operations/salla/refresh-scan", headers=_internal_headers())
    client.post("/internal/operations/salla/refresh-scan", headers=_internal_headers())
    assert len(client.app.state.container.jobs.jobs) == 1


def test_scan_requires_the_internal_token(client):
    r = client.post("/internal/operations/salla/refresh-scan")
    assert r.status_code in (401, 403)


def test_scan_refuses_without_a_push_signature_even_with_a_valid_internal_token(client):
    r = client.post("/internal/operations/salla/refresh-scan",
                    headers={"X-Internal-Token": INTERNAL_TOKEN})
    assert r.status_code == 401


def test_scan_reports_unavailable_when_job_service_is_not_configured(env_guard):
    from app.config import get_settings

    os.environ.update({
        "ENV": "test", "INTERNAL_SERVICE_TOKEN": INTERNAL_TOKEN,
        "TOKEN_VERIFIER_DRIVER": "hs256", "TOKEN_HS256_SECRET": TOKEN_SECRET,
        "TOKEN_ISSUER": ISS, "TOKEN_AUDIENCE": AUD, "RATELIMIT_MAX": "1000",
        "PII_SALT": "s" * 32, "PUBLIC_BASE_URL": "https://raje3.sa",
    })
    get_settings.cache_clear()
    from app.main import create_app

    c = TestClient(create_app(), raise_server_exceptions=False)   # real NullJobService, no fake
    import asyncio
    asyncio.run(c.app.state.container.salla.save_connection(
        tenant=TENANT, merchant_id="1", store_name="م", access_token="a", refresh_token="r",
        expires_at=int(time.time()) + 3600, scope=""))
    r = c.post("/internal/operations/salla/refresh-scan", headers=_internal_headers())
    assert r.json() == {"scanned": 1, "enqueued": 0, "unavailable": 1}


# ── the run ──────────────────────────────────────────────────────────────────────────────────
def test_run_refreshes_a_claimed_job_and_saves_the_new_tokens(client):
    _connect(client, tenant=TENANT, expires_in=3600)
    jobs = client.app.state.container.jobs
    import asyncio
    asyncio.run(jobs.enqueue(queue="salla", tenant=TENANT, type="salla.refresh_token",
                             payload={}, unique_key="k1"))

    client.app.state.container.salla.client.refresh = lambda refresh_token: {
        "access_token": "at_new", "refresh_token": "rt_new", "expires": 1209599,
    }

    r = client.post("/internal/operations/salla/jobs/run", headers=_internal_headers())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["claimed"] == 1
    assert body["refreshed"] == 1
    assert body["failed"] == 0
    assert len(jobs.acked) == 1
    assert len(jobs.nacked) == 0

    conn = asyncio.run(client.app.state.container.salla.connection_for(TENANT))
    assert conn.access_token == "at_new"
    assert conn.refresh_token == "rt_new"
    assert conn.merchant_id == "42", "everything but the tokens must survive the refresh"


def test_run_nacks_when_salla_refuses_the_refresh(client):
    _connect(client, tenant=TENANT, expires_in=3600)
    jobs = client.app.state.container.jobs
    import asyncio
    asyncio.run(jobs.enqueue(queue="salla", tenant=TENANT, type="salla.refresh_token",
                             payload={}, unique_key="k1"))
    client.app.state.container.salla.client.refresh = lambda refresh_token: None

    r = client.post("/internal/operations/salla/jobs/run", headers=_internal_headers())
    body = r.json()
    assert body["failed"] == 1
    assert body["refreshed"] == 0
    assert len(jobs.nacked) == 1

    conn = asyncio.run(client.app.state.container.salla.connection_for(TENANT))
    assert conn.access_token == "at_old", "a failed refresh must never overwrite a working token"


def test_run_nacks_when_salla_returns_no_new_refresh_token(client):
    """Salla rotates the refresh token on every call — a response missing one must be treated as
    a failure, never silently keep using the (now invalid) old one."""
    _connect(client, tenant=TENANT, expires_in=3600)
    jobs = client.app.state.container.jobs
    import asyncio
    asyncio.run(jobs.enqueue(queue="salla", tenant=TENANT, type="salla.refresh_token",
                             payload={}, unique_key="k1"))
    client.app.state.container.salla.client.refresh = lambda refresh_token: {
        "access_token": "at_new", "expires": 1209599,   # no refresh_token in the response
    }

    r = client.post("/internal/operations/salla/jobs/run", headers=_internal_headers())
    assert r.json()["failed"] == 1
    conn = asyncio.run(client.app.state.container.salla.connection_for(TENANT))
    assert conn.refresh_token == "rt_old"


def test_run_acks_as_skipped_when_the_connection_no_longer_exists(client):
    jobs = client.app.state.container.jobs
    import asyncio
    asyncio.run(jobs.enqueue(queue="salla", tenant="tnt_gone", type="salla.refresh_token",
                             payload={}, unique_key="k1"))

    r = client.post("/internal/operations/salla/jobs/run", headers=_internal_headers())
    body = r.json()
    assert body["skipped"] == 1
    assert body["failed"] == 0
    assert len(jobs.acked) == 1


def test_run_requires_the_internal_token(client):
    r = client.post("/internal/operations/salla/jobs/run")
    assert r.status_code in (401, 403)


def test_run_refuses_without_a_push_signature_even_with_a_valid_internal_token(client):
    r = client.post("/internal/operations/salla/jobs/run",
                    headers={"X-Internal-Token": INTERNAL_TOKEN})
    assert r.status_code == 401


def test_run_is_a_harmless_noop_when_job_service_is_not_configured(env_guard):
    from app.config import get_settings

    os.environ.update({
        "ENV": "test", "INTERNAL_SERVICE_TOKEN": INTERNAL_TOKEN,
        "TOKEN_VERIFIER_DRIVER": "hs256", "TOKEN_HS256_SECRET": TOKEN_SECRET,
        "TOKEN_ISSUER": ISS, "TOKEN_AUDIENCE": AUD, "RATELIMIT_MAX": "1000",
        "PII_SALT": "s" * 32, "PUBLIC_BASE_URL": "https://raje3.sa",
    })
    get_settings.cache_clear()
    from app.main import create_app

    c = TestClient(create_app(), raise_server_exceptions=False)
    r = c.post("/internal/operations/salla/jobs/run", headers=_internal_headers())
    assert r.status_code == 200
    assert r.json() == {"claimed": 0, "refreshed": 0, "skipped": 0, "failed": 0}
