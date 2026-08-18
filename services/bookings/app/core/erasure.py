"""Erasure — the contract every service in this platform answers.

Filled in for Stage 5 (docs/خطة-تنفيذ-الحجوزات.md §6.5): `Booking.subject_ref`, stamped once at
create time from `operations` (app/core/operations.py::SubjectRefLookup), is what makes this
lookup possible at all — before that field existed, this service had no way to find a subject's
own rows and this file was an honest, tracked TODO rather than a stub pretending to work.

WRITE THIS FILE HONESTLY. It is the one piece of code a regulator would read line by line, and the
three rules below are what separate a compliant answer from a plausible one:

  1. **Never report success for work that did not happen.** If you cannot reach the rows, cannot
     identify the subject, or must keep the data, say so. A false "she was erased" is the worst
     thing this platform can say. `already_absent` means you LOOKED and found nothing — it is not
     a default.

  2. **Say what you KEPT, and why, with a basis.** "We kept it" is always an answer with a reason
     attached, never a silence.

  3. **Decide delete vs pseudonymise vs redact deliberately.** A booking is a shop's operational
     record — the same reasoning `operations`' own erasure gives a Visit's `note`: the row stays
     (the shop needs its schedule and its history), the FREE TEXT inside it does not. Nothing here
     is deleted or cancelled — an erasure request is not a cancellation request, and a future
     appointment the shop still owes the customer must not be silently dropped because they
     exercised an unrelated right.

  4. **Be idempotent.** A DSAR retries. Erasing an already-erased subject is a no-op that still
     returns a receipt; it must never fail the second time.

See docs/contracts/privacy-erase.schema.json for the wire format and
docs/contracts/privacy-erase-guide.md for the three steps to connect a service.
"""
from __future__ import annotations

from typing import Any

from app.core.models import BOOKINGS
from app.core.pii import is_subject_ref, subject_ref

_REDACTED = "[محذوف]"
_PAGE = 100


class TemplateErasure:
    # Both appear in the DSAR's target list, so they must match the data-map row registered for
    # this service (compliance-service.values.yaml PRIVACY_TARGETS). A mismatch means the DSAR
    # waits for an ack that never arrives.
    service = "bookings"
    category = "appointments"

    def __init__(self, *, store, pii_salt: str, max_scan: int = 100_000) -> None:
        self._store = store
        self._salt = pii_salt
        self._max = max_scan          # a DSAR is rare, but must never be an unbounded read

    async def erase(self, tenant: str, subject: str) -> dict[str, Any]:
        # THE CALLER MAY HOLD EITHER, same asymmetry operations' own erasure names (د-2): our own
        # path (none exists yet — bookings never receives a raw phone number) would pass the raw
        # subject; compliance's DSAR fan-out passes the PSEUDONYM, which is the only identifier
        # this service holds at all (Booking.subject_ref). Hashing a pseudonym a second time would
        # match no row and silently report "already absent" for a subject we do hold.
        ref = subject if is_subject_ref(subject) else subject_ref(self._salt, tenant, subject)

        rows, truncated = await self._page(BOOKINGS, {"tenant": tenant, "subject_ref": ref})

        erased: list[str] = []
        n = 0
        for row in rows:
            if row.get("note"):
                row["note"] = _REDACTED
                await self._store.put(BOOKINGS, f"{tenant}|{row['id']}", row)
                n += 1
        if n:
            erased.append(f"bookings:{n}")

        retained: list[dict[str, str]] = []
        if rows:
            retained.append({
                "what": f"bookings:{len(rows)}",
                "basis": "operational_record",
                "why": "the appointment itself (time, status, which services) is the shop's own "
                      "operational schedule, not withdrawn by an erasure request — only the free "
                      "text note the customer or staff wrote is personal data and is redacted",
            })

        return {
            "service": self.service,
            "category": self.category,
            "subject_ref": ref,          # the pseudonym — never echo the raw subject back
            "erased": erased,
            "retained": retained,
            # Only true when you looked and there was nothing. Never a default, and never a way to
            # avoid admitting that a lookup failed.
            "already_absent": not rows,
            "truncated": truncated,
        }

    async def _page(self, collection: str, where: dict[str, Any]) -> tuple[list[dict], bool]:
        """Read a bounded set. Returns (rows, truncated) — and `truncated` is REPORTED rather than
        swallowed, because a DSAR that silently stopped halfway is a DSAR that lied."""
        out: list[dict] = []
        cursor = None
        while len(out) < self._max:
            rows, cursor = await self._store.find(collection, where, limit=_PAGE, after=cursor,
                                                  sort=("created", "asc"))
            if not rows:
                return out, False
            out.extend(rows)
            if not cursor:
                return out, False
        return out, True
