"""Erasure — the contract every service in this platform answers (docs/contracts/privacy-erase-guide.md).

A DIFFERENT SHAPE FROM EVERY OTHER SERVICE'S OWN erasure.py, same reason `services/coworking`'s own
copy gives: there is no identity-service account behind a referral code, and no `subject_ref` is
ever stamped onto a row here — the raw, normalized phone number IS the only identifier this
service's Phase-1 data ever holds (`app/core/referral_code.py`'s own module docstring: "the ONLY
fact this module keeps"). The caller names the subject as a raw phone, same convention coworking's
own `core/erasure.py` already established for exactly this identity shape.

WHAT IS ERASED, AND WHY DELETE RATHER THAN REDACT. Both `referral_codes_by_phone` and
`referral_phones_by_code` hold nothing but the phone and the code together — unlike a booking or an
invoice, there is no separate operational fact worth keeping once the phone is gone (the code
becoming unresolvable is the correct outcome of an erasure, not a loss of anything this platform
still needs). Deleted outright, both sides, same posture coworking's own join-request row takes.

ANY REAL REFERRAL RELATIONSHIP THAT LATER REFERENCES THIS CODE AS A FOREIGN STRING (a future
phase's own campaign/reward data) is that OTHER data's own erasure responsibility, scoped to
itself — this module's job ends at the mapping it alone owns.
"""
from __future__ import annotations

from typing import Any

from app.core.phone import canonical_phone
from app.core.pii import subject_ref
from app.core.referral_code import BY_CODE, BY_PHONE


class TemplateErasure:
    service = "referrals"
    category = "referral_code"

    def __init__(self, *, store: Any, pii_salt: str, max_scan: int = 100_000) -> None:
        self._store = store
        self._salt = pii_salt
        self._max = max_scan          # unused here (no paged scan needed — a direct key lookup)

    async def erase(self, tenant: str, subject: str) -> dict[str, Any]:
        phone = canonical_phone(subject)
        ref = subject_ref(self._salt, tenant, phone) if self._salt else ""

        # NO `tenant` SCOPING ON THE ROW ITSELF, DELIBERATELY — the code is global BY DESIGN (one
        # phone, one code, across every shop), so there is nothing tenant-scoped to filter here;
        # `tenant` in the signature is the DSAR's own caller shape, unused by this lookup.
        row = await self._store.get(BY_PHONE, phone)
        if row is None:
            return {
                "service": self.service, "category": self.category, "subject_ref": ref,
                "erased": [], "retained": [], "already_absent": True,
            }

        code = row.get("code", "")
        deleted_phone = await self._store.delete(BY_PHONE, phone)
        deleted_code = await self._store.delete(BY_CODE, code) if code else False

        erased: list[str] = []
        if deleted_phone:
            erased.append(f"{BY_PHONE}:1")
        if deleted_code:
            erased.append(f"{BY_CODE}:1")

        return {
            "service": self.service,
            "category": self.category,
            "subject_ref": ref,
            "erased": erased,
            "retained": [],
            "already_absent": not erased,
        }
