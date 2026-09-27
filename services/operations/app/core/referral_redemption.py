"""Phase 3 of docs/خطة-تطبيق-الإحالة-والمسوقين-2026-09-27.md — till-time redemption of the
global anonymous referral code (services/referrals' own Phase 1/2), the SECOND real source
`core/entitlements.py::EntitlementGateway` aggregates, alongside `MutualBenefitEngine`.

WHY THIS LIVES HERE, NOT IN services/referrals. The plan doc's own words: "كل تفاصيل الإحالة
الحقيقية (مين أحال مين، النقاط، السجل، التقارير) تعيش بالكامل داخل قاعدة كل محل المعزولة زي اليوم
بالضبط". services/referrals holds only the global phone<->code identity and each shop's campaign
CONFIG (both tenant-agnostic or read-only from here); every fact about WHO redeemed WHOM, at
which shop, is this shop's own isolated data — same isolation `MutualBenefitGrant` already keeps
for partnership grants, applied here to a different kind of grant.

THE TWO-STEP LIFECYCLE, MIRRORING `MutualBenefitGrant` EXACTLY:
  1. `register()` — a cashier types in a code a new customer presented (till action, §Phase 3
     "التحقق من الكود عند الكاشير"). This is where every refusal happens: unknown code,
     self-referral, no active campaign, below the campaign's min spend, the referrer's own usage
     cap already spent. A clean pass creates a PENDING grant, keyed by the new customer's own
     phone at THIS tenant — terms (both rewards) copied from the campaign at this moment, never
     referenced live, same "copy, not reference" discipline `MutualBenefitGrant` already takes.
  2. `eligibility()`/`redeem()` — called BY `EntitlementGateway`, from the SAME
     `Operations.apply_offer()` every other source already goes through. Nothing here changes
     `apply_offer` or `record_visit`: the pending grant is picked up automatically the next time
     the new customer's own visit applies an offer, exactly like a mutual-benefit grant is.

USAGE CAPS ARE ENFORCED AT `register()`, NOT AT REDEMPTION — checking only at redemption time
would let a cashier register five codes for five different new customers past the cap and only
discover the refusal when the fifth one's OWN visit tries to apply an offer, which is a much
worse moment to explain a refusal than the moment the code was typed in.

THE ONCE/X_TIMES CAP COUNTS EVERY GRANT THAT EXISTS, PENDING OR REDEEMED — never redeemed-only
(a real Phase 5b security-sweep fix; see `_enforce_usage_cap`'s own comment for the exact
exploit counting only redeemed rows left open: N different new customers, each registering
their own pending grant against the SAME once-or-x_times referrer before any of them redeems,
each reading "0 redeemed so far" at their own register() call). A grant here never expires, so
counting it the moment it exists — not only once it is redeemed — is what makes "at most once,
ever" actually true rather than aspirational.

THE REFERRER'S OWN REWARD IS CREDITED ON REDEEM, NOT ON REGISTER — the new customer might never
return to spend the discount, and a grant nobody redeemed must cost the referrer nothing (same
"redeemed vs expired unused" discipline `MutualBenefitEngine.kpis()` already reports on). Five of
the eight reward types resolve to an immediate points credit and are live this phase
(`fixed_points`, `cashback_points`, `points_match`, `invoice_percentage`, `mystery_box` — a
weighted draw, resolved once, at redemption). The other three — `status_multiplier`, `time_boost`
(both would need loyalty's OWN earn engine to read a per-customer modifier it does not have a
concept of yet) and `milestone_free_item` (needs a redeemable-gift mechanism this product does not
have outside `MutualBenefitGrant`'s own narrow one) are recorded honestly on the grant
(`referrer_reward_credited = False`) but not yet acted on — a real, deliberate Phase 3 boundary,
not a placeholder: see the plan doc's own Phase 4/5 sections for where this is expected to land.
"""
from __future__ import annotations

import random
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Any

from app.adapters.referrals_desk import ReferralsDesk, ReferralsPeerUnavailable
from app.core.models import Customer
from app.core.pii import subject_ref as _subject_ref
from app.core.signup import canonical_phone
from app.core.stores import CustomerStore, new_id

