# =============================================================================
# affiliate-service — «رشّح نفسك لوظيفة» (spec §8): ٥٠٠ عميل مشترك → مؤهّل يتقدّم للتوظيف الرسمي
# -----------------------------------------------------------------------------
# A ONE-TIME career milestone, not a recurring payment — see WafaRequest's own note on why this
# is a separate model from «برنامج دعم الوفاء» rather than a second tier on it.
#
# "عميل مشترك" IS A CONVERSION COMMISSION, never a referral count. A referral (core/referrals.py)
# is only a CLAIM that a shop signed up through this marketer; a Commission is the durable proof
# billing actually confirms he was PAID for it. Counting referrals here would let a marketer who
# refers 500 shops that never convert claim the same milestone as one whose 500 actually paid —
# exactly the gap RENEWAL's own retirement (core/commission.py) was reasoned about. Since RENEWAL
# no longer exists, every Commission this service holds IS a conversion; counting them by
# affiliate is the count.
#
# NO COOLDOWN, UNLIKE WafaRequest. A rejected request costs him nothing but trying again once he
# genuinely has more converted customers — there is no monthly cycle to protect here.
# =============================================================================
from __future__ import annotations

import time
from typing import Any

from app.core.models import (
    AFFILIATES,
    EMPLOYMENT_APPROVED,
    EMPLOYMENT_REJECTED,
    EMPLOYMENT_REQUESTED,
    EMPLOYMENT_REQUESTS,
    Affiliate,
    EmploymentRequest,
    new_id,
)

APPROVE = EMPLOYMENT_APPROVED
REJECT = EMPLOYMENT_REJECTED
_DECISIONS = (APPROVE, REJECT)


class EmploymentError(Exception):
    def __init__(self, message: str, reason: str = "") -> None:
        super().__init__(message)
        self.reason = reason


class EmploymentService:
    def __init__(self, *, store, commissions, threshold_customers: int = 500) -> None:
        self._s = store
        self._commissions = commissions
        self._threshold = threshold_customers

    async def converted_customers(self, affiliate_id: str) -> int:
        """Every Commission this service ever created for this affiliate IS a converted, paying
        customer — see the module docstring on why a referral count is the wrong number. Never
        filtered by status: a customer who later got refunded still genuinely subscribed once,
        and "عميل مشترك" is a historical fact, not a current balance."""
        rows = await self._commissions.of_affiliate(affiliate_id, limit=2000)
        return len(rows)

    async def request(self, affiliate_id: str) -> dict[str, Any]:
        row = await self._s.get(AFFILIATES, affiliate_id)
        affiliate = Affiliate.from_dict(row) if row else None
        if affiliate is None:
            raise EmploymentError("المسوّق غير موجود.", reason="not_found")

        if await self._open_request_for(affiliate_id) is not None:
            raise EmploymentError("عندك طلب توظيف قائم بالفعل.", reason="already_pending")
        if await self._approved_request_for(affiliate_id) is not None:
            return {"already_approved": True}

        count = await self.converted_customers(affiliate_id)
        if count < self._threshold:
            raise EmploymentError(f"تحتاج {self._threshold} عميل مشترك على الأقل.",
                                  reason="below_threshold")

        req = EmploymentRequest(
            id=new_id(), affiliate_id=affiliate_id, converted_customers=count,
            status=EMPLOYMENT_REQUESTED, requested_at=int(time.time()),
        )
        await self._s.put(EMPLOYMENT_REQUESTS, req.id, req.to_dict())
        return {"already_approved": False, **req.to_dict()}

    async def _open_request_for(self, affiliate_id: str) -> EmploymentRequest | None:
        rows, _ = await self._s.find(
            EMPLOYMENT_REQUESTS, {"affiliate_id": affiliate_id, "status": EMPLOYMENT_REQUESTED},
            limit=1)
        return EmploymentRequest.from_dict(rows[0]) if rows else None

    async def _approved_request_for(self, affiliate_id: str) -> EmploymentRequest | None:
        rows, _ = await self._s.find(
            EMPLOYMENT_REQUESTS, {"affiliate_id": affiliate_id, "status": EMPLOYMENT_APPROVED},
            limit=1)
        return EmploymentRequest.from_dict(rows[0]) if rows else None

    async def of_affiliate(self, affiliate_id: str, *, limit: int = 100) -> list[EmploymentRequest]:
        rows, _ = await self._s.find(EMPLOYMENT_REQUESTS, {"affiliate_id": affiliate_id},
                                     limit=limit, sort=("requested_at", "desc"))
        return [EmploymentRequest.from_dict(r) for r in rows]

    async def get(self, request_id: str) -> EmploymentRequest | None:
        row = await self._s.get(EMPLOYMENT_REQUESTS, request_id)
        return EmploymentRequest.from_dict(row) if row else None

    async def list_pending(self, *, limit: int = 200) -> list[EmploymentRequest]:
        rows, _ = await self._s.find(EMPLOYMENT_REQUESTS, {"status": EMPLOYMENT_REQUESTED},
                                     limit=limit, sort=("requested_at", "asc"))
        return [EmploymentRequest.from_dict(r) for r in rows]

    async def decide(self, request_id: str, *, decision: str, decided_by: str,
                     reason: str = "") -> EmploymentRequest:
        if decision not in _DECISIONS:
            raise EmploymentError("قرار غير معروف.", reason="bad_decision")
        req = await self.get(request_id)
        if req is None:
            raise EmploymentError("الطلب غير موجود.", reason="not_found")
        if req.status != EMPLOYMENT_REQUESTED:
            raise EmploymentError("هذا الطلب تم البتّ فيه بالفعل.", reason="already_decided")

        req.status = decision
        req.decided_by = decided_by
        req.decided_at = int(time.time())
        req.reason = reason[:500]
        await self._s.put(EMPLOYMENT_REQUESTS, req.id, req.to_dict())
        return req
