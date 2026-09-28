# =============================================================================
# affiliate-service — the withdrawal itself (spec §5)
# -----------------------------------------------------------------------------
# TWO PAYOUT CHANNELS, ONE MECHANISM. A marketer who does not want to hand
# over an IBAN can be paid through an intermediary payment platform instead (بحر, or whatever
# exists tomorrow — `payout_channel_name` is free text precisely so a new one never needs a code
# change). What matters to this file is identical either way: WHO gets paid, HOW MUCH, and a
# RECEIPT an admin attaches once the transfer actually happened. The channel is metadata riding
# along on the same request, never a second withdrawal flow.
#
# THE RECEIPT ITSELF, EITHER WAY ("كل الطرق ممكنة"). An admin may paste a
# link OR upload the actual file — both write the SAME `receipt_reference` field
# (`WithdrawalRequest`'s own note explains why), so `complete()` never has to know which
# happened. An uploaded file is stored under `receipt_key()` and referenced as
# `"object:<key>"`; a pasted URL is stored exactly as typed. `is_uploaded_receipt()` is the one
# place that tells them apart, so that distinction is never duplicated at each call site.
#
# A REQUEST LOCKS SPECIFIC COMMISSIONS, NEVER A "CURRENT BALANCE". Confirmed commissions keep
# arriving every day; if a request only remembered an amount, a second request racing the first
# could double-claim the same money, and neither row would say which commissions actually paid
# for which transfer — exactly the audit trail spec §5 exists to provide ("لا نزاع ما استلمت").
# So request_withdrawal() claims every currently-available commission by id, in one call, and a
# rejected request releases exactly those ids back — never a re-computed sum.
# =============================================================================
from __future__ import annotations

import re
import time
from typing import Any

from app.core.models import (
    AFFILIATES,
    COMMISSIONS,
    COMPLETED,
    CONFIRMED,
    PENDING,
    REQUESTED,
    WITHDRAWAL_REJECTED,
    WITHDRAWALS,
    Affiliate,
    Commission,
    WithdrawalRequest,
    new_id,
)

BANK_IBAN = "bank_iban"
INTERMEDIARY = "intermediary"
PAYOUT_CHANNELS = (BANK_IBAN, INTERMEDIARY)

_IBAN_RE = re.compile(r"^SA\d{22}$")


class PayoutError(Exception):
    def __init__(self, message: str, reason: str = "") -> None:
        super().__init__(message)
        self.reason = reason


# How many rows one find() page pulls when walking every commission an affiliate has, ever —
# a page, never the whole thing, so a marketer with a long history is streamed rather than
# silently truncated at whatever page size looked "big enough" the day this was written. Same
# reasoning, same page size, as backup.py's own _PAGE.
_COMMISSION_PAGE = 500

# Serialises `request_withdrawal` per-affiliate — added 2026-09-07, a real gap a QA audit found:
# the "any open request?" check and the commission-claiming write were two separate round trips
# with nothing between them, so two genuinely simultaneous requests could both pass the check and
# both claim the same confirmed commissions into two separate withdrawal requests. The whole
# method's own work (a few in-memory reads/writes) finishes well inside this window; it exists
# only to cover the request, not to be a human-facing wait.
_PAYOUT_LOCKS = "affiliate_payout_locks"
_LOCK_TTL_SECONDS = 20


async def _all_commissions(store, where: dict[str, Any]) -> list[dict[str, Any]]:
    """Every commission matching `where` — balance() and request_withdrawal() both mean
    literally every row an affiliate has (a total, a claim over everything confirmed), never a
    screenful, so this pages the cursor until find() itself says there is nothing left rather
    than trusting one page's worth to be the whole history."""
    out: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        rows, cursor = await store.find(COMMISSIONS, where, limit=_COMMISSION_PAGE, after=cursor,
                                        sort=("id", "asc"))
        out.extend(rows)
        if not cursor:
            return out


_OBJECT_PREFIX = "object:"


