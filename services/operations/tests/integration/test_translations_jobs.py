"""Shop-content translation via job-service (phase 3) — the two internal routes (scan + run),
same split `test_salla_refresh_jobs.py`'s own header already established. `_FakeJobService` is
copied from that file (a project-wide convention would be nice; this mirrors it deliberately
rather than importing across test files). `_FakeEngine` stands in for a real NLLB model —
`NullTranslationEngine` is exercised directly (it needs no fake), and the two integration-shaped
hard cases (staleness, a missing entity) plus a partial-result and an unavailable-engine case are
each their own test, matching this suite's "one behaviour per test" convention.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import hmac
import os
import time

import pytest
from fastapi.testclient import TestClient

TOKEN_SECRET = "h" * 40
ISS, AUD = "iss", "aud"
INTERNAL_TOKEN = "t" * 40
TENANT = "tnt_translations"


class _FakeJobService:
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


class _FakeEngine:
    """`driver` is deliberately NOT "null" — the route only special-cases `NullTranslationEngine`
    by isinstance, so this needs its own distinct class to be treated as "a real engine" by the
    route under test."""

    driver = "fake"

    def __init__(self, answers: dict[str, dict[str, str]] | None = None,
                broken: bool = False) -> None:
        # keyed by source text, so the same fake can answer differently per call in one test
        self.answers = answers or {}
        self.broken = broken
        self.calls: list[tuple[str, list[str]]] = []

    def translate(self, text: str, target_locales: list[str]) -> dict[str, str]:
        self.calls.append((text, list(target_locales)))
        if self.broken:
            from app.core.translation_engine import TranslationEngineUnavailable
            raise TranslationEngineUnavailable("fake engine is broken")
        return dict(self.answers.get(text, {}))


def _make_app() -> TestClient:
    from app.config import get_settings

    os.environ.update({
        "ENV": "test", "INTERNAL_SERVICE_TOKEN": INTERNAL_TOKEN, "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": TOKEN_SECRET, "TOKEN_ISSUER": ISS, "TOKEN_AUDIENCE": AUD,
        "RATELIMIT_MAX": "1000", "PII_SALT": "s" * 32,
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
    ts = int(time.time())
    sig = hmac.new(INTERNAL_TOKEN.encode("utf-8"), f"{ts}.".encode("utf-8"),
                   hashlib.sha256).hexdigest()
    from app.core.push_verify import SIGNATURE_HEADER, TIMESTAMP_HEADER
    return {"X-Internal-Token": INTERNAL_TOKEN, SIGNATURE_HEADER: sig, TIMESTAMP_HEADER: str(ts)}


def _seed_service(client: TestClient, *, tenant: str = TENANT, name: str = "غسيل خارجي") -> str:
    from app.core.models import Service
    from app.core.stores import ServiceStore

    async def go() -> str:
        svc = Service(id="svc_1", tenant=tenant, name=name)
        await ServiceStore(client.app.state.container.datastore).save(svc)
        return svc.id

    return asyncio.run(go())


def _entry(client: TestClient, tenant: str = TENANT):
    from app.core.stores import TranslationStore

    async def go():
        return await TranslationStore(client.app.state.container.datastore).get(
            tenant, "service", "svc_1", "name")

    return asyncio.run(go())


# ── the scan ─────────────────────────────────────────────────────────────────────────────────
def test_scan_enqueues_one_job_per_pending_field(client):
    _seed_service(client)
    r = client.post("/internal/operations/translations/scan", headers=_internal_headers())
    assert r.status_code == 200, r.text
    assert r.json() == {"scanned": 1, "enqueued": 1, "unavailable": 0}
    jobs = client.app.state.container.jobs.jobs
    assert len(jobs) == 1
    job = next(iter(jobs.values()))
    assert job["tenant"] == TENANT
    assert job["queue"] == "translations"
    assert job["payload"]["entity_type"] == "service"
    assert job["payload"]["field"] == "name"


def test_scan_is_idempotent_for_the_same_unchanged_text(client):
    _seed_service(client)
    client.post("/internal/operations/translations/scan", headers=_internal_headers())
    client.post("/internal/operations/translations/scan", headers=_internal_headers())
    assert len(client.app.state.container.jobs.jobs) == 1


def test_scan_finds_nothing_with_no_shop_content_yet(client):
    r = client.post("/internal/operations/translations/scan", headers=_internal_headers())
    assert r.json() == {"scanned": 0, "enqueued": 0, "unavailable": 0}


# ── the run: the ordinary path ──────────────────────────────────────────────────────────────
def test_run_translates_every_target_locale_and_marks_the_entry_done(client):
    _seed_service(client)
    client.post("/internal/operations/translations/scan", headers=_internal_headers())

    fake = _FakeEngine(answers={"غسيل خارجي": {
        "en": "Exterior wash", "ur": "بیرونی دھلائی", "ha": "Wanki na waje",
        "fil": "Panlabas na paghuhugas", "bn": "বাহ্যিক ধোয়া"}})
    client.app.state.container.translation_engine = fake

    r = client.post("/internal/operations/translations/jobs/run", headers=_internal_headers())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["claimed"] == 1 and body["translated"] == 1 and body["failed"] == 0

    entry = _entry(client)
    assert entry.status == "done"
    assert entry.translations["en"] == "Exterior wash"
    assert entry.translations["ur"] == "بیرونی دھلائی"
    assert client.app.state.container.jobs.acked and not client.app.state.container.jobs.nacked


def test_run_with_no_pending_jobs_never_touches_the_engine(client):
    """Nothing enqueued — `claim()` returns empty, the loop body (where the model would first be
    touched) never runs. Proven here by a `_FakeEngine` that records every call it receives."""
    fake = _FakeEngine()
    client.app.state.container.translation_engine = fake
    r = client.post("/internal/operations/translations/jobs/run", headers=_internal_headers())
    assert r.json()["claimed"] == 0
    assert fake.calls == []


def test_run_is_a_silent_no_op_with_the_default_null_engine(client):
    _seed_service(client)
    client.post("/internal/operations/translations/scan", headers=_internal_headers())
    r = client.post("/internal/operations/translations/jobs/run", headers=_internal_headers())
    assert r.json() == {"claimed": 0, "translated": 0, "stale": 0, "failed": 0}
    # the job is untouched — still sitting there for whenever a real engine is wired
    assert len(client.app.state.container.jobs.jobs) == 1


# ── the hard cases ───────────────────────────────────────────────────────────────────────────
def test_a_second_edit_before_the_worker_runs_makes_the_first_job_stale_not_overwritten(client):
    """THE compare-and-swap case `TranslationStore.write_result`'s own docstring exists for: the
    shop edits the SAME field again after the scan enqueued a job for the old text. The worker
    must never resurrect the old translation over the shop's newer, still-untranslated text."""
    _seed_service(client, name="غسيل خارجي")
    client.post("/internal/operations/translations/scan", headers=_internal_headers())

    # the owner changes his mind about the name before the job ever runs
    _seed_service(client, name="غسيل خارجي فاخر")

    fake = _FakeEngine(answers={"غسيل خارجي": {"en": "Exterior wash"}})
    client.app.state.container.translation_engine = fake
    r = client.post("/internal/operations/translations/jobs/run", headers=_internal_headers())
    body = r.json()
    assert body["claimed"] == 1 and body["stale"] == 1 and body["translated"] == 0

    entry = _entry(client)
    assert entry.source_text == "غسيل خارجي فاخر"
    assert entry.status == "pending"
    assert entry.translations == {}
    assert client.app.state.container.jobs.acked   # a stale skip is acked, never retried forever


