"""core/renewal_heads_up.py — the daily read-only scan + durable claim loop that turns a
"renewing soon" billing row into a real WhatsApp heads-up."""
from __future__ import annotations

import asyncio

from app.core.renewal_heads_up import (RenewingSoonReader, WhatsAppHeadsUpNotifier,
                                       run_claimed_jobs, scan)


def run(c):
    return asyncio.run(c)


class _FakeReader:
    def __init__(self, pages: list[dict]) -> None:
        self._pages = pages
        self.calls: list[dict] = []

    async def page(self, *, within_seconds, cursor="", limit=200):
        self.calls.append({"within_seconds": within_seconds, "cursor": cursor, "limit": limit})
        idx = len(self.calls) - 1
        if idx >= len(self._pages):
            return {"subscriptions": [], "next_cursor": ""}
        return self._pages[idx]


class _FakeJobs:
    def __init__(self, *, claimed=None, fail_enqueue=False) -> None:
        self.enqueued: list[dict] = []
        self._claimed = claimed or []
        self._fail_enqueue = fail_enqueue
        self.acked: list[tuple] = []
        self.nacked: list[tuple] = []

    async def enqueue(self, *, queue, tenant, type, payload, unique_key):
        if self._fail_enqueue:
            raise RuntimeError("job-service down")
        self.enqueued.append({"queue": queue, "tenant": tenant, "type": type,
                              "payload": payload, "unique_key": unique_key})
        return "job_1"

    async def claim(self, *, worker, queue, batch):
        return self._claimed

    async def ack(self, job_id, lease_token, result=None):
        self.acked.append((job_id, lease_token, result))

    async def nack(self, job_id, lease_token, error=""):
        self.nacked.append((job_id, lease_token, error))


class _FakeNotifier:
    def __init__(self, *, results=None, raises=None) -> None:
        self._results = results or {}
        self._raises = raises or {}
        self.calls: list[dict] = []

    async def trigger(self, *, tenant, subscription_id, period_end):
        self.calls.append({"tenant": tenant, "subscription_id": subscription_id,
                           "period_end": period_end})
        if subscription_id in self._raises:
            raise self._raises[subscription_id]
        return self._results.get(subscription_id, True)


# ── scan ─────────────────────────────────────────────────────────────────────────────────────────
def test_scan_enqueues_one_job_per_real_row():
    reader = _FakeReader([{"subscriptions": [
        {"id": "sub_1", "tenant": "t1", "current_period_end": 5000},
        {"id": "sub_2", "tenant": "t2", "current_period_end": 6000},
    ], "next_cursor": ""}])
    jobs = _FakeJobs()
    out = run(scan(renewing_soon=reader, jobs=jobs, within_seconds=172800))
    assert out == {"scanned": 2, "enqueued": 2, "unavailable": 0}
    assert jobs.enqueued[0]["payload"] == {"tenant": "t1", "subscription_id": "sub_1",
                                           "period_end": 5000}
    assert jobs.enqueued[0]["unique_key"] == "renewal_heads_up:sub_1:5000"


def test_scan_pages_through_a_cursor():
    reader = _FakeReader([
        {"subscriptions": [{"id": "sub_1", "tenant": "t1", "current_period_end": 1}],
         "next_cursor": "page2"},
        {"subscriptions": [{"id": "sub_2", "tenant": "t1", "current_period_end": 2}],
         "next_cursor": ""},
    ])
    jobs = _FakeJobs()
    out = run(scan(renewing_soon=reader, jobs=jobs, within_seconds=172800))
    assert out["scanned"] == 2 and out["enqueued"] == 2
    assert reader.calls[1]["cursor"] == "page2"


def test_scan_skips_a_row_missing_tenant_or_id_or_period_end():
    reader = _FakeReader([{"subscriptions": [
        {"id": "", "tenant": "t1", "current_period_end": 5000},
        {"id": "sub_1", "tenant": "", "current_period_end": 5000},
        {"id": "sub_1", "tenant": "t1", "current_period_end": 0},
    ], "next_cursor": ""}])
    jobs = _FakeJobs()
    out = run(scan(renewing_soon=reader, jobs=jobs, within_seconds=172800))
    assert out["enqueued"] == 0
    assert jobs.enqueued == []