def receipt_key(withdrawal_id: str) -> str:
    """One deterministic key per withdrawal — re-uploading overwrites rather than accumulating,
    which is exactly right before completion (an admin fixing a wrong photo) and irrelevant
    after (nothing re-uploads a completed request)."""
    return f"withdrawals/{withdrawal_id}/receipt"


def is_uploaded_receipt(reference: str) -> bool:
    return reference.startswith(_OBJECT_PREFIX)


def receipt_object_key(reference: str) -> str:
    """The object-store key inside an `"object:<key>"` reference — call only after
    `is_uploaded_receipt` confirms it is one."""
    return reference[len(_OBJECT_PREFIX):]


class PayoutService:
    def __init__(self, *, store, min_withdrawal_halalas: int = 0) -> None:
        self._s = store
        self._min = min_withdrawal_halalas

    @property
    def min_withdrawal_halalas(self) -> int:
        """The value this service BOOTED with — the static default. Prefer
        `effective_min_withdrawal_halalas` at any real read site; this stays for a caller with no
        RuntimeConfig context (a test, a script)."""
        return self._min

    async def effective_min_withdrawal_halalas(self, runtime_config: Any) -> int:
        """The LIVE threshold — "400 ريال، وممكن يتغير، أتوقع فيه مكان لتعديلها"
        — read through RuntimeConfig, which already exists and is already audited, same pattern as
        `operations/app/core/retention.py`'s own `policy_for`: an operator's admin-panel override
        (`PUT /api/v1/affiliates/operator/config`) if one was ever set, `self._min` (this deploy's own
        AFFILIATE_WITHDRAWAL_MIN_HALALAS) otherwise. Platform-wide, not per-shop — the tenant
        passed to RuntimeConfig is always "" (there is no establishment here to scope it to; a
        marketer's own tenant is the shared `raje3-affiliates`, not a business making this policy
        decision), so the read is a plain `key -> value` lookup, not a per-tenant one.

        A NONSENSE OVERRIDE FALLS BACK, same discipline as `policy_for`: a negative or zero
        threshold from one bad panel edit would let every marketer withdraw one halala at a time,
        never applied."""
        if runtime_config is None:
            return self._min
        try:
            value = int(await runtime_config.get(tenant="", key="AFFILIATE_WITHDRAWAL_MIN_HALALAS",
                                                 default=self._min))
        except (TypeError, ValueError):
            return self._min
        return value if value > 0 else self._min

    # ── how he wants to be paid ──────────────────────────────────────────────────────────────
    async def set_payout_method(self, affiliate_id: str, *, channel: str,
                                channel_name: str = "", account_ref: str) -> dict[str, Any]:
        if channel not in PAYOUT_CHANNELS:
            raise PayoutError(f"طريقة استلام غير معروفة: {channel}", reason="bad_channel")
        if not account_ref.strip():
            raise PayoutError("أدخل بيانات الاستلام.", reason="missing_account_ref")
        if channel == INTERMEDIARY and not channel_name.strip():
            # Free text, but not EMPTY free text — a request an admin cannot read "paid through
            # what?" off of is not a request they can actually settle.
            raise PayoutError("أدخل اسم منصة الوسيط.", reason="missing_channel_name")
        if channel == BANK_IBAN and not _IBAN_RE.match(account_ref.strip().replace(" ", "").upper()):
            raise PayoutError("رقم الآيبان غير صحيح — تأكد أنه يبدأ بـ SA ويتكوّن من 24 خانة.",
                              reason="bad_iban")

        row = await self._s.get(AFFILIATES, affiliate_id)
        affiliate = Affiliate.from_dict(row) if row else None
        if affiliate is None:
            raise PayoutError("المسوّق غير موجود.", reason="not_found")

        affiliate.payout_channel = channel
        affiliate.payout_channel_name = channel_name.strip() if channel == INTERMEDIARY else ""
        affiliate.payout_account_ref = account_ref.strip()
        await self._s.put(AFFILIATES, affiliate.id, affiliate.to_dict())
        return {"channel": affiliate.payout_channel, "channel_name": affiliate.payout_channel_name,
               "account_ref": affiliate.payout_account_ref}

    async def get_payout_method(self, affiliate_id: str) -> dict[str, Any]:
        """The read half `set_payout_method` never had — the account screen needs to
        show WHAT is on file before he changes it, same "hint, never the value" discipline
        `LeadSourcingKeys`'s own places-API-key routes already use for a secret on file. The full
        `account_ref` (an IBAN, or a platform account id) is write-only past this point: it goes
        in once, and every read back is masked to its last four characters — enough for him to
        recognise his own account, never enough to be useful to anyone reading over his shoulder
        or a leaked response body."""
        row = await self._s.get(AFFILIATES, affiliate_id)
        affiliate = Affiliate.from_dict(row) if row else None
        if affiliate is None or not affiliate.payout_channel:
            return {"set": False}
        ref = affiliate.payout_account_ref
        masked = f"••••{ref[-4:]}" if len(ref) >= 4 else "••••"
        return {"set": True, "channel": affiliate.payout_channel,
                "channel_name": affiliate.payout_channel_name, "masked_account_ref": masked}

    # ── the balance a marketer actually sees ────────────────────────────────────────────────
    async def balance(self, affiliate_id: str) -> dict[str, int]:
        rows = await _all_commissions(self._s, {"affiliate_id": affiliate_id})
        pending = confirmed_available = withdrawn = 0
        for r in rows:
            c = Commission.from_dict(r)
            if c.status == PENDING:
                pending += c.amount_halalas
            elif c.status == CONFIRMED and not c.withdrawal_id:
                confirmed_available += c.amount_halalas
            elif c.withdrawal_id:
                withdrawn += c.amount_halalas
        return {"pending_halalas": pending, "confirmed_available_halalas": confirmed_available,
               "withdrawn_halalas": withdrawn}

    # ── requesting a withdrawal ──────────────────────────────────────────────────────────────
    async def request_withdrawal(self, affiliate_id: str, *, min_halalas: int | None = None) -> dict[str, Any]:
        """`min_halalas`, WHEN GIVEN, IS THE LIVE THRESHOLD — the caller's own read through
        RuntimeConfig (an operator's admin-panel override, or `self._min` as its default), same
        pattern as `operations/app/core/retention.py`'s own `policy_for`. Omitting it falls back to
        `self._min`, the value this service booted with — never stale, since a route that has a
        request-scoped RuntimeConfig always passes the resolved value; this default only covers a
        caller with no such context (a test, a script)."""
        threshold = self._min if min_halalas is None else min_halalas
        now0 = int(time.time())
        # THE LOCK, BEFORE ANYTHING ELSE IS EVEN READ — see `_PAYOUT_LOCKS`'s own comment above.
        # A second concurrent request for the SAME affiliate finds this held and is refused
        # immediately, rather than racing the read-then-write below.
        took = await self._s.claim(
            _PAYOUT_LOCKS, affiliate_id, {"affiliate_id": affiliate_id, "at": now0},
            ttl_seconds=_LOCK_TTL_SECONDS, now=now0)
        if not took:
            raise PayoutError("عندك طلب سحب قيد المعالجة الآن، حاول بعد لحظات.", reason="already_pending")

        # RELEASED IN `finally`, NOT LEFT TO THE TTL — the TTL above is only a crash safety net;
        # a legitimate next request (after this one is refused, or right after an admin rejects
        # the one it created) must not have to wait out `_LOCK_TTL_SECONDS` for no reason.
        try:
            row = await self._s.get(AFFILIATES, affiliate_id)
            affiliate = Affiliate.from_dict(row) if row else None
            if affiliate is None:
                raise PayoutError("المسوّق غير موجود.", reason="not_found")
            if not affiliate.payout_channel:
                raise PayoutError("أضِف طريقة استلام أولاً.", reason="no_payout_method")

            existing_open = await self._open_request_for(affiliate_id)
            if existing_open is not None:
                raise PayoutError("عندك طلب سحب قائم بالفعل.", reason="already_pending")

            available_rows = await _all_commissions(
                self._s, {"affiliate_id": affiliate_id, "status": CONFIRMED})
            claimable = [Commission.from_dict(r) for r in available_rows if not r.get("withdrawal_id")]
            total = sum(c.amount_halalas for c in claimable)
            if total < threshold:
                raise PayoutError(
                    f"الحد الأدنى للسحب {threshold / 100:.2f} ريال — رصيدك المؤكد أقل من ذلك.",
                    reason="below_minimum")

            now = int(time.time())
            request = WithdrawalRequest(
                id=new_id(), affiliate_id=affiliate_id, amount_halalas=total,
                commission_ids=[c.id for c in claimable], status=REQUESTED,
                payout_channel=affiliate.payout_channel,
                payout_channel_name=affiliate.payout_channel_name,
                payout_account_ref=affiliate.payout_account_ref, requested_at=now,
            )
            await self._s.put(WITHDRAWALS, request.id, request.to_dict())
            for c in claimable:
                c.withdrawal_id = request.id
                await self._s.put(COMMISSIONS, c.id, c.to_dict())
            return request.to_dict()
        finally:
            await self._s.delete(_PAYOUT_LOCKS, affiliate_id)

    async def _open_request_for(self, affiliate_id: str) -> WithdrawalRequest | None:
        rows, _ = await self._s.find(
            WITHDRAWALS, {"affiliate_id": affiliate_id, "status": REQUESTED}, limit=1)
        return WithdrawalRequest.from_dict(rows[0]) if rows else None

    async def of_affiliate(self, affiliate_id: str, *, limit: int = 100) -> list[WithdrawalRequest]:
        rows, _ = await self._s.find(WITHDRAWALS, {"affiliate_id": affiliate_id}, limit=limit,
                                     sort=("requested_at", "desc"))
        return [WithdrawalRequest.from_dict(r) for r in rows]

    async def get(self, withdrawal_id: str) -> WithdrawalRequest | None:
        row = await self._s.get(WITHDRAWALS, withdrawal_id)
        return WithdrawalRequest.from_dict(row) if row else None

    async def save_receipt_upload(self, withdrawal_id: str, *, content_type: str) -> WithdrawalRequest:
        """Records that a FILE was uploaded for this withdrawal — writing the actual bytes to
        the object store is the caller's job (it holds the container's object_store, which this
        service-layer class deliberately does not reach into itself; see admin_payouts.py).
        Never changes status: uploading a receipt is a step BEFORE completing, not completion
        itself — an admin may upload, look at it, and only then call complete()."""
        request = await self.get(withdrawal_id)
        if request is None:
            raise PayoutError("طلب السحب غير موجود.", reason="not_found")
        if request.status != REQUESTED:
            raise PayoutError("لا يمكن إرفاق إيصال لطلب غير معلّق.", reason="not_pending")
        request.receipt_reference = f"{_OBJECT_PREFIX}{receipt_key(withdrawal_id)}"
        request.receipt_content_type = content_type
        await self._s.put(WITHDRAWALS, request.id, request.to_dict())
        return request

    # ── the admin's side ─────────────────────────────────────────────────────────────────────
    async def list_pending(self, *, limit: int = 200) -> list[WithdrawalRequest]:
        rows, _ = await self._s.find(WITHDRAWALS, {"status": REQUESTED}, limit=limit,
                                     sort=("requested_at", "asc"))
        return [WithdrawalRequest.from_dict(r) for r in rows]

    async def complete(self, withdrawal_id: str, *, decided_by: str,
                       receipt_reference: str) -> dict[str, Any]:
        # SAME LOCK CLASS AS request_withdrawal ABOVE — complete()/reject() race each other on the
        # same withdrawal_id with no lock (found live, 2026-09-28): a concurrent complete+reject
        # could both read the pre-decision row, one marking it paid, the other then re-releasing
        # the same commissions back to "available" as if nothing was ever paid.
        now0 = int(time.time())
        lock_key = f"decide:{withdrawal_id}"
        took = await self._s.claim(_PAYOUT_LOCKS, lock_key, {"withdrawal_id": withdrawal_id, "at": now0},
                                   ttl_seconds=_LOCK_TTL_SECONDS, now=now0)
        if not took:
            raise PayoutError("طلب آخر يعالج هذا السحب الآن، حاول بعد لحظات.", reason="already_pending")
        try:
            row = await self._s.get(WITHDRAWALS, withdrawal_id)
            request = WithdrawalRequest.from_dict(row) if row else None
            if request is None:
                raise PayoutError("طلب السحب غير موجود.", reason="not_found")
            if request.status == COMPLETED:
                return {"already_completed": True}
            if request.status == WITHDRAWAL_REJECTED:
                raise PayoutError("هذا الطلب مرفوض بالفعل.", reason="already_rejected")
            if not receipt_reference.strip():
                # Spec §5: the receipt IS the compliance proof — a completion with no receipt is
                # exactly the "ما استلمت" dispute this whole mechanism exists to prevent.
                raise PayoutError("أرفق إيصال التحويل.", reason="receipt_required")

            request.status = COMPLETED
            request.decided_at = int(time.time())
            request.decided_by = decided_by
            request.receipt_reference = receipt_reference.strip()
            await self._s.put(WITHDRAWALS, request.id, request.to_dict())
            return {"already_completed": False}
        finally:
            await self._s.delete(_PAYOUT_LOCKS, lock_key)

    async def reject(self, withdrawal_id: str, *, decided_by: str, reason: str = "") -> dict[str, Any]:
        now0 = int(time.time())
        lock_key = f"decide:{withdrawal_id}"
        took = await self._s.claim(_PAYOUT_LOCKS, lock_key, {"withdrawal_id": withdrawal_id, "at": now0},
                                   ttl_seconds=_LOCK_TTL_SECONDS, now=now0)
        if not took:
            raise PayoutError("طلب آخر يعالج هذا السحب الآن، حاول بعد لحظات.", reason="already_pending")
        try:
            return await self._reject_locked(withdrawal_id, decided_by=decided_by, reason=reason)
        finally:
            await self._s.delete(_PAYOUT_LOCKS, lock_key)

    async def _reject_locked(self, withdrawal_id: str, *, decided_by: str,
                             reason: str = "") -> dict[str, Any]:
        row = await self._s.get(WITHDRAWALS, withdrawal_id)
        request = WithdrawalRequest.from_dict(row) if row else None
        if request is None:
            raise PayoutError("طلب السحب غير موجود.", reason="not_found")
        if request.status == COMPLETED:
            raise PayoutError("هذا الطلب مكتمل بالفعل.", reason="already_completed")
        if request.status == WITHDRAWAL_REJECTED:
            return {"already_rejected": True}

        # RELEASE THE CLAIM — every commission this request locked goes back to available, so
        # rejecting a request (a bad IBAN, a typo) never stalls real money in limbo.
        #
        # ONE BATCHED READ, NOT ONE `get()` PER COMMISSION. `commission_ids` is this affiliate's
        # whole set of confirmed, unclaimed commissions at request time — dozens to hundreds of
        # rows for an active promoter — and reading them one at a time was that many sequential
        # round trips just to release a rejected withdrawal. `find`'s own membership-filter shape
        # (`{field: [v1, v2, ...]}`) does the read side in one query; there is no batched `put`,
        # so the write loop below is unavoidable.
        if request.commission_ids:
            rows, _ = await self._s.find(COMMISSIONS, {"id": request.commission_ids},
                                         limit=len(request.commission_ids))
            for crow in rows:
                if crow.get("withdrawal_id") == request.id:
                    crow["withdrawal_id"] = ""
                    await self._s.put(COMMISSIONS, crow["id"], crow)

        request.status = WITHDRAWAL_REJECTED
        request.decided_at = int(time.time())
        request.decided_by = decided_by
        request.reason = reason[:500]
        await self._s.put(WITHDRAWALS, request.id, request.to_dict())
        return {"already_rejected": False}