def test_the_entity_disappearing_before_the_worker_runs_is_acked_not_failed(client):
    _seed_service(client)
    client.post("/internal/operations/translations/scan", headers=_internal_headers())

    from app.core.stores import TranslationStore
    asyncio.run(TranslationStore(client.app.state.container.datastore)._s.delete(
        "translations", f"{TENANT}|service:svc_1:name"))

    fake = _FakeEngine(answers={"غسيل خارجي": {"en": "Exterior wash"}})
    client.app.state.container.translation_engine = fake
    r = client.post("/internal/operations/translations/jobs/run", headers=_internal_headers())
    body = r.json()
    assert body["claimed"] == 1 and body["stale"] == 1 and body["failed"] == 0
    assert client.app.state.container.jobs.acked


def test_a_partial_result_is_stored_but_the_entry_stays_pending_for_a_retry(client):
    _seed_service(client)
    client.post("/internal/operations/translations/scan", headers=_internal_headers())

    # only 2 of the 5 target locales answered — a real, if unusual, model outcome
    fake = _FakeEngine(answers={"غسيل خارجي": {"en": "Exterior wash", "ur": "بیرونی دھلائی"}})
    client.app.state.container.translation_engine = fake
    client.post("/internal/operations/translations/jobs/run", headers=_internal_headers())

    entry = _entry(client)
    assert entry.status == "pending"
    assert entry.translations == {"en": "Exterior wash", "ur": "بیرونی دھلائی"}
    # acked, not nacked — a partial success is not an error; a later scan/run pair (the entry is
    # still `pending`) simply tries again, this time only for the still-missing locales' worth of
    # value (the engine itself always re-translates all of them, which is fine — idempotent).
    assert client.app.state.container.jobs.acked


def test_an_unavailable_engine_nacks_the_whole_claimed_batch_without_trying_each_one(client):
    _seed_service(client, name="غسيل خارجي")
    client.post("/internal/operations/translations/scan", headers=_internal_headers())
    from app.core.models import Service
    from app.core.stores import ServiceStore
    asyncio.run(ServiceStore(client.app.state.container.datastore).save(
        Service(id="svc_2", tenant=TENANT, name="تلميع")))
    client.post("/internal/operations/translations/scan", headers=_internal_headers())

    fake = _FakeEngine(broken=True)
    client.app.state.container.translation_engine = fake
    r = client.post("/internal/operations/translations/jobs/run", headers=_internal_headers())
    body = r.json()
    assert body["claimed"] == 2 and body["failed"] == 2 and body["translated"] == 0
    assert len(client.app.state.container.jobs.nacked) == 2
    assert not client.app.state.container.jobs.acked


# ── server-load gating ──────────────────────────────────────────────────────────────────────
def test_run_refuses_to_claim_anything_when_the_server_is_busy(client, monkeypatch):
    _seed_service(client)
    client.post("/internal/operations/translations/scan", headers=_internal_headers())

    monkeypatch.setattr("app.core.server_load.is_idle", lambda threshold=0.7: False)
    fake = _FakeEngine(answers={"غسيل خارجي": {"en": "Exterior wash"}})
    client.app.state.container.translation_engine = fake

    r = client.post("/internal/operations/translations/jobs/run", headers=_internal_headers())
    body = r.json()
    assert body["claimed"] == 0 and body.get("skipped") == "server_busy"
    assert fake.calls == []
    # untouched — still there for the next, hopefully quieter, firing
    assert len(client.app.state.container.jobs.jobs) == 1
