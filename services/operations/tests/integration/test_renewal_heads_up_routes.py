"""POST /internal/operations/subscriptions/renewal-heads-up/scan and .../jobs/run — see
app/core/renewal_heads_up.py."""
from __future__ import annotations

from tests.conftest import INTERNAL_TOKEN, push_headers

TENANT = "renewsoon_ops_shop"


def _headers():
    return {"X-Internal-Token": INTERNAL_TOKEN, **push_headers(b"")}


class _FakeReader:
    def __init__(self, subs: list[dict]) -> None:
        self._subs = subs
        self.calls = 0

    async def page(self, *, within_seconds, cursor="", limit=200):
        self.calls += 1
        return {"subscriptions": self._subs, "next_cursor": ""}


class _FakeJobs:
    def __init__(self, *, claimed=None) -> None:
        self.enqueued: list[dict] = []
        self._claimed = claimed or []
        self.acked: list[tuple] = []
        self.nacked: list[tuple] = []

    async def enqueue(self, *, queue, tenant, type, payload, unique_key):
        self.enqueued.append({"queue": queue, "tenant": tenant, "payload": payload})
        return "job_1"

    async def claim(self, *, worker, queue, batch):
        return self._claimed

    async def ack(self, job_id, lease_token, result=None):
        self.acked.append((job_id, result))

    async def nack(self, job_id, lease_token, error=""):
        self.nacked.append((job_id, error))


class _FakeNotifier:
    def __init__(self, *, sent=True) -> None:
        self._sent = sent
        self.calls: list[dict] = []

    async def trigger(self, *, tenant, subscription_id, period_end):
        self.calls.append({"tenant": tenant, "subscription_id": subscription_id})
        return self._sent


def _swap(client, *, reader=None, jobs=None, notifier=None):
    c = client.app.state.container
    saved = (c.renewing_soon, c.jobs, c.renewal_heads_up_notifier)
    if reader is not None:
        c.renewing_soon = reader
    if jobs is not None:
        c.jobs = jobs
    if notifier is not None:
        c.renewal_heads_up_notifier = notifier
    return saved


def _restore(client, saved):
    c = client.app.state.container
    c.renewing_soon, c.jobs, c.renewal_heads_up_notifier = saved


def test_scan_enqueues_every_real_row(client):
    reader = _FakeReader([{"id": "sub_1", "tenant": TENANT, "current_period_end": 999999999}])
    jobs = _FakeJobs()
    saved = _swap(client, reader=reader, jobs=jobs)
    try:
        r = client.post("/internal/operations/subscriptions/renewal-heads-up/scan",
                        headers=_headers())
        assert r.status_code == 200
        assert r.json() == {"scanned": 1, "enqueued": 1, "unavailable": 0}
        assert len(jobs.enqueued) == 1
    finally:
        _restore(client, saved)


def test_jobs_run_claims_and_acks(client):
    claimed = [{"id": "j1", "lease_token": "lt1",
               "payload": {"tenant": TENANT, "subscription_id": "sub_1", "period_end": 1}}]
    jobs = _FakeJobs(claimed=claimed)
    notifier = _FakeNotifier(sent=True)
    saved = _swap(client, jobs=jobs, notifier=notifier)
    try:
        r = client.post("/internal/operations/subscriptions/renewal-heads-up/jobs/run",
                        headers=_headers())
        assert r.status_code == 200
        assert r.json() == {"claimed": 1, "sent": 1, "skipped": 0, "failed": 0}
        assert jobs.acked == [("j1", {"sent": True})]
    finally:
        _restore(client, saved)


def test_scan_requires_the_internal_token(client):
    r = client.post("/internal/operations/subscriptions/renewal-heads-up/scan")
    assert r.status_code in (401, 403)


def test_jobs_run_requires_the_internal_token(client):
    r = client.post("/internal/operations/subscriptions/renewal-heads-up/jobs/run")
    assert r.status_code in (401, 403)


def test_scan_refuses_without_a_push_signature_even_with_a_valid_internal_token(client):
    r = client.post("/internal/operations/subscriptions/renewal-heads-up/scan",
                    headers={"X-Internal-Token": INTERNAL_TOKEN})
    assert r.status_code == 401


def test_jobs_run_refuses_without_a_push_signature_even_with_a_valid_internal_token(client):
    r = client.post("/internal/operations/subscriptions/renewal-heads-up/jobs/run",
                    headers={"X-Internal-Token": INTERNAL_TOKEN})
    assert r.status_code == 401
