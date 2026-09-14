"""job-service — the platform's own durable scheduler (`platform/services/job-service`), reached
the same way campaigns' own `adapters/job_service.py` already does (this service's first use of
it — copied deliberately rather than shared, since a peer client this small costs nothing to keep
per-service and a shared one would be a cross-service import into a sibling's `app/` package).

WHY THIS EXISTS HERE. A Salla access token lives two weeks and its refresh token a month, and
BOTH must be renewed before they lapse or the connection dies silently with no way back except a
full reinstall. A blind daily sweep that scans every connection and just calls Salla synchronously
has no retry, no backoff, and no visibility when a specific shop's refresh keeps failing (a
revoked app, a merchant who uninstalled from Salla's own side) — it either logs quietly or crashes
the whole sweep on one bad row. job-service already solves exactly this: durable enqueue, retry
with jittered backoff, and a dead-letter queue a person can actually look at.
"""
from __future__ import annotations

from typing import Any

from app.adapters import internal_http

_post = internal_http.post_json


class NullJobService:
    """No `JOB_SERVICE_URL` configured — the honest default, not a silent no-op. Every method
    answers "nothing to do" rather than pretending a job was scheduled; `salla_refresh_scan`
    reads an empty `claim()`/a raised `enqueue()` as "refresh is not wired here yet", never as
    "every connection is already up to date"."""
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
    """Raised by `enqueue` when no `JOB_SERVICE_URL` is configured — named rather than a bare
    `False`/`None` so a caller that needs to tell the owner something specific can."""


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
