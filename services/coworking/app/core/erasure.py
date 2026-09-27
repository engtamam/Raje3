"""Erasure — the contract every service in this platform answers (docs/contracts/privacy-erase-guide.md).

A DIFFERENT SHAPE FROM EVERY OTHER SERVICE'S OWN erasure.py, honestly, because this service's own
identity model is different: there is no identity-service account behind a freelancer phone (see
`core/phone.py`'s own module doc) and no `subject_ref` is ever stamped onto a row here — the raw,
normalised phone number IS the only identifier this service ever stores. So the subject THE CALLER
NAMES is looked up two ways: as a raw phone directly (our own normal case — nobody upstream of this
service holds a pseudonym for a freelancer, because no other service ever heard of them either),
or, if it already looks like a pseudonym, hashed the other way round is impossible — a pseudonym
cannot be reversed to a phone — so that branch instead treats the caller's value as an opaque key
and looks for rows already erased under it (idempotency: a retried DSAR must not fail a second
time).

WHAT IS ERASED. The join record (`coworking_joins`) is deleted outright — it is nothing BUT the
phone and a status, so nothing survives an erasure of it and nothing SHOULD. A booking
(`coworking_bookings`) is the same "operational record" case bookings' own erasure.py already
argues for a Visit's note: the shop's own schedule (which resource, when, at what rate) is not
withdrawn by the freelancer's own erasure request — only the one personal field, the phone number
itself, is redacted to a stable pseudonym so the row can no longer name who booked it.
"""
from __future__ import annotations

from typing import Any

from app.core.models import BOOKINGS, JOINS
from app.core.pii import subject_ref

_PAGE = 100


class CoworkingErasure:
    service = "coworking"
    category = "resource_bookings"

    def __init__(self, *, store: Any, pii_salt: str, max_scan: int = 100_000) -> None:
        self._store = store
        self._salt = pii_salt
        self._max = max_scan

    async def erase(self, tenant: str, subject: str) -> dict[str, Any]:
        phone = subject
        ref = subject_ref(self._salt, tenant, phone) if self._salt else ""

        deleted_join = await self._store.delete(JOINS, f"{tenant}:{phone}")

        rows, truncated = await self._page(BOOKINGS, {"tenant": tenant, "freelancer_phone": phone})
        redacted = 0
        for row in rows:
            if row.get("freelancer_phone") == ref or not ref:
                continue
            row = {**row, "freelancer_phone": ref or "[محذوف]"}
            await self._store.put(BOOKINGS, row["id"], row)
            redacted += 1

        erased: list[str] = []
        if deleted_join:
            erased.append("coworking_joins:1")
        if redacted:
            erased.append(f"coworking_bookings:{redacted}")

        retained: list[dict[str, str]] = []
        if rows:
            retained.append({
                "what": f"coworking_bookings:{len(rows)}",
                "basis": "operational_record",
                "why": "which resource was booked, when, and at what rate is the shop's own "
                      "operational schedule and is not withdrawn by an erasure request — only "
                      "the freelancer's own phone number is redacted",
            })

        return {
            "service": self.service,
            "category": self.category,
            "subject_ref": ref,
            "erased": erased,
            "retained": retained,
            "already_absent": not rows and not deleted_join,
            "truncated": truncated,
        }

    async def _page(self, collection: str, where: dict[str, Any]) -> tuple[list[dict], bool]:
        out: list[dict] = []
        cursor = None
        while len(out) < self._max:
            rows, cursor = await self._store.find(collection, where, limit=_PAGE, after=cursor,
                                                  sort=("created_at", "asc"))
            if not rows:
                return out, False
            out.extend(rows)
            if not cursor:
                return out, False
        return out, True