GRANTS = "referral_redemption_grants"
# THE RACE `register()` CLOSES WITH IT: two concurrent calls for the SAME never-before-seen
# beneficiary phone (a fast double-tap, a retried request racing the original — the exact same
# defect class `core/offer_lock.py::OfferApplyLock` closes for `apply_offer`, ported here on the
# datastore's own `claim()` instead of the cache, since this engine holds no cache reference) would
# otherwise both pass the "any pending grant?" read before either has written one, and both create
# their own grant — an orphaned duplicate that never counts against the referrer's usage cap and
# never gets picked up by `eligibility()` (which only ever reads the newest). Short TTL: it only
# needs to outlive one peer HTTP round trip (referrer lookup + active campaign) plus one write.
_REGISTER_LOCK = "referral_redemption_register_lock"
_REGISTER_LOCK_TTL_SECONDS = 5

REWARD_FIXED_POINTS = "fixed_points"
REWARD_INVOICE_PERCENTAGE = "invoice_percentage"
REWARD_POINTS_MATCH = "points_match"
REWARD_MILESTONE_FREE_ITEM = "milestone_free_item"
REWARD_CASHBACK_POINTS = "cashback_points"
REWARD_STATUS_MULTIPLIER = "status_multiplier"
REWARD_TIME_BOOST = "time_boost"
REWARD_MYSTERY_BOX = "mystery_box"

# THE FIVE LIVE THIS PHASE — see the module docstring for why the other three are recorded, not
# credited, yet.
_IMMEDIATE_POINTS_REWARDS = (
    REWARD_FIXED_POINTS, REWARD_CASHBACK_POINTS, REWARD_POINTS_MATCH, REWARD_INVOICE_PERCENTAGE,
    REWARD_MYSTERY_BOX,
)

NEW_CUSTOMER_DISCOUNT_PERCENT = "discount_percent"
NEW_CUSTOMER_WELCOME_POINTS = "welcome_points"

MODE_ONCE = "once"
MODE_X_TIMES = "x_times"
MODE_LIFETIME = "lifetime"


class ReferralRedemptionError(Exception):
    """A refusal a cashier should read verbatim — never a stack trace."""


def _new_customer_text(reward_type: str, params: dict[str, Any]) -> str:
    if reward_type == NEW_CUSTOMER_DISCOUNT_PERCENT:
        return f"خصم عميل جديد بالإحالة: {params.get('percent', 0)}%"
    if reward_type == NEW_CUSTOMER_WELCOME_POINTS:
        return f"نقاط ترحيب بالإحالة: {params.get('points', 0)} نقطة"
    return "مكافأة إحالة نشطة"


def _referrer_points(reward_type: str, params: dict[str, Any], *, invoice_minor: int) -> int:
    """How many points the REFERRER earns for this one redemption — pure, no I/O. `invoice_minor`
    is the NEW customer's own paid amount, needed only by the two reward types that scale off it."""
    if reward_type == REWARD_FIXED_POINTS or reward_type == REWARD_CASHBACK_POINTS:
        return int(params.get("points") or 0)
    if reward_type == REWARD_INVOICE_PERCENTAGE:
        percent = int(params.get("percent") or 0)
        # halalas -> points 1:1 below a real conversion table (none exists yet — plan doc §7's own
        # "قاعدة تحويل توضيحية... رقم مرجعي فقط"); a real rate is a reporting-phase concern, not
        # this one, and rounding DOWN never credits a fraction the shop did not actually intend.
        return (invoice_minor * percent) // 100
    if reward_type == REWARD_POINTS_MATCH:
        # "نسبة من إجمالي نقاط العميل الجديد بهذي الزيارة" — the new customer's OWN points for
        # this visit are not known here (loyalty computes them independently, after this runs);
        # matched against the invoice as the same stand-in `invoice_percentage` uses, honestly,
        # until a real cross-service read of "points this visit just earned" exists.
        percent = int(params.get("percent") or 0)
        return (invoice_minor * percent) // 100
    if reward_type == REWARD_MYSTERY_BOX:
        outcomes = params.get("outcomes") or []
        if not outcomes:
            return 0
        weights = [int(o.get("weight") or 0) for o in outcomes]
        if sum(weights) <= 0:
            return 0
        chosen = random.choices(outcomes, weights=weights, k=1)[0]
        return int(chosen.get("points") or 0)
    return 0


