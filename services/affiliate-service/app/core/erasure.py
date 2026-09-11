"""Erasing a marketer — spec §9: "طلب حذف البيانات لا يعني ضياع الحق ولا ضياع الدليل".

WHAT GOES, AND WHAT DOES NOT — the same split as operations' own Customer/Visit and loyalty's own
Balance/Redemption, chosen the same way:

  Application  phone and name are BLANKED. The row itself — status, decision, WHO decided and
               when — is kept: an applicant who was rejected and disputes it later, or one whose
               application became the paper trail for a later legal claim (spec §9's own scenario:
               "a marketer works for a while, asks to be erased, then sues"), needs that history to
               still be answerable. The decision is our own record of our own act, not his personal
               data to take with him.

  Affiliate    phone and name are BLANKED. role, parent_id, status and every later slice's data
               that hangs off `id` (commission earned, payouts made) are financial/commercial
               record and are RETAINED — same basis billing-service and loyalty already use: the
               identifier is removed, the transaction history is not the customer's (here: the
               marketer's) personal data to erase once the identifier naming him is gone.

Both are found by `subject_ref`, computed once at write time (onboarding.py) rather than
re-derived here from a phone number this very function may have already blanked on an earlier,
truncated run — see core/pii.py for why re-hashing an already-blank value would silently match
nothing and report a false `already_absent`.

IDEMPOTENT: an already-erased row's phone/name are already blank, so a second pass touches nothing
further and still returns a receipt rather than failing.
"""
from __future__ import annotations

from typing import Any

from app.core.models import AFFILIATES, APPLICATIONS
from app.core.pii import is_subject_ref, subject_ref

_REDACTED = "[erased]"


class AffiliateErasure:
    # Both strings must match the data-map row registered for this service in compliance-service.
    # A mismatch means a DSAR waits for an ack that never arrives.
    service = "affiliate-service"
    category = "affiliate_identity"

    def __init__(self, *, store, pii_salt: str, max_scan: int = 100_000) -> None:
        self._store = store
        self._salt = pii_salt
        self._max = max_scan

    async def erase(self, tenant: str, subject: str) -> dict[str, Any]:
        # THE CALLER MAY HOLD EITHER, same reasoning as operations' own erasure.py: our own path
        # (were we ever to build one) would pass the phone; compliance-service passes the
        # pseudonym it already holds for every other service. Hashing a pseudonym a second time
        # matches no row and would report a false `already_absent`.
        ref = subject if is_subject_ref(subject) else subject_ref(self._salt, tenant, subject)

        erased: list[str] = []
        retained: list[dict[str, str]] = []
        truncated = False

        n_apps, cut = await self._blank(APPLICATIONS, ref)
        truncated = truncated or cut
        if n_apps:
            erased.append(f"{APPLICATIONS}:{n_apps}")
            retained.append({
                "what": f"{APPLICATIONS} decision record",
                "basis": "operational_record",
                "why": "who applied, who decided, when and why (approved/rejected) is our own "
                       "record of our own act — the identifying phone/name is removed, the "
                       "decision trail is not the applicant's personal data to take with him",
            })

        n_aff, cut = await self._blank(AFFILIATES, ref)
        truncated = truncated or cut
        if n_aff:
            erased.append(f"{AFFILIATES}:{n_aff}")
            retained.append({
                "what": f"{AFFILIATES} record",
                "basis": "financial_record",
                "why": "role, referral tree and any commission already earned are our commercial "
                       "and financial record — the identifier naming him is removed; the "
                       "transaction history behind it is retained the same way billing-service "
                       "retains a pseudonymised invoice",
            })

        return {
            "service": self.service,
            "category": self.category,
            "subject_ref": ref,
            "erased": erased,
            "retained": retained,
            "already_absent": not erased and not retained,
            "truncated": truncated,
        }

    async def _blank(self, collection: str, ref: str) -> tuple[int, bool]:
        """PAGES WITH THE STORE'S OWN CURSOR NOW — fixed 2026-09-12, a real gap a QA audit found.
        Blanking phone/name never changes `subject_ref`, so every call used to re-fetch the exact
        same {subject_ref: ref} FIRST page (no `after` was ever threaded through), and the
        already-blanked skip below made that page a no-op the second time around — a subject with
        200+ matching rows in one collection (e.g. a repeat `affiliate_applications` submitter)
        burned the whole `self._max` scan budget re-reading page one and never reached row 201,
        then reported `truncated: true` as if more scanning would have helped. `after` now
        advances exactly like every other paged store read in this codebase.
        """
        touched = 0
        scanned = 0
        truncated = False
        after: str | None = None
        while True:
            rows, after = await self._store.find(collection, {"subject_ref": ref}, limit=200,
                                                 after=after, sort=("created_at", "asc"))
            rows = list(rows or [])
            if not rows:
                break
            for row in rows:
                if row.get("phone") == _REDACTED and row.get("name") == _REDACTED:
                    continue   # already processed by an earlier, truncated run
                row["phone"] = _REDACTED
                row["name"] = _REDACTED
                await self._store.put(collection, row["id"], row)
                touched += 1
            scanned += len(rows)
            if scanned >= self._max:
                truncated = True
                break
            if not after:
                break
        return touched, truncated
