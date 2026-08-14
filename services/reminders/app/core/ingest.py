"""Two ways a visit reaches this service, and why one of them is not optional.

THE EVENT BUS IS AT-MOST-ONCE, and its port says so in capitals. A subscriber that is restarting,
disconnected, or not yet deployed does not receive the event, and nothing anywhere records that it
missed one. For most consumers that is a delay. For this one it is a customer who never gets a
reminder — for ever, because nothing will ever mention that visit again.

So the event is the FAST path and the read is the TRUE one:

  subscribe()   the visit event arrives, and the reminder is scheduled within a second.
  catch_up()    a cron asks operations "what visits happened after this watermark?" and schedules
                whatever the event missed. Self-healing by construction: any outage, restart, or
                deploy gap is repaired by the next run.

ONE CODE PATH FOR BOTH. The catch-up read returns the same payload shape as the event, and both
call the same `Scheduler.on_visit`. Two paths would mean the recovery path is the one nobody
exercises, and therefore the one that is broken on the day it is finally needed.

THE WATERMARK IS ON `created`, NEVER ON `occurred_at`. `occurred_at` is the device clock: an
offline till draining a week of records emits visits dated in the past, and a cursor on it would
skip every one of them. `created` is ours and only ever increases.
"""
from __future__ import annotations

from typing import Any

WATERMARKS = "watermarks"


async def _resolve(flag: Any, tenant: str) -> bool:
    """A bool stays a bool; a callable is asked about this tenant, and may be async."""
    if callable(flag):
        out = flag(tenant)
        if hasattr(out, "__await__"):
            out = await out
        return bool(out)
    return bool(flag)


class Ingest:
    """Both paths into the scheduler."""

    def __init__(self, *, store, scheduler, visits_client=None, telemetry=None) -> None:
        self._store = store
        self._sched = scheduler
        self._visits = visits_client
        self._t = telemetry

    async def on_event(self, event: Any, *, now: int,
                       service_config: dict[str, dict[str, Any]] | None = None,
                       confirm_visits: Any = True) -> None:
        """Handle one `operations.visit.recorded`.

        NEVER RAISES. The bus swallows subscriber exceptions anyway, so raising here buys nothing
        and loses the telemetry — and the catch-up will repair whatever this drops.
        """
        payload = getattr(event, "payload", None) or (event if isinstance(event, dict) else {})
        try:
            confirm = await _resolve(confirm_visits, str(payload.get("tenant") or ""))
            await self._sched.on_visit(payload, now=now, service_config=service_config or {},
                                       confirm_visits=confirm)
            # The watermark advances on the event path too. Without this the catch-up re-reads
            # everything the events already handled — harmless, because on_visit is idempotent on
            # the visit id, but it grows into a full-table read on every cron tick.
            await self._advance(payload.get("tenant", ""), int(payload.get("created") or 0))
        except Exception as exc:                                            # noqa: BLE001
            if self._t is not None:
                self._t.event("visit_event_failed", error=str(exc)[:200],
                              visit=payload.get("visit_id", ""))

    async def discover(self, *, now: int,
                       service_config: dict[str, Any] | None = None,
                       confirm_visits: Any = True,
                       max_batches: int = 5) -> dict[str, int]:
        """Catch up across EVERY tenant, from a single global watermark.

        THIS IS THE BOOTSTRAP, and it exists because the per-tenant catch-up cannot start.
        `catch_up` is asked about a tenant we already know, and the tick derives that list from
        tenants with pending schedules — so an establishment whose very FIRST visit event was
        missed has no schedule, is never in the list, is never caught up, and never receives a
        reminder. For ever.

        Found by running the tick on a live cluster with a real visit sitting in operations and
        getting `tenants: 0` back. No unit test could have seen it: every test hands the ingest a
        tenant name.
        """
        return await self.catch_up("", now=now, service_config=service_config,
                                   confirm_visits=confirm_visits,
                                   max_batches=max_batches)

    async def catch_up(self, tenant: str, *, now: int,
                       service_config: dict[str, dict[str, Any]] | None = None,
                       confirm_visits: Any = True,
                       max_batches: int = 5) -> dict[str, int]:
        """Read visits since our watermark and schedule whatever the events missed.

        BOUNDED AT `max_batches`. A tenant that was offline for a month must not be drained in one
        request — it would hold the worker, and the next run continues from the advanced watermark
        anyway. Progress beats completeness on a repair path.
        """
        if self._visits is None:
            return {"read": 0, "scheduled": 0, "batches": 0}
        # An empty tenant is the global cursor — see discover(). Held under a reserved key so it
        # cannot collide with a real tenant's.
        mark = await self._watermark(tenant or "_all")
        read = scheduled = batches = 0
        for _ in range(max_batches):
            page = await self._visits.since(tenant=tenant, since=mark)
            visits = page.get("visits") or []
            if not visits:
                break
            for v in visits:
                # RESOLVED PER VISIT, not per call. discover() reads across EVERY tenant from one
                # global cursor, so a single boolean here would apply one shop's answer to another
                # shop's customer. A resolver keeps the setting owned by the establishment it
                # belongs to; a plain bool still works for the single-tenant path.
                confirm = await _resolve(confirm_visits, str(v.get("tenant") or tenant))
                out = await self._sched.on_visit(v, now=now,
                                                 service_config=service_config or {},
                                                 confirm_visits=confirm)
                read += 1
                if not out.duplicate:
                    scheduled += len(out.scheduled)
            # The watermark is advanced ONLY after the batch is processed. Advancing first would
            # mean a crash mid-batch skips those visits permanently — the exact failure this whole
            # file exists to prevent.
            mark = int(page.get("watermark") or mark)
            await self._advance(tenant or "_all", mark)
            batches += 1
            if not page.get("more"):
                break
        return {"read": read, "scheduled": scheduled, "batches": batches, "watermark": mark}

    async def _watermark(self, tenant: str) -> int:
        row = await self._store.get(WATERMARKS, f"{tenant}|visits")
        return int((row or {}).get("mark") or 0)

    async def _advance(self, tenant: str, mark: int) -> None:
        if not tenant or mark <= 0:
            return
        current = await self._watermark(tenant)
        if mark <= current:
            return
        await self._store.put(WATERMARKS, f"{tenant}|visits",
                              {"id": f"{tenant}|visits", "tenant": tenant, "mark": mark})


class HttpVisits:
    """Reads operations' catch-up route. stdlib urllib, like every other internal client."""

    def __init__(self, *, url: str, path: str, token: str, timeout: int = 8,
                 page: int = 200) -> None:
        self._url = url.rstrip("/") + path
        self._token = token
        self._timeout = timeout
        self._page = page

    async def since(self, *, tenant: str, since: int) -> dict[str, Any]:
        import json
        import urllib.request
        body = json.dumps({"tenant": tenant, "since": since, "limit": self._page}).encode()
        req = urllib.request.Request(
            self._url, data=body, method="POST",
            headers={"Content-Type": "application/json", "X-Internal-Token": self._token})
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:    # nosec B310
            return json.loads(resp.read() or b"{}")