def test_scan_counts_an_unavailable_job_service_without_losing_the_row():
    reader = _FakeReader([{"subscriptions": [
        {"id": "sub_1", "tenant": "t1", "current_period_end": 5000},
    ], "next_cursor": ""}])
    jobs = _FakeJobs(fail_enqueue=True)
    out = run(scan(renewing_soon=reader, jobs=jobs, within_seconds=172800))
    assert out == {"scanned": 1, "enqueued": 0, "unavailable": 1}


def test_scan_is_bounded_by_max_pages_even_if_the_cursor_never_ends():
    pages = [{"subscriptions": [], "next_cursor": "keep-going"} for _ in range(100)]
    reader = _FakeReader(pages)
    jobs = _FakeJobs()
    out = run(scan(renewing_soon=reader, jobs=jobs, within_seconds=172800, max_pages=3))
    assert len(reader.calls) == 3


# ── run_claimed_jobs ─────────────────────────────────────────────────────────────────────────────
def _job(job_id, tenant, sub_id, period_end):
    return {"id": job_id, "lease_token": f"lt_{job_id}",
           "payload": {"tenant": tenant, "subscription_id": sub_id, "period_end": period_end}}


def test_run_claimed_jobs_acks_a_real_send():
    jobs = _FakeJobs(claimed=[_job("j1", "t1", "sub_1", 5000)])
    notifier = _FakeNotifier(results={"sub_1": True})
    out = run(run_claimed_jobs(jobs=jobs, notifier=notifier))
    assert out == {"claimed": 1, "sent": 1, "skipped": 0, "failed": 0}
    assert jobs.acked == [("j1", "lt_j1", {"sent": True})]


def test_run_claimed_jobs_acks_but_counts_skipped_when_nothing_was_sent():
    """Already claimed for this cycle, or no reachable owner phone — a real, already-handled
    outcome, never a failure to retry forever."""
    jobs = _FakeJobs(claimed=[_job("j1", "t1", "sub_1", 5000)])
    notifier = _FakeNotifier(results={"sub_1": False})
    out = run(run_claimed_jobs(jobs=jobs, notifier=notifier))
    assert out == {"claimed": 1, "sent": 0, "skipped": 1, "failed": 0}
    assert jobs.acked == [("j1", "lt_j1", {"sent": False})]
    assert jobs.nacked == []


def test_run_claimed_jobs_nacks_a_peer_failure_for_retry():
    jobs = _FakeJobs(claimed=[_job("j1", "t1", "sub_1", 5000)])
    notifier = _FakeNotifier(raises={"sub_1": ConnectionError("down")})
    out = run(run_claimed_jobs(jobs=jobs, notifier=notifier))
    assert out == {"claimed": 1, "sent": 0, "skipped": 0, "failed": 1}
    assert len(jobs.nacked) == 1
    assert jobs.acked == []


def test_run_claimed_jobs_with_nothing_claimed_is_a_clean_no_op():
    jobs = _FakeJobs(claimed=[])
    notifier = _FakeNotifier()
    out = run(run_claimed_jobs(jobs=jobs, notifier=notifier))
    assert out == {"claimed": 0, "sent": 0, "skipped": 0, "failed": 0}


# ── RenewingSoonReader / WhatsAppHeadsUpNotifier — unconfigured is a clean no-op ────────────────
def test_reader_unconfigured_returns_empty_never_raises():
    reader = RenewingSoonReader(base_url="", path="/x", token="t")
    assert reader.configured is False
    out = run(reader.page(within_seconds=1))
    assert out == {"subscriptions": [], "next_cursor": ""}


def test_notifier_unconfigured_returns_false_never_raises():
    notifier = WhatsAppHeadsUpNotifier(base_url="", path="/x", token="t")
    assert notifier.configured is False
    out = run(notifier.trigger(tenant="t1", subscription_id="sub_1", period_end=5000))
    assert out is False
