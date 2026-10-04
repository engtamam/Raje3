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

  Referral grant / affiliate — a REAL PHONE NUMBER in the clear (`referrer_phone`,
              `beneficiary_phone`, an affiliate's own `phone`, a settlement's own denormalized
              `affiliate_phone`) — a Phase 5b security-sweep finding: these two collections
              (`core/referral_redemption.py::GRANTS`, `core/affiliates.py::AFFILIATES`/
              `SETTLEMENTS`) went live across Phases 3/4 with no erasure coverage at all, the
              exact "holder nobody declares is one nobody backs up/erases" defect this fleet's own
              manifest-driven fan-out exists to catch — except here it was declared (this
              service's own manifest lists a `referral_code` erasure category already) while the
              CODE simply never grew to actually sweep the newer collections it grew afterward.
              BLANKED, same as `Customer.phone` above: the reward terms, amounts, and dates stay
              (the establishment's own operational record of a promotion it ran), only the phone
              numbers identifying WHO go. ONLY REACHABLE BY RAW PHONE, not by pseudonym — these
              rows store the phone directly, never a `subject_ref`, so a caller holding only the
              pseudonym (see the `ref`-vs-`subject` note in `erase()` below) cannot be matched
              against them at all; this is a real, inherent limit of the data model, not a bug
              this method can close on its own.

Scoped to the tenant throughout, and paged with a ceiling. A DSAR is rare, but an unbounded read is
an outage waiting for the one tenant large enough to trigger it.
"""
from __future__ import annotations

from typing import Any

from app.core.affiliates import AFFILIATES, SETTLEMENTS
from app.core.models import ASSETS, CUSTOMERS, VISITS
from app.core.pii import is_subject_ref, subject_ref
from app.core.referral_redemption import GRANTS
from app.core.signup import canonical_phone

_PAGE = 200
_REDACTED = "[erased]"


class OperationsErasure:
    # Both strings appear in compliance-service's target list and its data map. A mismatch means
    # the DSAR waits for an acknowledgement that never arrives under the name it is expecting.
    service = "operations"
    category = "field_operations"

    def __init__(self, *, store, pii_salt: str, max_scan: int = 100_000,
                default_cc: str = "966") -> None:
        self._store = store
        self._salt = pii_salt
        self._max = max_scan
        self._cc = default_cc

    async def erase(self, tenant: str, subject: str) -> dict[str, Any]:
        # THE CALLER MAY HOLD EITHER, AND ONLY ONE OF THEM MAY BE HASHED (د-2).
        #
        # Our own path passes the phone number, because that is this service's identifier for a
        # person. compliance passes the PSEUDONYM, because that is the only identifier every other
        # service holds — and this line hashed it a second time. The ref of a ref matches no row
        # anywhere: the scan found nothing, answered `already_absent` with 200, the dispatcher read
        # ACKED, and the request closed COMPLETED. The name, the number, the plate and the notes
        # stayed exactly where they were, in the one service that holds the real identifier, and
        # the customer was told his data was gone.
        ref = subject if is_subject_ref(subject) else subject_ref(self._salt, tenant, subject)
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

        # REFERRAL GRANTS / AFFILIATES — ONLY REACHABLE BY THE RAW PHONE, never the pseudonym
        # (see this module's own docstring on why: these rows store a phone directly, not a
        # subject_ref, so a caller holding only `ref` cannot be matched against them at all).
        canon_phone = "" if is_subject_ref(subject) else (canonical_phone(subject, default_cc=self._cc) or "")
        if canon_phone:
            grant_ids_seen: set[str] = set()
            n_grants = 0
            for field in ("referrer_phone", "beneficiary_phone"):
                rows, cut = await self._page(GRANTS, {"tenant": tenant, field: canon_phone})
                truncated = truncated or cut
                for row in rows:
                    gid = row.get("id", "")
                    if gid in grant_ids_seen:
                        continue
                    # BLANK ONLY THE FIELD(S) THAT ACTUALLY EQUAL THIS SUBJECT'S PHONE — the query
                    # matched on `field`, never on the other role's field, so the other party's
                    # number must survive untouched unless it independently equals the same phone
                    # too (the self-referral edge case: shouldn't exist by business rules, but if it
                    # ever did, both fields genuinely belong to the one subject being erased here).
                    changed = False
                    if row.get("referrer_phone") == canon_phone:
                        row["referrer_phone"] = ""
                        changed = True
                    if row.get("beneficiary_phone") == canon_phone:
                        row["beneficiary_phone"] = ""
                        changed = True
                    if changed:
                        await self._store.put(GRANTS, f"{tenant}|{gid}", row)
                        grant_ids_seen.add(gid)
                        n_grants += 1
            if n_grants:
                erased.append(f"referral_grants:{n_grants}")

            affiliates, cut = await self._page(AFFILIATES, {"tenant": tenant, "phone": canon_phone})
            truncated = truncated or cut
            n_affiliates = 0
            affiliate_ids: list[str] = []
            for row in affiliates:
                affiliate_ids.append(row.get("id", ""))
                if row.get("phone"):
                    row["phone"] = ""
                    await self._store.put(AFFILIATES, f"{tenant}|{row['id']}", row)
                    n_affiliates += 1
            if n_affiliates:
                erased.append(f"affiliates:{n_affiliates}")

            n_settlements = 0
            for aid in affiliate_ids:
                if not aid:
                    continue
                settlements, cut = await self._page(
                    SETTLEMENTS, {"tenant": tenant, "affiliate_id": aid})
                truncated = truncated or cut
                for row in settlements:
                    if row.get("affiliate_phone"):
                        row["affiliate_phone"] = ""
                        await self._store.put(SETTLEMENTS, f"{tenant}|{row['id']}", row)
                        n_settlements += 1
            if n_settlements:
                erased.append(f"affiliate_settlements:{n_settlements}")

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
            }, {
                "what": "referral/affiliate reward terms and amounts, without phone numbers",
                "basis": "operational_record",
                "why": "the establishment's own record of a promotion it ran and what it paid out "
                       "— the phone numbers identifying who are gone; the reward type, amount, "
                       "and date are not personal data once nobody can be identified by them.",
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
