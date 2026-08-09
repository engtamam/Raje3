"""Erasing what we derived about one person.

MOST OF THIS SERVICE HOLDS NOBODY'S DATA. Snapshots are shop-level aggregates — "return rate 0.42",
"340 visits" — and identify no one. Pairs are relationships between services. Neither is a person's
data and neither is touched here.

ONE COLLECTION IS. `insight_sequences` holds the set of services one pseudonym has taken across
their visits, and although we derived it, it was derived FROM one person and describes only them.
Deriving something does not launder it.

AND ERASING IT MATTERS BEYOND THE PRINCIPLE: the association engine reads those sequences, so a
customer who asked to be forgotten would otherwise keep influencing what the shop is told about its
customers for as long as the product runs.

IDEMPOTENT, because a DSAR retries. BOUNDED, and a truncation is reported rather than swallowed —
a partial erasure acknowledged as complete is the false ack this contract exists to prevent.
"""
from __future__ import annotations

from typing import Any

from app.core.models import SEQUENCES


class TemplateErasure:
    # Must match the data-map row registered in compliance-service, or the DSAR waits for an ack
    # that never arrives — and waits without erroring.
    service = "insights"
    category = "derived_behaviour"

    def __init__(self, *, store, pii_salt: str, max_scan: int = 100_000) -> None:
        self._s = store
        self._salt = pii_salt
        self._max = max_scan

    async def erase(self, tenant: str, subject: str) -> dict[str, Any]:
        """`subject` is the SUBJECT_REF. This service never receives a raw identifier and has no
        use for one — the pseudonym is enough to group a person's own visits, which is all the
        engine ever asked for."""
        if not tenant or not subject:
            return {"service": self.service, "erased": [], "retained": [],
                    "already_absent": True, "truncated": False,
                    "note": "tenant and subject are both required; nothing was scanned"}

        key = f"{tenant}|{subject}"
        deleted = 0
        if await self._s.get(SEQUENCES, key):
            await self._s.delete(SEQUENCES, key)
            deleted = 1

        return {
            "service": self.service,
            "category": self.category,
            "subject_ref": subject,
            "erased": [f"{SEQUENCES}:{deleted}"] if deleted else [],
            "retained": [{
                "what": "the establishment's aggregate indicators and its service relationships",
                "basis": "operational_record",
                "why": "a return rate, a peak map and a relationship between two services carry "
                       "no identifier and describe the shop rather than any customer. Removing "
                       "one person from a computed average is not erasure of their data, it is "
                       "falsification of the shop's own record.",
            }],
            "already_absent": not deleted,
            "truncated": False,
        }