@dataclass
class ReferralGrant:
    id: str
    tenant: str
    code: str
    referrer_phone: str
    beneficiary_phone: str
    campaign_id: str
    mode: str
    created: int
    new_customer_reward_type: str
    new_customer_reward_params: dict[str, Any]
    referrer_reward_type: str
    referrer_reward_params: dict[str, Any]
    invoice_minor: int = 0
    redeemed_at: int = 0
    redeemed_visit_id: str = ""
    referrer_reward_credited: bool = False
    referrer_points_credited: int = 0
    # PHASE 4 — see core/affiliates.py's own module docstring for the full "never both roles"
    # design. "referral" (the default, and every grant this dataclass shape predates Phase 4)
    # means an ordinary campaign-sourced grant; "affiliate" means the referrer held (at the
    # moment of `register()`) an active Affiliate row at this tenant, so `referrer_reward_type/
    # params` and `new_customer_reward_type/params` above came from THAT affiliate's own
    # negotiated terms, never the tenant's ordinary campaign — the two are mutually exclusive per
    # grant, decided once at register() and never re-derived at redeem().
    source: str = "referral"
    affiliate_id: str = ""

    def public_for_beneficiary(self) -> dict[str, Any]:
        return {"eligible": True,
                "new_customer_reward_type": self.new_customer_reward_type,
                "new_customer_reward_params": self.new_customer_reward_params}


