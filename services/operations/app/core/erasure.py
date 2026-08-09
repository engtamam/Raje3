"""operations — erasing a data subject.

THIS SERVICE HOLDS THE MOST PERSONAL DATA IN THE PLATFORM, and it is the only one that holds a
phone number in the clear (see core/models.py for why). Every other service holds a `subject_ref`.
So when a deletion request arrives, this is the service where it actually means something — the
rest acknowledge a pseudonym; here the number itself goes.

It is also why this must be right rather than merely present. A service that answers 200 and clears
nothing is worse than one that errors: the error is investigated, the false ack closes the request
and the data lives on with a record saying it does not.

WHAT GOES, AND WHAT DOES NOT:

  Customer  — the phone number and the name are the personal data. They are BLANKED, and the row
              is kept with its subject_ref, its counts and its dates. Deleting the row would take
              the visit history down with it, and the establishment's operational record — how
              many services it performed, when its busy hours are — is not the customer's personal
              data and is not theirs to erase. What remains cannot identify anyone.

  Asset     — the PLATE GOES. A plate identifies a person as surely as a phone number does in a
              country where a workshop can look it up. Make, model and year stay: "a 2019 Camry
              was serviced" identifies nobody.

  Visit     — the free-text NOTE is redacted, because an operator writes whatever they like there
              and we cannot assume it is clean. The rest of a visit — which service, when, by
              which operator — is the establishment's record of its own work.

  Operator  — NOT touched by a customer's DSAR. An operator is the establishment's employee, not
              its customer; erasing them belongs to a different request with a different basis.

Scoped to the tenant throughout, and paged with a ceiling. A DSAR is rare, but an unbounded read is
an outage waiting for the one tenant large enough to trigger it.
"""
from __future__ import annotations

from typing import Any

from app.core.models import ASSETS, CUSTOMERS, VISITS
from app.core.pii import subject_ref

_PAGE = 200
_REDACTED = "[erased]"


class OperationsErasure:
    # Both strings appear in compliance-service's target list and its data map. A mismatch means
    # the DSAR waits for an acknowledgement that never arrives under the name it is expecting.
    service = "operations"
    category = "field_operations"

    def __init__(self, *, store, pii_salt: str, max_scan: int = 100_000) -> None:
        self._store = store
        self._salt = pii_salt
        self._max = max_scan

    async def erase(self, tenant: str, subject: str) -> dict[str, Any]:
        ref = subject_ref(self._salt, tenant, subject)
        erased: list[str] = []
        truncated = False

        # The subject arrives as the phone number — this service's identifier for a person. We
        # locate by ref rather than by the raw value so that a caller who only holds the pseudonym
        # (every other service) can still trigger a complete erasure here.
        customers, cut = await self._page(CUSTOMERS, {"tenant": tenant, "subject_ref": ref})
        truncated = truncated or cut

        n_customers = 0
        customer_ids: list[str] = []
        for row in customers:
            customer_ids.append(row.get("id", ""))
            if row.get("phone") or row.get("name"):
                row["phone"] = ""
                row["name"] = ""
                await self._store.put(CUSTOMERS, f"{tenant}|{row['id']}", row)
                n_customers += 1
        if n_customers:
            erased.append(f"customers:{n_customers}")

        n_assets = 0
        n_visits = 0
        for cid in customer_ids:
            if not cid:
                continue
            assets, cut = await self._page(ASSETS, {"tenant": tenant, "customer_id": cid})
            truncated = truncated or cut
            for row in assets:
                if row.get("plate"):
                    row["plate"] = ""
                    await self._store.put(ASSETS, f"{tenant}|{row['id']}", row)
                    n_assets += 1

            visits, cut = await self._page(VISITS, {"tenant": tenant, "customer_id": cid})
            truncated = truncated or cut
            for row in visits:
                if row.get("note"):
                    row["note"] = _REDACTED
                    await self._store.put(VISITS, f"{tenant}|{row['id']}", row)
                    n_visits += 1
        if n_assets:
            erased.append(f"assets:{n_assets}")
        if n_visits:
            erased.append(f"visits:{n_visits}")

        return {
            "service": self.service,
            "category": self.category,
            "subject_ref": ref,
            "erased": erased,
            # Stated rather than left to inference. A regulator asking "what did you keep and why"
            # gets an answer here, not a shrug — and "operational_record" is a basis we can defend:
            # it is the establishment's record of work it performed, holding no identifier.
            "retained": [{
                "what": "visit history without identifiers",
                "basis": "operational_record",
                "why": "the establishment's record of services it performed — how many, when, by "
                       "which operator. The identifiers are gone; what remains identifies nobody "
                       "and is not the customer's personal data to erase.",
            }],
            "already_absent": not erased,
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
