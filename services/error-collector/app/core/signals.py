"""The signal itself — one contract for every source, and the store that holds them.

WHY THE SHAPE IS SO LOOSE WHERE IT IS LOOSE, AND STRICT WHERE IT IS STRICT.

`source` and `severity` are FREE-FORM STRINGS, validated only for "non-empty and not absurdly
long". They are not enums, and making them enums is the one change this file exists to prevent.
Today two things write here — Fluent Bit tailing pod logs (`source="server_log"`) and the console's
own window.onerror (`source="browser"`) — and only `severity="error"` is ever populated. Tomorrow it
is a mobile app, a webhook peer, a `warning` we want to watch for a week, an `info` breadcrumb
around a bug we cannot reproduce. Every one of those is a new VALUE in an existing column: no
migration, no enum edit, no deploy of the collector, no screen change beyond a checkbox appearing
because the API now returns a new distinct value. An enum would turn each of them into a
three-repository change, and the practical result of that cost is that the signal never gets sent.

WHAT IS STRICT IS THE ENVELOPE. `message` is required, the strings are length-bounded, and the two
JSON blobs are bounded by their serialised size. A collector is a route that accepts whatever the
world throws at it, so it is the one route on this service where an unbounded field is an outage:
a runaway client posting a 40 MB stack trace must be refused at the door, not written to the
datastore and then read back into a browser.

`detail` AND `context` ARE THE EXTENSIBILITY VALVE, and they are two blobs rather than one on
purpose. `detail` is about the EVENT (the rest of the parsed log line, the stack, the exception
class); `context` is about WHERE it happened (tenant, url, user agent, pod, namespace, node). A
reader filtering "everything from this pod" and a reader asking "what actually broke" are two
different questions, and one blob would make both of them grep.

RETENTION IS TEN DAYS, AND THAT IS THE PRIVACY DESIGN, not a disk-space setting. See
app/core/erasure.py for the argument in full.
"""
from __future__ import annotations

import datetime as _dt
import json
import uuid
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.core.models import SIGNAL_KIND, SIGNALS

#: The ceiling on the two JSON blobs, measured on their serialised bytes rather than on a field
#: length — a dict has no `max_length`, and "16 KB of JSON" is the bound that actually protects the
#: datastore and the browser that later renders it.
MAX_BLOB_BYTES = 16 * 1024

#: How far back `browse` will page looking for rows that match the filters it cannot push down into
#: the datastore (the time window and the free-text search). A bound, not a page size — see browse.
MAX_BROWSE_SCAN = 20_000


def _now() -> int:
    return int(_dt.datetime.now(_dt.timezone.utc).timestamp())