class ReferralRedemptionEngine:
    def __init__(self, *, store: Any, referrals_desk: ReferralsDesk, loyalty_desk: Any,
                pii_salt: str, default_cc: str, affiliates: Any = None) -> None:
        self._s = store
        self._referrals = referrals_desk
        self._loyalty = loyalty_desk
        self._customers = CustomerStore(store)
        self._salt = pii_salt
        self._cc = default_cc
        # OPTIONAL, same posture every peer on this engine already takes (`referrals_desk`'s own
        # `configured` property, `loyalty_desk`'s). `None` means Phase 4's affiliate tier simply
        # never triggers — every code is read as an ordinary referral code, exactly Phase 3's
        # own behaviour before this module existed.
        self._affiliates = affiliates

    # ── register: the cashier's own action, once, per new customer ─────────────────────────────
    async def register(self, tenant: str, *, code: str, beneficiary_phone: str,
                       invoice_minor: int = 0, actor: str = "") -> ReferralGrant:
        canon_beneficiary = canonical_phone(beneficiary_phone, default_cc=self._cc)
        if not canon_beneficiary:
            raise ReferralRedemptionError("رقم جوال العميل مطلوب")
        code = (code or "").strip().upper()
        if not code:
            raise ReferralRedemptionError("كود الإحالة مطلوب")

        # IDEMPOTENT — a cashier retrying (a network blip, a double tap) must not stack a second
        # pending grant on the same customer; the first one already carries the terms that apply.
        existing = await self._pending_for_beneficiary(tenant, canon_beneficiary)
        if existing is not None:
            return existing

        # SERIALISE THE "NO PENDING GRANT YET, CREATE ONE" PATH — see this module's own
        # `_REGISTER_LOCK` note. A caller that loses the claim is a genuine concurrent collision,
        # not a data problem; it is told to retry, exactly like `OfferApplyBusy` tells a caller
        # racing `apply_offer`.
        won = await self._s.claim(_REGISTER_LOCK, f"{tenant}|{canon_beneficiary}",
                                  {"actor": actor}, ttl_seconds=_REGISTER_LOCK_TTL_SECONDS,
                                  now=time.time())
        if not won:
            raise ReferralRedemptionError(
                "جارٍ تسجيل كود لهذا العميل الآن — أعد المحاولة بعد لحظة")

        # RE-CHECK INSIDE THE CLAIM — the racer that just lost it may have been the one that
        # actually finished first; trusting the read from before the claim was won would create
        # the exact duplicate the claim exists to prevent.
        existing = await self._pending_for_beneficiary(tenant, canon_beneficiary)
        if existing is not None:
            return existing

        # PHASE 4 — a shop-local affiliate custom code, checked FIRST and entirely locally (no
        # services/referrals round trip at all: an affiliate's code is never registered globally,
        # see core/affiliates.py's own module docstring). A match here short-circuits the whole
        # ordinary-campaign path below — an affiliate's terms are independent of it by design.
        if self._affiliates is not None:
            affiliate = await self._affiliates.get_by_code(tenant, code)
            if affiliate is not None:
                return await self._register_affiliate_grant(
                    tenant, code=code, canon_beneficiary=canon_beneficiary, affiliate=affiliate,
                    invoice_minor=invoice_minor)

        try:
            referrer_phone = await self._referrals.lookup_code(code)
        except ReferralsPeerUnavailable as exc:
            raise ReferralRedemptionError(
                "تعذّر التحقق من الكود الآن. أعد المحاولة بعد قليل.") from exc
        if referrer_phone is None:
            raise ReferralRedemptionError("كود الإحالة غير صالح")

        canon_referrer = canonical_phone(referrer_phone, default_cc=self._cc)
        if not canon_referrer:
            # NEVER an anonymous referrer. A referrer phone that fails to canonicalize would
            # otherwise fall through with `referrer_phone=""` — `_enforce_usage_cap` skips its
            # own check entirely for an empty phone (nothing to count against), which would turn
            # one malformed record into an uncapped, uncredited discount mill: every registration
            # against it grants the NEW customer's own reward for free with no referrer on the
            # hook and no cap ever triggering. Refusing outright is the only safe answer to data
            # this shape, exactly the same "refuse, do not guess" posture the referrer lookup
            # itself already takes for an unreadable peer.
            raise ReferralRedemptionError("كود الإحالة غير صالح")
        if canon_referrer == canon_beneficiary:
            raise ReferralRedemptionError("لا يمكن للعميل استخدام كوده الخاص")

        # PHASE 4 — "ما فيه حد يقعد بالاثنين" (never both roles at once), enforced even when the
        # customer entered the referrer's ORDINARY global code rather than their affiliate one: if
        # this phone currently holds an active Affiliate row here, the affiliate's own negotiated
        # terms apply, never the tenant's ordinary campaign — the two reward shapes must never mix
        # for one person at one shop.
        if self._affiliates is not None:
            affiliate = await self._affiliates.get_by_phone(tenant, canon_referrer)
            if affiliate is not None:
                return await self._register_affiliate_grant(
                    tenant, code=code, canon_beneficiary=canon_beneficiary, affiliate=affiliate,
                    invoice_minor=invoice_minor)

        try:
            campaign = await self._referrals.active_campaign(tenant)
        except ReferralsPeerUnavailable as exc:
            raise ReferralRedemptionError(
                "تعذّر التحقق من حملة الإحالة الآن. أعد المحاولة بعد قليل.") from exc
        if campaign is None:
            raise ReferralRedemptionError("لا توجد حملة إحالة نشطة بهذا المتجر")

        min_spend = int(campaign.get("min_spend_minor") or 0)
        if min_spend and int(invoice_minor or 0) < min_spend:
            raise ReferralRedemptionError(
                f"الفاتورة أقل من الحد الأدنى المطلوب لهذه الحملة ({min_spend} هللة)")

        await self._enforce_usage_cap(tenant, referrer_phone=canon_referrer, campaign=campaign)

        grant = ReferralGrant(
            id=str(uuid.uuid4()), tenant=tenant, code=code, referrer_phone=canon_referrer,
            beneficiary_phone=canon_beneficiary, campaign_id=str(campaign.get("id") or ""),
            mode=str(campaign.get("mode") or ""), created=int(time.time()),
            new_customer_reward_type=str(campaign.get("new_customer_reward_type") or ""),
            new_customer_reward_params=dict(campaign.get("new_customer_reward_params") or {}),
            referrer_reward_type=str(campaign.get("reward_type") or ""),
            referrer_reward_params=dict(campaign.get("reward_params") or {}),
            invoice_minor=int(invoice_minor or 0),
        )
        await self._s.put(GRANTS, f"{tenant}|{grant.id}", asdict(grant))
        return grant

    async def _register_affiliate_grant(self, tenant: str, *, code: str, canon_beneficiary: str,
                                        affiliate: Any, invoice_minor: int) -> ReferralGrant:
        """Build and store an affiliate-sourced grant — no campaign, no usage cap, no min-spend:
        an affiliate's terms are a single negotiated relationship, independent of the tenant's
        ordinary referral campaign (plan doc §5: "مستقلة كليًا عن قواعد العملاء العاديين")."""
        canon_referrer = canonical_phone(affiliate.phone, default_cc=self._cc)
        if not canon_referrer:
            raise ReferralRedemptionError("كود الإحالة غير صالح")
        if canon_referrer == canon_beneficiary:
            raise ReferralRedemptionError("لا يمكن للعميل استخدام كوده الخاص")

        grant = ReferralGrant(
            id=str(uuid.uuid4()), tenant=tenant, code=code, referrer_phone=canon_referrer,
            beneficiary_phone=canon_beneficiary, campaign_id="", mode="", created=int(time.time()),
            new_customer_reward_type=NEW_CUSTOMER_DISCOUNT_PERCENT,
            new_customer_reward_params={"percent": affiliate.discount_percent},
            referrer_reward_type=affiliate.reward_type,
            referrer_reward_params=dict(affiliate.reward_params),
            invoice_minor=int(invoice_minor or 0), source="affiliate", affiliate_id=affiliate.id,
        )
        await self._s.put(GRANTS, f"{tenant}|{grant.id}", asdict(grant))
        return grant

    async def _pending_for_beneficiary(self, tenant: str, beneficiary_phone: str
                                       ) -> ReferralGrant | None:
        rows, _ = await self._s.find(
            GRANTS, {"tenant": tenant, "beneficiary_phone": beneficiary_phone}, limit=1000)
        pending = [r for r in rows if not r.get("redeemed_at")]
        if not pending:
            return None
        pending.sort(key=lambda r: int(r.get("created") or 0), reverse=True)
        return ReferralGrant(**pending[0])

    async def _enforce_usage_cap(self, tenant: str, *, referrer_phone: str,
                                 campaign: dict[str, Any]) -> None:
        if not referrer_phone:
            return
        campaign_id = str(campaign.get("id") or "")
        mode = str(campaign.get("mode") or "")
        rows, _ = await self._s.find(
            GRANTS, {"tenant": tenant, "referrer_phone": referrer_phone,
                    "campaign_id": campaign_id}, limit=100000)
        redeemed = [r for r in rows if r.get("redeemed_at")]

        # ONCE/X_TIMES ARE ABSOLUTE, LIFETIME CAPS — counted against EVERY grant that exists at
        # all (pending or redeemed), never redeemed-only. A grant here has no expiry (nothing
        # ever cancels or times one out): counting only REDEEMED rows would let any number of
        # DIFFERENT new customers each register their own pending grant against the SAME
        # once-or-x_times referrer at once — every one of them reads "0 (or under-limit) redeemed
        # so far" at THEIR OWN register() call, since none of the others have redeemed yet either
        # — and later every single one of them redeems with nothing here ever having refused past
        # the first (or the Xth). That is not a narrow timing race (closing it would take more
        # than `_REGISTER_LOCK`, which only ever serialises calls for the SAME beneficiary, never
        # two DIFFERENT beneficiaries against the same referrer) — it is a structural gap in what
        # this method counted, real the moment two customers register before either one redeems,
        # which needs no unlucky timing at all. Counting every grant that exists, redeemed or
        # still pending, is what actually enforces "at most once/X times, ever."
        active = rows

        if mode == MODE_ONCE and len(active) >= 1:
            raise ReferralRedemptionError("هذا السفير استخدم مكافأة هذه الحملة من قبل")
        if mode == MODE_X_TIMES:
            limit = int(campaign.get("x_times_limit") or 0)
            if limit and len(active) >= limit:
                raise ReferralRedemptionError("هذا السفير وصل للحد الأقصى لهذه الحملة")

        period = str(campaign.get("usage_cap_period") or "")
        limit = int(campaign.get("usage_cap_limit") or 0)
        if period and limit:
            now = time.time()
            window_seconds = {"day": 86400, "week": 7 * 86400, "month": 31 * 86400}.get(period, 0)
            in_window = [r for r in redeemed if now - int(r.get("redeemed_at") or 0) <= window_seconds]
            if len(in_window) >= limit:
                raise ReferralRedemptionError(
                    f"هذا السفير وصل لسقف الاستخدام لهذه الحملة ({limit} لكل {period})")

    # ── the EntitlementGateway shape — called from Operations.apply_offer, unchanged ────────────
    async def eligibility(self, tenant: str, phone: str) -> dict[str, Any] | None:
        canon = canonical_phone(phone, default_cc=self._cc)
        if not canon:
            return None
        grant = await self._pending_for_beneficiary(tenant, canon)
        return grant.public_for_beneficiary() if grant is not None else None

    async def redeem(self, tenant: str, phone: str, *, visit_id: str) -> bool:
        """IDEMPOTENT ON `visit_id`, same reason and same shape as
        `MutualBenefitEngine.redeem`'s own docstring: `EntitlementGateway.finalize` calls this
        BEFORE the visit is stamped, so a retry after a partial failure must not credit the
        referrer's own reward twice."""
        canon = canonical_phone(phone, default_cc=self._cc)
        if not canon:
            return False
        rows, _ = await self._s.find(
            GRANTS, {"tenant": tenant, "beneficiary_phone": canon}, limit=1000)
        already = next((r for r in rows if r.get("redeemed_visit_id") == visit_id), None)
        if already is not None:
            return True
        pending = [r for r in rows if not r.get("redeemed_at")]
        if not pending:
            return False
        pending.sort(key=lambda r: int(r.get("created") or 0), reverse=True)
        grant = ReferralGrant(**pending[0])
        grant.redeemed_at = int(time.time())
        grant.redeemed_visit_id = visit_id

        if grant.referrer_reward_type in _IMMEDIATE_POINTS_REWARDS and grant.referrer_phone:
            points = _referrer_points(grant.referrer_reward_type, grant.referrer_reward_params,
                                      invoice_minor=grant.invoice_minor)
            if points > 0:
                referrer = await self._customer_for_phone(tenant, grant.referrer_phone)
                is_affiliate = grant.source == "affiliate"
                # TAGGED DIFFERENTLY, SAME LEDGER — plan doc §5's own "وسم مصدر مختلف" rule,
                # exactly the same reasoning cashback already reuses the ordinary points system by
                # tag alone. Nothing about the loyalty call itself changes.
                out = await self._loyalty.award(
                    tenant=tenant, subject_ref=referrer.subject_ref, points=points,
                    idempotency_key=f"referral:{grant.id}",
                    reason="affiliate" if is_affiliate else "referral", actor="referrals")
                # A 200 response is not itself proof of a credit — a lapsed licence answers
                # `{"earned": 0, ...}` with no "_status" key at all (see loyalty's own
                # `/internal/loyalty/award`), so reading THAT as success would mark a grant
                # "credited" for points nobody actually received. `duplicate: True` (this exact
                # idempotency key already posted) is the one other honest success shape — it means
                # an earlier call already earned it, not that this call did.
                if out is not None and "_status" not in out and \
                        (int(out.get("earned") or 0) > 0 or out.get("duplicate")):
                    grant.referrer_reward_credited = True
                    grant.referrer_points_credited = points
                    if is_affiliate and grant.affiliate_id and self._affiliates is not None:
                        # BEST-EFFORT, LIKE THE LOYALTY CALL ABOVE IT — a failure here never
                        # un-credits the loyalty points already awarded above; it only means this
                        # one sale's points are missing from the affiliate's own settlement
                        # balance until a human notices, the same accepted-gap posture
                        # `LoyaltyDesk.rating_bonus`'s own docstring already takes.
                        await self._affiliates.credit_sale(tenant, grant.affiliate_id, points)

        await self._s.put(GRANTS, f"{tenant}|{grant.id}", asdict(grant))
        return True

    async def _customer_for_phone(self, tenant: str, phone: str) -> Customer:
        """Resolve-or-create, mirroring `Operations._resolve_customer`'s own reasoning: a referrer
        earning their FIRST ever reward at this shop may not be a customer here yet, and a phone
        number that shows up always becomes one rather than being turned away."""
        existing = await self._customers.by_phone(tenant, phone)
        if existing is not None:
            return existing
        customer = Customer(id=new_id("cus"), tenant=tenant, phone=phone,
                            subject_ref=_subject_ref(self._salt, tenant, phone),
                            created=int(time.time()), source="referral")
        return await self._customers.save(customer)
