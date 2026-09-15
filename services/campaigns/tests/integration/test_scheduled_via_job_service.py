"""A future `fire_at`, for any goal, delegates to job-service instead of firing inline or waiting
on `/internal/campaigns/tick`'s own 15-minute scan (2026-09-12).
"""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

SECRET = "h" * 40
ISS = "iss"
AUD = "aud"
INTERNAL_TOKEN = "t" * 40


def push_headers(body: bytes) -> dict[str, str]:
    """A genuine job-service push signature over `body`, verifiable against
    INTERNAL_SERVICE_TOKEN (the default `require_push_signature` falls back to) — needed on top
    of X-Internal-Token for /internal/campaigns/jobs/run since 2026-09-16's push-dispatch
    migration."""
    import hashlib
    import hmac
    import time

    from app.core.push_verify import SIGNATURE_HEADER, TIMESTAMP_HEADER

    ts = int(time.time())
    signed = f"{ts}.".encode("utf-8") + body
    sig = hmac.new(INTERNAL_TOKEN.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return {SIGNATURE_HEADER: sig, TIMESTAMP_HEADER: str(ts)}


class FakeJobs:
    def __init__(self):
        self.enqueued: list[dict] = []
        self.claimable: list[dict] = []
        self.acked: list[tuple] = []
        self.nacked: list[tuple] = []
        self.requeued: list[dict] = []

    async def enqueue(self, *, queue, tenant, type, payload, delay_seconds=0, unique_key=""):
        row = {"queue": queue, "tenant": tenant, "type": type, "payload": payload,
              "delay_seconds": delay_seconds, "unique_key": unique_key}
        self.enqueued.append(row)
        if type == "campaigns.fire" and unique_key.startswith("cmp-fire-cont:"):
            self.requeued.append(row)
        return "job_1"

    async def claim(self, *, worker, queue, batch=1):
        out = self.claimable
        self.claimable = []
        return out

    async def ack(self, job_id, lease_token, result=None):
        self.acked.append((job_id, lease_token, result))

    async def nack(self, job_id, lease_token, error=""):
        self.nacked.append((job_id, lease_token, error))


@pytest.fixture
def client():
    from app.config import get_settings

    saved = dict(os.environ)
    os.environ.update({
        "ENV": "test", "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256", "TOKEN_HS256_SECRET": SECRET,
        "TOKEN_ISSUER": ISS, "TOKEN_AUDIENCE": AUD, "RATELIMIT_MAX": "1000",
    })
    get_settings.cache_clear()
    from app.main import create_app

    app = create_app()
    from app.adapters.peers import NullTemplates
    app.state.container.templates = NullTemplates([
        {"type": "mkt_announcement", "name": "mkt_announcement", "fills": ["owner"],
         "body": "{{1}} — {{2}}"},
    ])
    fake = FakeJobs()
    app.state.container.jobs = fake
    app.state.jobs_fake = fake
    yield app, TestClient(app, raise_server_exceptions=False)
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


def _auth(tenant="tnt_sched"):
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "u1", "iss": ISS, "aud": AUD, "tenant": tenant,
                      "caps": ["campaigns.read", "campaigns.manage"],
                      "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


def test_a_future_fire_at_on_an_ordinary_manual_goal_is_handed_to_job_service_not_fired_inline(client):
    """«أعلن جديدك» is `manual` trigger — today's, pre-2026-09-12 code fired it inline the moment
    it was created regardless of `fire_at`. A month-out National Day announcement must not go out
    the instant it is saved."""
    app, http = client
    future = int(dt.datetime.now(dt.timezone.utc).timestamp()) + 30 * 86_400
    r = http.post("/api/v1/campaigns",
                  json={"goal": "announce", "owner_text": "احتفل معنا باليوم الوطني",
                       "fire_at": future},
                  headers=_auth())
    assert r.status_code in (200, 201), r.text
    assert r.json()["run"] is None, "must not have fired inline"

    fake = app.state.jobs_fake
    assert len(fake.enqueued) == 1
    job = fake.enqueued[0]
    assert job["type"] == "campaigns.fire"
    assert job["queue"] == "campaigns"
    assert job["tenant"] == "tnt_sched"
    assert abs(job["delay_seconds"] - 30 * 86_400) < 5
    assert job["unique_key"].startswith("cmp-fire:")

    cid = r.json()["campaign"]["id"]
    listed = http.get("/api/v1/campaigns", headers=_auth())
    row = next(c for c in listed.json()["campaigns"] if c["id"] == cid)
    assert row["state"] == "active"
    assert row["last_evaluated"] == 0


def test_creation_still_succeeds_even_if_job_service_enqueue_fails(client):
    """Best-effort — job-service being unreachable must never block the campaign from existing;
    tick.py's own scan is still the fallback once fire_at actually passes."""
    app, http = client

    class _Boom:
        async def enqueue(self, **kw):
            raise RuntimeError("job-service unreachable")
        async def claim(self, **kw):
            return []
        async def ack(self, *a, **kw):
            pass
        async def nack(self, *a, **kw):
            pass

    app.state.container.jobs = _Boom()
    future = int(dt.datetime.now(dt.timezone.utc).timestamp()) + 3600
    r = http.post("/api/v1/campaigns",
                  json={"goal": "announce", "owner_text": "افتتحنا اليوم", "fire_at": future},
                  headers=_auth())
    assert r.status_code in (200, 201), r.text


def test_jobs_run_refuses_without_a_push_signature_even_with_a_valid_internal_token(client):
    app, http = client
    r = http.post("/internal/campaigns/jobs/run", headers={"X-Internal-Token": INTERNAL_TOKEN})
    assert r.status_code == 401


def test_tick_refuses_without_a_push_signature(client):
    app, http = client
    r = http.post("/internal/campaigns/tick", json={},
                  headers={"X-Internal-Token": INTERNAL_TOKEN})
    assert r.status_code == 401


def test_tick_with_a_valid_push_signature_succeeds(client):
    app, http = client
    r = http.post("/internal/campaigns/tick", json={},
                  headers={"X-Internal-Token": INTERNAL_TOKEN, **push_headers(b"{}")})
    assert r.status_code == 200, r.text


def test_internal_jobs_run_fires_a_claimed_due_campaign(client):
    app, http = client
    r = http.post("/api/v1/campaigns",
                  json={"goal": "announce", "owner_text": "خبر عاجل",
                       "fire_at": int(dt.datetime.now(dt.timezone.utc).timestamp()) + 3600},
                  headers=_auth())
    cid = r.json()["campaign"]["id"]

    fake = app.state.jobs_fake
    fake.claimable = [{"id": "job_x", "lease_token": "lt_x", "tenant": "tnt_sched",
                      "payload": {"campaign_id": cid}}]

    run_r = http.post("/internal/campaigns/jobs/run",
                      headers={"X-Internal-Token": INTERNAL_TOKEN, **push_headers(b"")})
    assert run_r.status_code == 200, run_r.text
    assert run_r.json()["claimed"] == 1
    assert len(fake.acked) == 1
    assert fake.acked[0][0] == "job_x"


def test_internal_jobs_run_skips_a_campaign_that_was_paused_since_scheduling(client):
    app, http = client
    r = http.post("/api/v1/campaigns",
                  json={"goal": "announce", "owner_text": "خبر عاجل",
                       "fire_at": int(dt.datetime.now(dt.timezone.utc).timestamp()) + 3600},
                  headers=_auth())
    cid = r.json()["campaign"]["id"]
    http.post(f"/api/v1/campaigns/{cid}/pause", headers=_auth())

    fake = app.state.jobs_fake
    fake.claimable = [{"id": "job_y", "lease_token": "lt_y", "tenant": "tnt_sched",
                      "payload": {"campaign_id": cid}}]
    run_r = http.post("/internal/campaigns/jobs/run",
                      headers={"X-Internal-Token": INTERNAL_TOKEN, **push_headers(b"")})
    assert run_r.status_code == 200, run_r.text
    assert len(fake.acked) == 1
    assert fake.acked[0][2] == {"skipped": "not_active"}
