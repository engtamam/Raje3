"""Shop-to-shop coupons — one tenant grants another tenant a discount on ITS OWN platform
subscription, applied at that subscription's next renewal. Not an end-customer discount: this
product has no customer invoices at all, and the "customer" here is a registered establishment.

WE ARE THE INTERMEDIARY, ALWAYS. The granting shop never sees or touches the beneficiary's
account — it supplies a phone number and receives back only success/failure, never a name, a plan,
or a balance. The lookup reuses `signup.py`'s own `PHONE_INDEX` (the shop-owner registration
phone → tenant map every sign-in already resolves through) rather than inventing a second index —
one source of truth for "which tenant does this phone belong to."

WHY THE ENGINE IS ENTIRELY OURS AND BILLING-SERVICE STAYS DUMB. billing-service's `Coupon` model
already does everything the discount itself needs (percent, expiry, single-redemption via
`max_redemptions=1`, plan-scoped, read live every renewal cycle) — see base-services v0.23.0's two
narrow internal routes this module calls: `POST /internal/billing/coupons` (create one row) and
`POST /internal/billing/subscriptions/{id}/coupon` (attach a code to an EXISTING subscription,
the one gap that blocked using the coupon primitive at all — a subscription's code is otherwise
stamped once, at signup only). Neither route knows anything about "who granted this to whom", a
monthly tier, a role, or a ceiling — all of that lives here, so billing-service's blast radius
stays exactly "can create one coupon row" no matter what this engine later grows into.

THE CEILING IS THE LAST WORD. `effective_cap()` computes a base percent from a per-tenant override
or the automatic monthly-activity tier, and ALWAYS clamps it to `CouponSettings.ceiling_percent`
before returning — no caller of this module ever sees or can request a percent above the ceiling,
by construction (see that function's own docstring for the exact resolution order).

NO DAILY RATE LIMIT (owner's own correction, 2026-09-14) — the earlier design capped attempts per
day as an anti-fishing defence for END-CUSTOMER phone numbers. That threat does not apply here:
the "customer" is a registered business, not a private individual, and un-capped grant volume is
itself the tiering signal (`monthly_grant_count`) — an activity a shop is meant to maximise, not a
number we defend against.

`feature.coupons` IS ALWAYS EXCLUDED from a grant's own scope, specific or general — a shop must
never be able to grant a discount on the very app used to grant discounts.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

from app.core.apps import KEYS as APP_KEYS
from app.core.signup import PHONE_INDEX, canonical_phone
from app.core.subscribe import row_plan_id

COUPON_SETTINGS = "cross_tenant_coupon_settings"
COUPON_TENANT_OVERRIDES = "cross_tenant_coupon_overrides"
COUPON_GRANTS = "cross_tenant_coupon_grants"
COUPON_ATTEMPTS = "cross_tenant_coupon_attempts"

_GRANT_LOCKS = "coupon_grant_locks"
_LOCK_TTL_SECONDS = 20
# A SHOP'S OWN preference, distinct from `COUPON_TENANT_OVERRIDES` (platform-admin-set, the
# competitive-cap lever) — this one is self-service, keyed by the shop's own tenant id directly
# (no `_platform` prefix needed: it is genuinely this tenant's own row, not platform-owned fact).
COUPON_PREFERENCES = "cross_tenant_coupon_preferences"
# Same reserved-key registry pattern as `core/partners.py::PLATFORM` — a fact owned by neither
# tenant, stored under a key no real tenant id can collide with.
PLATFORM = "_platform"
SETTINGS_ID = "settings"

COUPONS_KEY = "feature.partner_loyalty"
# THE ONE OTHER APP EXCLUDED EVERYWHERE COUPONS_KEY IS — «جهات الاتصال» is free (amount 0,
# `interval='once'`) and granted automatically to every shop at signup (signup.py's own
# `_start_contacts_grant`), so it can never be discounted (there is nothing to discount) AND,
# more importantly, it can never by itself count as "this beneficiary is a real subscriber" — a
# shop holding nothing but the free app is a registered account, not a paying one, and the whole
# point of `NOT_SUBSCRIBED` is to refuse exactly that (owner's own correction, 2026-09-14: "لازم
# يكون عميل يدفع لنا").
FREE_APP_KEY = "feature.contacts"

# A generous, simple, non-accumulating window — "one month, unused = gone" (owner's own words).
# Additive rather than calendar-aligned: simpler, and never a day short for a grant made on the
# 31st.
_GRANT_WINDOW_SECONDS = 31 * 24 * 3600

GRANTED = "granted"
INVALID_PERCENT = "invalid_percent"
INVALID_SCOPE = "invalid_scope"
OVER_CAP = "over_cap"
NO_ACCOUNT = "no_account"
NOT_SUBSCRIBED = "not_subscribed"
BILLING_UNAVAILABLE = "billing_unavailable"
ALREADY_HAS_BETTER = "already_has_better_coupon"
# A SHOP GRANTING ITSELF A DISCOUNT ON ITS OWN SUBSCRIPTION (owner's own correction, 2026-09-15:
# "ما يقدر يعطي نفسه خصم") — the whole product is an alliance BETWEEN two establishments; a
# granter whose own phone (or any phone that happens to resolve to its own tenant) is the
# beneficiary is not an alliance with anyone. Checked right after the phone resolves, before any
# billing call — the cheapest possible refusal, and one no caller can route around by trying a
# different phone number that happens to be registered under the same account.
SELF_GRANT = "self_grant"

# base-services v0.23.1's own reason codes on the attach-coupon 400, mapped to a per-app outcome
# a shop's own history screen can show verbatim — the whole reason this module asked for the
# distinction rather than settling for a single opaque "it failed" (owner's own requirement, from
# the very first draft of this feature).
_ATTACH_REASON_TO_OUTCOME = {
    "COUPON_EXPIRED": "coupon_expired",
    "COUPON_EXHAUSTED": "coupon_exhausted",
    "COUPON_MAX_REDEMPTIONS": "coupon_exhausted",
    "COUPON_UNKNOWN": "coupon_unknown",
    "COUPON_PLAN_MISMATCH": "plan_mismatch",
    "COUPON_DISABLED": "coupon_disabled",
    "COUPON_SCHEDULED": "coupon_scheduled",
}


def _now() -> int:
    return int(time.time())


def _month_key(ts: int) -> str:
    t = time.gmtime(ts)
    return f"{t.tm_year:04d}-{t.tm_mon:02d}"


def _prev_month_key(ts: int) -> str:
    t = time.gmtime(ts)
    year, month = t.tm_year, t.tm_mon - 1
    if month == 0:
        year, month = year - 1, 12
    return f"{year:04d}-{month:02d}"


def _month_key_offset(ts: int, months_back: int) -> str:
    """The same `_month_key`, `months_back` months earlier — used by `stats()`'s own 6-month
    trend, never for tiering (which reads `_prev_month_key` exactly, one month back, always)."""
    t = time.gmtime(ts)
    year, month = t.tm_year, t.tm_mon - months_back
    while month <= 0:
        month += 12
        year -= 1
    return f"{year:04d}-{month:02d}"


def uuid_hex() -> str:
    return uuid.uuid4().hex


class CouponError(Exception):
    """A refusal the caller (an admin route) can show verbatim."""


class CouponBusy(Exception):
    """Another grant for the same order is already in flight."""


@dataclass
class CouponTier:
    # A shop whose GRANT COUNT last month was <= this gets `percent` as its automatic cap this
    # month — reward for activity, never for revenue (owner's own correction).
    max_grants: int
    percent: int


@dataclass
class CouponTenantOverride:
    tenant: str
    # `None` means "no override, fall through to the automatic tier" — distinct from 0, a real
    # (if pointless) explicit cap.
    percent: int | None = None
    note: str = ""
    updated: int = 0


@dataclass
class CouponShopPreferences:
    tenant: str
    # WHETHER THE VISIT-RECORDING SCREEN OFFERS A COUPON GRANT AT ALL — the shop's own call, not
    # ours: holding the app and holding the role only means a grant is POSSIBLE (owner's own
    # words, 2026-09-14) — this is the third gate Visit.tsx checks before drawing anything,
    # alongside app ownership. Defaults True so a shop that just bought the app sees it working
    # immediately, exactly the opt-OUT posture every other bundled feature in this product takes.
    visit_grant_enabled: bool = True
    updated: int = 0


@dataclass
class CouponSettings:
    # THE LAST WORD — see module docstring. No tier, override, or caller-supplied percent is ever
    # honoured above this, by construction in `effective_cap()`.
    ceiling_percent: int = 35
    # What a shop with zero grant history (or no tiers configured at all) gets.
    base_percent: int = 10
    tiers: list[CouponTier] = field(default_factory=list)


@dataclass
class CouponGrant:
    id: str
    granter_tenant: str
    beneficiary_tenant: str
    app_key: str
    percent: int
    coupon_code: str
    sub_id: str
    created: int
    expires_at: float

    def public(self) -> dict[str, Any]:
        # NEVER THE BENEFICIARY'S TENANT ID OR THE RAW COUPON CODE to the granter's own screen —
        # the granter already knows which app and percent it asked for; the rest is billing's.
        row = asdict(self)
        row.pop("beneficiary_tenant", None)
        row.pop("coupon_code", None)
        return row


@dataclass
class CouponAttempt:
    id: str
    granter_tenant: str
    granter_operator_id: str
    # Last 4 digits only — enough for an owner to recognise which attempt was which of his own
    # entries, never enough to reconstruct the number he typed.
    beneficiary_phone_last4: str
    percent_requested: int
    scope: str                      # "all", or a comma-joined app-key list
    outcome: str
    created: int
    month_key: str
    per_app: dict[str, str] = field(default_factory=dict)
    grant_ids: list[str] = field(default_factory=list)
    # "" FOR EVERY DOOR EXCEPT THE EXTERNAL ONE (till.py) — a human granting from the console has
    # us for the retry problem (the row on screen either shows "granted" already or it does not);
    # a real store/site integration has no such screen and WILL retry a timed-out call, so it
    # supplies its own order number and `grant()` returns the FIRST attempt verbatim on a repeat
    # rather than granting twice. Empty means "no dedup key, an ordinary console/visit grant".
    order_id: str = ""

    def public(self) -> dict[str, Any]:
        return asdict(self)


class CouponService:
    """Everything a shop-to-shop grant needs, other than the two narrow billing-service calls
    (`plans.create_coupon`/`plans.attach_coupon`, injected as `plans`)."""

    def __init__(self, *, store, plans: Any, default_cc: str) -> None:
        self._s = store
        self._plans = plans
        self._cc = default_cc

    # ── settings & overrides — platform admin only, see api/v1/platform.py ────────────────────
    async def settings(self) -> CouponSettings:
        row = await self._s.get(COUPON_SETTINGS, f"{PLATFORM}|{SETTINGS_ID}")
        if not row:
            return CouponSettings()
        tiers = [CouponTier(**t) for t in (row.get("tiers") or [])]
        return CouponSettings(ceiling_percent=int(row.get("ceiling_percent") or 35),
                              base_percent=int(row.get("base_percent") or 10), tiers=tiers)

    async def update_settings(self, *, ceiling_percent: int, base_percent: int,
                              tiers: list[dict[str, int]] | None = None) -> CouponSettings:
        if not (0 < ceiling_percent <= 100):
            raise CouponError("السقف العام يجب أن يكون بين 1 و100.")
        if not (0 <= base_percent <= ceiling_percent):
            raise CouponError("النسبة الافتراضية يجب ألا تتجاوز السقف العام.")
        clean: list[CouponTier] = []
        for t in (tiers or []):
            max_grants, percent = int(t.get("max_grants") or 0), int(t.get("percent") or 0)
            if max_grants < 0:
                raise CouponError("عدد الخصومات بالشريحة لا يكون سالباً.")
            if not (0 <= percent <= ceiling_percent):
                raise CouponError("نسبة الشريحة يجب ألا تتجاوز السقف العام.")
            clean.append(CouponTier(max_grants=max_grants, percent=percent))
        clean.sort(key=lambda t: t.max_grants)
        settings = CouponSettings(ceiling_percent=ceiling_percent, base_percent=base_percent,
                                  tiers=clean)
        await self._s.put(COUPON_SETTINGS, f"{PLATFORM}|{SETTINGS_ID}",
                          {"tenant": PLATFORM, **asdict(settings)})
        return settings

    async def tenant_override(self, tenant: str) -> CouponTenantOverride | None:
        row = await self._s.get(COUPON_TENANT_OVERRIDES, f"{PLATFORM}|{tenant}")
        return CouponTenantOverride(**{k: v for k, v in row.items() if k != "tenant_key"}) \
            if row else None

    async def set_tenant_override(self, tenant: str, *, percent: int | None,
                                  note: str = "") -> CouponTenantOverride:
        if percent is not None:
            settings = await self.settings()
            if not (0 <= percent <= settings.ceiling_percent):
                raise CouponError("سقف المحل الخاص يجب ألا يتجاوز السقف العام.")
        row = CouponTenantOverride(tenant=tenant, percent=percent, note=note[:512],
                                   updated=_now())
        await self._s.put(COUPON_TENANT_OVERRIDES, f"{PLATFORM}|{tenant}",
                          {"tenant_key": PLATFORM, **asdict(row)})
        return row

    # ── the shop's own on/off switch for the visit-screen integration ─────────────────────────
    async def preferences(self, tenant: str) -> CouponShopPreferences:
        row = await self._s.get(COUPON_PREFERENCES, tenant)
        if not row:
            return CouponShopPreferences(tenant=tenant)
        return CouponShopPreferences(tenant=tenant,
                                     visit_grant_enabled=bool(row.get("visit_grant_enabled", True)),
                                     updated=int(row.get("updated") or 0))

    async def set_preferences(self, tenant: str, *, visit_grant_enabled: bool) -> CouponShopPreferences:
        row = CouponShopPreferences(tenant=tenant, visit_grant_enabled=visit_grant_enabled,
                                    updated=_now())
        await self._s.put(COUPON_PREFERENCES, tenant, asdict(row))
        return row

    # ── the cap a granter may use right now ────────────────────────────────────────────────────
    async def effective_cap(self, granter_tenant: str) -> int:
        """THE RESOLUTION ORDER: an explicit per-tenant override wins outright; otherwise the
        automatic tier for LAST month's grant count; otherwise the platform's own base. Either way
        the result is clamped to `ceiling_percent` before it is ever returned — nothing downstream
        of this function can see, request, or accidentally honour a percent above the ceiling."""
        settings = await self.settings()
        override = await self.tenant_override(granter_tenant)
        if override and override.percent is not None:
            base = override.percent
        else:
            base = settings.base_percent
            if settings.tiers:
                count = await self.monthly_grant_count(
                    granter_tenant, _prev_month_key(_now()))
                matched = False
                for tier in settings.tiers:                 # already sorted ascending, see above
                    if count <= tier.max_grants:
                        base = tier.percent
                        matched = True
                        break
                if not matched:
                    base = settings.tiers[-1].percent        # exceeded every threshold: best tier
        return min(base, settings.ceiling_percent)

    async def monthly_grant_count(self, tenant: str, month_key: str) -> int:
        rows, _ = await self._s.find(
            COUPON_ATTEMPTS,
            {"tenant": PLATFORM, "granter_tenant": tenant, "outcome": GRANTED,
             "month_key": month_key},
            limit=100000)
        return len(rows)

    # ── who is this phone, without telling the caller anything else ───────────────────────────
    async def _lookup_beneficiary(self, phone: str) -> str:
        row = await self._s.get(PHONE_INDEX, canonical_phone(phone, default_cc=self._cc))
        return str((row or {}).get("tenant") or "")

    async def _attempt_for_order(self, granter_tenant: str, order_id: str) -> CouponAttempt | None:
        """The stored attempt for a (granter, order) pair already seen, else `None`. `order_id` is
        unique per granter, not globally — two different shops are free to use "1", "2", ... in
        their own POS numbering without colliding."""
        rows, _ = await self._s.find(
            COUPON_ATTEMPTS,
            {"tenant": PLATFORM, "granter_tenant": granter_tenant, "order_id": order_id},
            limit=1)
        if not rows:
            return None
        row = rows[0]
        return CouponAttempt(**{k: v for k, v in row.items() if k != "tenant"})

    async def granter_is_subscribed(self, tenant: str) -> bool | None:
        """Does THIS tenant (the one about to grant) itself hold `feature.coupons` — asked by the
        till door only. A human door's capability IS the entitlement check (same posture as every
        other bundled app's console screen); a till's credential proves only `operations.record`,
        held by every till regardless of which apps its shop bought, so granting through it needs
        its own real check rather than inheriting the console's client-side gate.

        THREE ANSWERS: `True`/`False` on a real read, `None` when billing could not be asked — the
        same "a hiccup must not stop a shop's counter, but a plain no must" split `core/licence.py`
        documents at length for `feature.api`; the caller here makes the identical call.

        An empty `plan_id_for_key` is read as `False`, not `None` — the SAME ambiguity
        `_target_apps` above already accepts for the beneficiary side (that call cannot tell "no
        such plan" from "billing unreachable" either); not a new, weaker guarantee introduced here.
        """
        plan_id = await self._plans.plan_id_for_key(COUPONS_KEY)
        if not plan_id:
            return False
        subs = await self._plans.subscriptions(tenant)
        if subs is None:
            return None
        return any(row_plan_id(s) == plan_id
                  and str(s.get("status") or "") in ("active", "trialing") for s in subs)

    async def admin_tenant_by_phone(self, phone: str) -> str:
        """PLATFORM ADMIN ONLY — full disclosure of a tenant id, unlike `check()`/`grant()`'s own
        minimal-disclosure posture toward an ordinary granting shop. The caller here is our own
        platform-admin screen finding which shop a support conversation is about, the same trust
        level `CustomerByPhoneLookup.tsx` already operates at (a raw tenant id is normal to show
        an admin in this panel)."""
        return await self._lookup_beneficiary(phone)

    async def _target_apps(self, beneficiary_tenant: str, *, general: bool,
                           app_keys: list[str]) -> list[tuple[str, str, str]] | None:
        """`(app_key, plan_id, subscription_id)` for every ELIGIBLE app already held by the
        beneficiary — `None` means billing could not be read (a different refusal from "holds
        none"), an empty list means it answered and there is genuinely nothing eligible."""
        subs = await self._plans.subscriptions(beneficiary_tenant)
        if subs is None:
            return None
        held = [s for s in subs if str(s.get("status") or "") in ("active", "trialing")]
        out: list[tuple[str, str, str]] = []
        if general:
            for s in held:
                plan_id, sub_id = row_plan_id(s), str(s.get("id") or "")
                if not plan_id or not sub_id:
                    continue
                limits = await self._plans.limits(plan_id) or {}
                fkeys = [k for k in limits if k.startswith("feature.")]
                if len(fkeys) != 1 or fkeys[0] in (COUPONS_KEY, FREE_APP_KEY):
                    continue
                out.append((fkeys[0], plan_id, sub_id))
            return out
        for key in app_keys:
            plan_id = await self._plans.plan_id_for_key(key)
            if not plan_id:
                continue
            match = next((s for s in held if row_plan_id(s) == plan_id), None)
            if match:
                out.append((key, plan_id, str(match.get("id") or "")))
        return out

    # ── the act itself ──────────────────────────────────────────────────────────────────────────
    async def grant(self, *, granter_tenant: str, granter_operator_id: str, phone: str,
                    percent: int, general: bool = False,
                    app_keys: list[str] | None = None, order_id: str = "") -> CouponAttempt:
        """Every path ends in ONE `CouponAttempt` row, successful or not, with the real reason —
        same discipline the owner asked for from the very first draft of this feature.

        `order_id` (till.py only): a repeat call with the SAME (granter_tenant, order_id) returns
        the FIRST attempt untouched — no new billing call, no new row — rather than granting a
        second time. Locked on (granter_tenant, order_id) so two concurrent retries cannot both
        pass the dedup check and both grant."""
        if not order_id:
            return await self._grant_unlocked(
                granter_tenant=granter_tenant, granter_operator_id=granter_operator_id,
                phone=phone, percent=percent, general=general, app_keys=app_keys, order_id="")
        lock_key = f"{granter_tenant}|{order_id}"
        now0 = _now()
        took = await self._s.claim(_GRANT_LOCKS, lock_key, {"at": now0},
                                   ttl_seconds=_LOCK_TTL_SECONDS, now=now0)
        if not took:
            existing = await self._attempt_for_order(granter_tenant, order_id)
            if existing is not None:
                return existing
            raise CouponBusy("a grant for this order is already being processed")
        try:
            existing = await self._attempt_for_order(granter_tenant, order_id)
            if existing is not None:
                return existing
            return await self._grant_unlocked(
                granter_tenant=granter_tenant, granter_operator_id=granter_operator_id,
                phone=phone, percent=percent, general=general, app_keys=app_keys,
                order_id=order_id)
        finally:
            await self._s.delete(_GRANT_LOCKS, lock_key)

    async def _grant_unlocked(self, *, granter_tenant: str, granter_operator_id: str, phone: str,
                              percent: int, general: bool = False,
                              app_keys: list[str] | None = None, order_id: str = "") -> CouponAttempt:
        app_keys = list(app_keys or [])
        now = _now()

        async def _log(outcome: str, per_app: dict[str, str] | None = None,
                       grant_ids: list[str] | None = None) -> CouponAttempt:
            att = CouponAttempt(
                id=f"ctatt_{uuid_hex()}", granter_tenant=granter_tenant,
                granter_operator_id=granter_operator_id,
                beneficiary_phone_last4=phone[-4:] if len(phone) >= 4 else phone,
                percent_requested=int(percent), scope=("all" if general else ",".join(app_keys)),
                outcome=outcome, created=now, month_key=_month_key(now),
                per_app=per_app or {}, grant_ids=grant_ids or [], order_id=order_id)
            await self._s.put(COUPON_ATTEMPTS, f"{PLATFORM}|{att.id}",
                              {"tenant": PLATFORM, **asdict(att)})
            return att

        if percent <= 0 or percent > 100:
            return await _log(INVALID_PERCENT)
        known = set(APP_KEYS) - {COUPONS_KEY, FREE_APP_KEY}
        if general:
            app_keys = []
        else:
            if not app_keys or any(k not in known for k in app_keys):
                return await _log(INVALID_SCOPE)

        cap = await self.effective_cap(granter_tenant)
        if percent > cap:
            return await _log(OVER_CAP)

        beneficiary_tenant = await self._lookup_beneficiary(phone)
        if not beneficiary_tenant:
            return await _log(NO_ACCOUNT)
        if beneficiary_tenant == granter_tenant:
            return await _log(SELF_GRANT)

        targets = await self._target_apps(beneficiary_tenant, general=general,
                                          app_keys=app_keys)
        if targets is None:
            return await _log(BILLING_UNAVAILABLE)
        if not targets:
            return await _log(NOT_SUBSCRIBED)

        expires_at = now + _GRANT_WINDOW_SECONDS
        per_app: dict[str, str] = {}
        grant_ids: list[str] = []
        for app_key, plan_id, sub_id in targets:
            existing_best = await self._best_active_percent(beneficiary_tenant, app_key, now)
            if existing_best >= int(percent):
                per_app[app_key] = ALREADY_HAS_BETTER
                continue
            code = f"x2t_{uuid_hex()}"
            status, _out = await self._plans.create_coupon(
                code=code, plan_id=plan_id, percent=int(percent), expires_at=float(expires_at),
                note=f"shop-to-shop grant from {granter_tenant[:24]}")
            if status not in (200, 201):
                per_app[app_key] = BILLING_UNAVAILABLE
                continue
            status2, out2 = await self._plans.attach_coupon(
                tenant=beneficiary_tenant, sub_id=sub_id, coupon_code=code)
            if status2 != 200:
                # A coupon row now exists in billing with nobody ever able to redeem it — harmless
                # (plan-scoped, single-use, expires on its own) and left alone rather than adding a
                # compensating-delete call for a case this narrow.
                if status2 == 404:
                    # base-services v0.23.1: deliberately undistinguished from a tenant mismatch
                    # (IDOR guard) — the subscription we just read moments ago is gone or no
                    # longer this tenant's; either way there is nothing left to attach to.
                    per_app[app_key] = NOT_SUBSCRIBED
                else:
                    reason = str((out2 or {}).get("reason") or "")
                    per_app[app_key] = _ATTACH_REASON_TO_OUTCOME.get(reason, BILLING_UNAVAILABLE)
                continue
            grant = CouponGrant(id=f"ctg_{uuid_hex()}", granter_tenant=granter_tenant,
                                beneficiary_tenant=beneficiary_tenant, app_key=app_key,
                                percent=int(percent), coupon_code=code, sub_id=sub_id,
                                created=now, expires_at=expires_at)
            await self._s.put(COUPON_GRANTS, f"{PLATFORM}|{grant.id}",
                              {"tenant": PLATFORM, **asdict(grant)})
            grant_ids.append(grant.id)
            per_app[app_key] = str(out2.get("status") or "attached")

        if not grant_ids:
            # THE REAL REASON, NOT A BLANKET FAILURE — if every target was refused for already
            # carrying an equal-or-better coupon, that IS the outcome, distinct from an actual
            # billing problem (owner's own requirement: the history screen must say why).
            overall = (ALREADY_HAS_BETTER if per_app
                      and all(v == ALREADY_HAS_BETTER for v in per_app.values())
                      else BILLING_UNAVAILABLE)
            return await _log(overall, per_app=per_app)
        return await _log(GRANTED, per_app=per_app, grant_ids=grant_ids)

    # ── the live "before you even press grant" check — the grant form's own inline hint ────────
    async def check(self, *, granter_tenant: str, phone: str) -> dict[str, Any]:
        """`{"registered": bool, "already_granted_this_month": bool, "is_self": bool}` — nothing
        else, ever. The granter already typed this phone himself; this answers only the facts
        that change what he is about to do, never confirming or naming the beneficiary beyond
        that. `is_self` lets the form refuse before he even presses submit — `grant()`'s own
        `SELF_GRANT` outcome is the real, unavoidable enforcement; this is only the earlier,
        friendlier warning."""
        beneficiary_tenant = await self._lookup_beneficiary(phone)
        if not beneficiary_tenant:
            return {"registered": False, "already_granted_this_month": False, "is_self": False}
        if beneficiary_tenant == granter_tenant:
            return {"registered": True, "already_granted_this_month": False, "is_self": True}
        now = _now()
        rows, _ = await self._s.find(
            COUPON_GRANTS,
            {"tenant": PLATFORM, "granter_tenant": granter_tenant,
             "beneficiary_tenant": beneficiary_tenant},
            limit=1000)
        this_month = _month_key(now)
        granted_this_month = any(_month_key(int(r.get("created") or 0)) == this_month
                                 for r in rows)
        return {"registered": True, "already_granted_this_month": granted_this_month,
               "is_self": False}

    # ── the granter's own history — «المنح» ────────────────────────────────────────────────────
    async def history(self, granter_tenant: str, limit: int = 100) -> list[CouponAttempt]:
        rows, _ = await self._s.find(
            COUPON_ATTEMPTS, {"tenant": PLATFORM, "granter_tenant": granter_tenant},
            limit=limit, sort=("created", "desc"))
        return [CouponAttempt(**{k: v for k, v in r.items() if k != "tenant"}) for r in rows]

    async def _best_active_percent(self, beneficiary_tenant: str, app_key: str,
                                   now: int) -> int:
        """The highest percent this beneficiary already carries for this app, among grants not yet
        expired — from ANY granter, not just this one. A shop granting a NEW coupon must beat this
        or the grant is refused outright (`ALREADY_HAS_BETTER`), so a lower coupon can never sit on
        top of a stronger one, and a shop cannot game its own daily activity by handing out coupons
        nobody can ever actually use.

        `store.find` is equality-only, so `expires_at` cannot be filtered server-side — read every
        row for this (beneficiary, app) pair (a small, naturally bounded set: at most one live
        coupon per granter at a time, per this same rule applied on ITS OWN creation) and filter in
        Python."""
        rows, _ = await self._s.find(
            COUPON_GRANTS,
            {"tenant": PLATFORM, "beneficiary_tenant": beneficiary_tenant, "app_key": app_key},
            limit=1000)
        live = [int(r.get("percent") or 0) for r in rows if float(r.get("expires_at") or 0) > now]
        return max(live) if live else 0

    async def grants_for(self, granter_tenant: str, limit: int = 100) -> list[CouponGrant]:
        rows, _ = await self._s.find(
            COUPON_GRANTS, {"tenant": PLATFORM, "granter_tenant": granter_tenant},
            limit=limit, sort=("created", "desc"))
        return [CouponGrant(**{k: v for k, v in r.items() if k != "tenant"}) for r in rows]

    # ── stats for this app's own screen — grounded in real, already-collected data ─────────────
    async def stats(self, granter_tenant: str) -> dict[str, Any]:
        now = _now()
        this_month = await self.monthly_grant_count(granter_tenant, _month_key(now))
        settings = await self.settings()
        cap = await self.effective_cap(granter_tenant)
        next_tier = next((t for t in settings.tiers if t.percent > cap), None)
        # THE 6-MONTH TREND — the console's own stats tab chart, month_key left un-formatted
        # (locale/month-name rendering is the operator-i18n screen's job, never this service's).
        history = [{"month_key": _month_key_offset(now, i),
                   "grants": await self.monthly_grant_count(
                       granter_tenant, _month_key_offset(now, i))}
                  for i in range(5, -1, -1)]
        return {
            "grants_this_month": this_month,
            "current_cap_percent": cap,
            "ceiling_percent": settings.ceiling_percent,
            "next_tier_percent": next_tier.percent if next_tier else None,
            "next_tier_grants_needed": (
                max(0, next_tier.max_grants - this_month + 1) if next_tier else None),
            "history": history,
        }
