"""job-service — the platform's own durable scheduler (`platform/services/job-service`), reached
the same way compliance-service's own `job-http` orchestrator already does
(`platform/services/compliance-service/app/adapters/orchestrator/job_http.py`).

WHY THIS EXISTS. A campaign scheduled for a month out (§ a National Day promotion prepared in
advance) used to have exactly one mechanism available: sit as a stored `fire_at` and wait for
`tick.py`'s own 15-minute scan of every active campaign to notice the day arrived. That scan is
cheap at today's volume and stays cheap regardless — but it is still a scan, and it is the same
shape every other service in this fleet independently reinvented for the identical problem (see
the platform-wide scheduling audit, 2026-09-12). `job-service` already solves it once, durably,
with retry/dead-letter/idempotency built in, and TWO platform services already depend on it in
production. This is campaigns' own first use of it — an ADDITIVE path (a future `fire_at`
delegates to job-service instead of waiting on the tick), not a replacement of the existing scan,
which keeps evaluating standing/manual campaigns exactly as it always has.
"""
from __future__ import annotations

from typing import Any

from app.adapters import internal_http

_post = internal_http.post_json


class NullJobService:
    """No `JOB_SERVICE_URL` configured — the honest default, not a silent no-op. Every method
    raises `JobServiceUnavailable` rather than pretending a job was scheduled; the caller decides
    what that means (api/v1/campaigns.py refuses the request outright rather than accepting a
    "scheduled" campaign that will, in fact, never fire)."""
    driver = "null"

    async def enqueue(self, *, queue: str, tenant: str, type: str, payload: dict[str, Any],
                      delay_seconds: float = 0, unique_key: str = "") -> str:
        raise JobServiceUnavailable

    async def claim(self, *, worker: str, queue: str, batch: int = 1) -> list[dict[str, Any]]:
        return []

    async def ack(self, job_id: str, lease_token: str, result: dict[str, Any] | None = None) -> None:
        return None

    async def nack(self, job_id: str, lease_token: str, error: str = "") -> None:
        return None


class JobServiceUnavailable(Exception):
    """Raised by every method above when no `JOB_SERVICE_URL` is configured. Named rather than a
    bare `False`/`None` return — `api/v1/campaigns.py` catches it specifically to give the owner
    the one honest sentence ("جدولة الحملات المستقبلية غير متاحة الآن") instead of a generic 500."""


class HttpJobService:
    driver = "http"

    def __init__(self, *, base_url: str, token: str, timeout: int = 8) -> None:
        self._base = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout

    async def enqueue(self, *, queue: str, tenant: str, type: str, payload: dict[str, Any],
                      delay_seconds: float = 0, unique_key: str = "") -> str:
        body = {"queue": queue, "tenant": tenant, "type": type, "payload": payload,
                "delay_seconds": delay_seconds, "unique_key": unique_key}
        data = await _post(f"{self._base}/internal/jobs/enqueue", body,
                           token=self._token, timeout=self._timeout)
        return str((data.get("job") or data).get("id") or "")

    async def claim(self, *, worker: str, queue: str, batch: int = 1) -> list[dict[str, Any]]:
        data = await _post(f"{self._base}/internal/jobs/claim",
                           {"worker": worker, "queue": queue, "batch": batch},
                           token=self._token, timeout=self._timeout)
        return list(data.get("jobs") or [])

    async def ack(self, job_id: str, lease_token: str, result: dict[str, Any] | None = None) -> None:
        await _post(f"{self._base}/internal/jobs/ack",
                   {"job_id": job_id, "lease_token": lease_token, "result": result or {}},
                   token=self._token, timeout=self._timeout)

    async def nack(self, job_id: str, lease_token: str, error: str = "") -> None:
        await _post(f"{self._base}/internal/jobs/nack",
                   {"job_id": job_id, "lease_token": lease_token, "error": error},
                   token=self._token, timeout=self._timeout)