def _iso(epoch: int) -> str:
    """A lexicographically sortable UTC stamp.

    The sort field is a STRING and not the integer next to it, because the datastore orders on
    `COALESCE(value->>'created','')` and ships a btree index matching exactly that expression
    (see app/adapters/datastore/postgres.py). Ordering on an integer field would order it as text
    anyway — «9» after «10» — and would not use the index. ISO-8601 UTC is the one format where
    text order and time order are the same thing.
    """
    return _dt.datetime.fromtimestamp(epoch, _dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _blob_ok(value: dict[str, Any] | None, field: str) -> dict[str, Any] | None:
    if value is None:
        return None
    encoded = json.dumps(value, ensure_ascii=False, default=str)
    if len(encoded.encode("utf-8")) > MAX_BLOB_BYTES:
        raise ValueError(f"{field} is larger than {MAX_BLOB_BYTES} bytes")
    return value


class SignalIn(BaseModel):
    """THE ingestion contract. Both write routes validate this exact model, not two similar ones.

    ONE MODEL, TWO DOORS. `/internal/signals/ingest` (Fluent Bit, internal token) and
    `/api/v1/signals/report` (the console, a session JWT) differ in who may call them and in
    nothing else. Two models that drifted by one optional field would produce two row shapes in one
    collection, and the screen would render blanks for half its rows with nothing failing anywhere.
    """

    # Free-form, indexed, never an enum — see the module docstring. 64 is long enough for any name
    # a human would choose and short enough that it cannot be used as a payload field.
    source: str = Field(min_length=1, max_length=64)
    severity: str = Field(min_length=1, max_length=64)
    # Which service or app emitted it. "console" is just another value here.
    service: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=8192)

    # Optional. When the payload does not carry its own clock, `received_at` becomes `occurred_at`
    # at write time — an event with no time at all is unsortable, and guessing zero would file it
    # in 1970, at the far end of every screen.
    occurred_at: int | None = Field(default=None, ge=0)
    status_code: int | None = Field(default=None, ge=0, le=999)
    request_id: str | None = Field(default=None, max_length=128)
    detail: dict[str, Any] | None = None
    context: dict[str, Any] | None = None

    @field_validator("source", "severity", "service")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        # min_length=1 admits "   ". A whitespace source is a filter checkbox with no label.
        out = v.strip()
        if not out:
            raise ValueError("must not be blank")
        return out

    @field_validator("detail")
    @classmethod
    def _detail_bounded(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        return _blob_ok(v, "detail")

    @field_validator("context")
    @classmethod
    def _context_bounded(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        return _blob_ok(v, "context")


class SignalStore:
    """Write, read and expire signals. The only module that knows the row shape."""

    def __init__(self, store: Any, *, retention_days: int = 10,
                 reap_limit: int = 5000, max_scan: int = MAX_BROWSE_SCAN) -> None:
        self._s = store
        self._retention_days = max(1, int(retention_days))
        self._reap_limit = max(1, int(reap_limit))
        self._max_scan = max(1, int(max_scan))

    # ── write ────────────────────────────────────────────────────────────────────────────────
    async def record(self, signal: SignalIn, *, now: int | None = None,
                     tenant: str = "", subject_ref: str = "") -> dict[str, Any]:
        """Persist one signal and return the stored row.

        `received_at` IS SERVER-SET AND THE PAYLOAD CANNOT INFLUENCE IT. It is what retention is
        measured against, so a client clock — a browser's, or a pod whose time drifted — deciding
        when a row expires would let a wrong clock either keep a row forever or purge it on
        arrival. `occurred_at` is the caller's claim and is kept as one, separately.
        """
        at = _now() if now is None else int(now)
        row = {
            "id": uuid.uuid4().hex,
            "kind": SIGNAL_KIND,
            "received_at": at,
            # The sort key. Derived from received_at, never from the caller.
            "created": _iso(at),
            "occurred_at": int(signal.occurred_at) if signal.occurred_at else at,
            "source": signal.source,
            "severity": signal.severity,
            "service": signal.service,
            "status_code": signal.status_code,
            "request_id": signal.request_id or "",
            "message": signal.message,
            "detail": signal.detail,
            "context": signal.context,
            # Both empty for a server log. A browser report carries the reporter's own token
            # claims, which is what makes an erasure here able to look and find something rather
            # than answer `already_absent` by construction — see app/core/erasure.py.
            "tenant": tenant,
            "subject_ref": subject_ref,
        }
        await self._s.put(SIGNALS, row["id"], row)
        return row

    # ── read ─────────────────────────────────────────────────────────────────────────────────
    async def browse(self, *, sources: list[str] | None = None,
                     severities: list[str] | None = None, service: str = "",
                     since: int = 0, until: int = 0, q: str = "",
                     limit: int = 100, after: str = "") -> tuple[list[dict[str, Any]], str | None]:
        """One page, newest first, with a cursor for the next.

        TWO KINDS OF FILTER, AND THE SPLIT IS NOT ARBITRARY. `source`, `severity` and `service` are
        equality/membership, which is exactly what the DataStore port supports and what its GIN
        index serves — so they are pushed DOWN and cost nothing. The time window and the free-text
        search are neither, so they are applied HERE, over pages the datastore already ordered.

        WHICH MEANS THIS LOOP IS BOUNDED AND SAYS SO. It keeps pulling ordered pages until it has a
        full page of matches, the collection runs out, or it has examined `max_scan` rows — and in
        that last case it returns the cursor of the last row it LOOKED at, not the last row it
        MATCHED. A caller that pages on gets the rest; a caller that stops has an honest partial
        answer rather than a silent "no more results" over rows nobody read.
        """
        where: dict[str, Any] = {"kind": SIGNAL_KIND}
        if sources:
            where["source"] = sources if len(sources) > 1 else sources[0]
        if severities:
            where["severity"] = severities if len(severities) > 1 else severities[0]
        if service:
            where["service"] = service

        limit = max(1, min(int(limit), 500))
        needle = q.strip().lower()
        out: list[dict[str, Any]] = []
        cursor: str | None = after or None
        scanned = 0

        while len(out) < limit and scanned < self._max_scan:
            rows, cursor = await self._s.find(
                SIGNALS, where, limit=200, after=cursor, sort=("created", "desc"))
            if not rows:
                return out, None
            scanned += len(rows)
            last_seen = rows[-1]
            for row in rows:
                if since and int(row.get("received_at") or 0) < since:
                    continue
                if until and int(row.get("received_at") or 0) > until:
                    continue
                if needle and needle not in str(row.get("message") or "").lower():
                    continue
                out.append(row)
                if len(out) >= limit:
                    # The cursor is the LAST ROW EXAMINED, so the next page resumes immediately
                    # after it. Using the last MATCH would re-examine every row we just rejected.
                    return out, _cursor_of(row)
            if not cursor:
                return out, None
            if scanned >= self._max_scan:
                return out, _cursor_of(last_seen)
        return out, cursor

    async def distinct(self, field: str, *, cap: int = 2000) -> list[str]:
        """The values actually present for one field, so the screen's filters are populated from
        the data rather than from a hardcoded list that goes stale the day a new source appears.

        Bounded, and over the most RECENT rows — the whole store is ten days wide, so "recent" and
        "all of it" are nearly the same set, and the bound is what keeps this from becoming a full
        scan on a bad day.
        """
        seen: list[str] = []
        cursor: str | None = None
        scanned = 0
        while scanned < cap:
            rows, cursor = await self._s.find(
                SIGNALS, {"kind": SIGNAL_KIND}, limit=200, after=cursor, sort=("created", "desc"))
            if not rows:
                break
            scanned += len(rows)
            for row in rows:
                v = str(row.get(field) or "")
                if v and v not in seen:
                    seen.append(v)
            if not cursor:
                break
        return sorted(seen)

    # ── expire ───────────────────────────────────────────────────────────────────────────────
    async def reap(self, *, now: int | None = None, limit: int | None = None) -> int:
        """Delete signals older than the retention window. Returns how many went.

        BOUNDED PER CALL, AND RE-INVOKED UNTIL IT RETURNS 0 — the same shape as every other sweep
        on this platform (whatsapp-assistant's `purge_for_subject`, reminders' `_delete_where`).
        An unbounded delete is one request that times out, retries from the beginning, and never
        finishes on the one day the store is large enough to need it.

        ASCENDING, so the oldest rows are the ones the bound reaches. Descending would page through
        every fresh row first and delete nothing until the very last page — a sweep that is
        perfectly correct and, under any bound, does nothing at all.
        """
        at = _now() if now is None else int(now)
        cutoff = at - self._retention_days * 86_400
        budget = self._reap_limit if limit is None else max(1, int(limit))

        removed = 0
        cursor: str | None = None
        scanned = 0
        while removed < budget and scanned < budget * 2:
            rows, cursor = await self._s.find(
                SIGNALS, {"kind": SIGNAL_KIND}, limit=200, after=cursor, sort=("created", "asc"))
            if not rows:
                break
            scanned += len(rows)
            for row in rows:
                if int(row.get("received_at") or 0) >= cutoff:
                    # Ascending order means the first row inside the window is also the last one
                    # worth looking at. Everything after it is younger still.
                    return removed
                if await self._s.delete(SIGNALS, str(row.get("id") or "")):
                    removed += 1
                if removed >= budget:
                    return removed
            if not cursor:
                break
        return removed

    # ── erase ────────────────────────────────────────────────────────────────────────────────
    async def purge_for_subject(self, tenant: str, subject_ref: str, *,
                                max_scan: int = 5000) -> tuple[int, bool]:
        """Every signal attributed to one person, deleted. Returns (deleted, truncated).

        Truncation is RETURNED rather than swallowed, so the erasure ack can say it — a partial
        purge reported as complete is the false ack the whole DSAR contract exists to prevent
        (the convention reminders' `_delete_where` set and whatsapp-assistant's inbound store
        follows).
        """
        deleted = 0
        cursor: str | None = None
        scanned = 0
        while True:
            rows, cursor = await self._s.find(
                SIGNALS, {"kind": SIGNAL_KIND, "tenant": tenant, "subject_ref": subject_ref},
                limit=200, after=cursor, sort=("created", "asc"))
            if not rows:
                return deleted, False
            for row in rows:
                if await self._s.delete(SIGNALS, str(row.get("id") or "")):
                    deleted += 1
            scanned += len(rows)
            if scanned >= max_scan:
                return deleted, True
            if not cursor:
                return deleted, False


def _cursor_of(row: dict[str, Any]) -> str:
    """The opaque keyset cursor pointing AT this row, in the store's own encoding.

    Imported from the adapter package rather than re-derived: a cursor this module encoded
    differently would decode to a position the datastore reads as somewhere else entirely.
    """
    from app.adapters.datastore import cursor as _c
    return _c.encode(row.get("created"), str(row.get("id") or ""))


def public(row: dict[str, Any]) -> dict[str, Any]:
    """The row as the screen reads it. `kind` and `created` are storage mechanics — the partition
    constant and the sort key — and mean nothing to a reader, so they do not travel."""
    return {
        "id": row.get("id", ""),
        "received_at": row.get("received_at", 0),
        "occurred_at": row.get("occurred_at", 0),
        "source": row.get("source", ""),
        "severity": row.get("severity", ""),
        "service": row.get("service", ""),
        "status_code": row.get("status_code"),
        "request_id": row.get("request_id", ""),
        "message": row.get("message", ""),
        "detail": row.get("detail"),
        "context": row.get("context"),
    }
