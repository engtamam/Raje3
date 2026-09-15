"""The daily scan that finds every subscription renewing within 2 days, across every tenant, and
asks whatsapp-assistant to open the heads-up Flow for each — the ONE piece the 2026-09-15 feature
was still missing (see app/adapters/renewal_provider.py's own `renew_now`/early-form docstrings
for the rest of it).

WHY A SEPARATE SCAN + RUN, NOT ONE STEP. Same shape as `salla_refresh_scan`/`salla_jobs_run`
(api/internal.py): the SCAN reads billing's own read-only `renewing-soon` endpoint (platform
v0.24.1, no invoicing, no side effect at all) and enqueues one durable job-service job per row;
the RUN, driven far more often, claims and actually calls whatsapp-assistant. A scan that also
sent the WhatsApp message directly would have no retry, no backoff and no visibility when one
shop's send keeps failing — job-service already solves exactly this.

DEDUPED TWICE, ON PURPOSE. `unique_key` here (per subscription_id + period_end) stops job-service
from enqueuing the SAME cycle's heads-up twice across two scans; `UpcomingRenewalTriggerStore`
(services/whatsapp-assistant) stops it a second, independent way, at the point that actually sends
— so even a job-service replay or a manually re-run scan can never open the Flow twice for the
same real cycle."""
from __future__ import annotations

from typing import Any

from app.adapters import internal_http

_QUEUE = "renewal_heads_up"
_JOB_TYPE = "whatsapp.renewal_heads_up"


class RenewingSoonReader:
    """billing-service's own read, wrapped — see config.py's own `BILLING_RENEWING_SOON_PATH`."""

    def __init__(self, *, base_url: str, path: str, token: str, timeout: int = 8) -> None:
        self._url = f"{base_url.rstrip('/')}{path}" if base_url else ""
        self._token = token
        self._timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self._url)

    async def page(self, *, within_seconds: int, cursor: str = "",
                   limit: int = 200) -> dict[str, Any]:
        """-> {"subscriptions": [...], "next_cursor": "..."} — empty/absent when unconfigured or
        exhausted, never a guess. Read-only: no billing state changes as a result of this call."""
        if not self._url:
            return {"subscriptions": [], "next_cursor": ""}
        from starlette.concurrency import run_in_threadpool

        params = {"within_seconds": within_seconds, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        import urllib.parse
        url = f"{self._url}?{urllib.parse.urlencode(params)}"
        data = await run_in_threadpool(internal_http.get_json, url, self._token, self._timeout)
        return {"subscriptions": list(data.get("subscriptions") or []),
                "next_cursor": str(data.get("next_cursor") or "")}


class WhatsAppHeadsUpNotifier:
    """whatsapp-assistant's own per-row trigger — see that service's `upcoming_renewal_trigger.py`."""

    def __init__(self, *, base_url: str, path: str, token: str, timeout: int = 8) -> None:
        self._url = f"{base_url.rstrip('/')}{path}" if base_url else ""
        self._token = token
        self._timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self._url)

    async def trigger(self, *, tenant: str, subscription_id: str, period_end: int) -> bool:
        if not self._url:
            return False
        from starlette.concurrency import run_in_threadpool

        data = await run_in_threadpool(
            internal_http.post_json, self._url,
            {"tenant": tenant, "subscription_id": subscription_id, "period_end": period_end},
            self._token, self._timeout)
        return bool(data.get("sent"))


async def scan(*, renewing_soon: RenewingSoonReader, jobs: Any, within_seconds: int,
               max_pages: int = 50) -> dict[str, int]:
    """Page through billing's own read and enqueue one durable job per row. Bounded by
    `max_pages` so a cursor that never terminates cannot hang a CronJob run forever."""
    scanned = enqueued = unavailable = 0
    cursor = ""
    for _ in range(max_pages):
        out = await renewing_soon.page(within_seconds=within_seconds, cursor=cursor)
        rows = out["subscriptions"]
        scanned += len(rows)
        for row in rows:
            tenant = str(row.get("tenant") or "")
            sub_id = str(row.get("id") or "")
            period_end = int(row.get("current_period_end") or 0)
            if not tenant or not sub_id or period_end <= 0:
                continue
            try:
                await jobs.enqueue(
                    queue=_QUEUE, tenant=tenant, type=_JOB_TYPE,
                    payload={"tenant": tenant, "subscription_id": sub_id, "period_end": period_end},
                    unique_key=f"{_QUEUE}:{sub_id}:{period_end}")
                enqueued += 1
            except Exception:                                                   # noqa: BLE001
                # job-service not configured on this deployment, or unreachable — the same row is
                # simply found again on tomorrow's scan; nothing here is lost, only delayed.
                unavailable += 1
        cursor = out["next_cursor"]
        if not cursor:
            break
    return {"scanned": scanned, "enqueued": enqueued, "unavailable": unavailable}


async def run_claimed_jobs(*, jobs: Any, notifier: WhatsAppHeadsUpNotifier, batch: int = 20,
                           worker: str = "renewal-heads-up") -> dict[str, int]:
    """job-service's own claim loop, from this service's side — driven far more often than the
    scan above, same reasoning as `salla_jobs_run`'s own docstring."""
    claimed = await jobs.claim(worker=worker, queue=_QUEUE, batch=batch)
    sent = skipped = failed = 0
    for job in claimed:
        job_id, lease_token = job.get("id", ""), job.get("lease_token", "")
        payload = job.get("payload") or {}
        tenant = str(payload.get("tenant") or "")
        sub_id = str(payload.get("subscription_id") or "")
        period_end = int(payload.get("period_end") or 0)
        try:
            ok = await notifier.trigger(tenant=tenant, subscription_id=sub_id,
                                        period_end=period_end)
        except Exception as exc:                                               # noqa: BLE001
            await jobs.nack(job_id, lease_token, str(exc)[:200])
            failed += 1
            continue
        if ok:
            await jobs.ack(job_id, lease_token, {"sent": True})
            sent += 1
        else:
            # already claimed for this cycle (another worker got there first), or no reachable
            # owner phone — a real, already-handled outcome, never a failure to retry forever.
            await jobs.ack(job_id, lease_token, {"sent": False})
            skipped += 1
    return {"claimed": len(claimed), "sent": sent, "skipped": skipped, "failed": failed}
