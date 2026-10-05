"""Customer-service freelancer CRM — business rules, the filtered customer list, the freelancer's
own actions, the escalation inbox, and call notes/export. `core/freelancer_service.py` owns WHO
may act (the link table, the authorization boundary); this module owns WHAT they can do once
authorized, scoped to exactly one tenant per call — every method here takes `tenant` and every
store query is filtered by it, same discipline that module's own docstring states.

REWARDS REUSE REAL ENGINES, NEVER A SHADOW ONE. "نقاط" grants call `LoyaltyDesk.award()` —
the SAME non-visit points primitive `core/referral_redemption.py` already uses (tagged
`reason="freelancer_reward"` here instead of `"referral"`) — a real, immediate points credit.
"خصم"/"هدية" have no equivalent off-visit redemption engine anywhere in this codebase today (every
existing discount/reward path is visit- or order-scoped); granting one here is recorded as a real,
audited `FreelancerRewardGrant` row the shop's own staff honours by hand at the customer's next
visit, rather than inventing a second, parallel discount-application engine duplicating
`core/best_offer.py`'s own job.

THE COOLDOWN IS ABOUT THE FREELANCER'S OWN LAST TOUCH, NOT THE SHOP'S LAST VISIT (docs/جديد.txt
§"قائمة العملاء" — "لا يظهر عميل تم التواصل معه حديثاً"). `FreelancerContact.last_contacted_at`
is a fact about THIS customer-service channel, kept separate from `Customer.last_visit` (a fact
about the shop floor) on purpose — a customer who visited yesterday and was never called by a
freelancer must still appear; a customer not visited in months but called by a freelancer
yesterday must still be hidden.

AUTO-HIDE, THEN AUTO-RETURN — rating or escalating a customer stamps `last_contacted_at = now`,
which is the ONE write that drives visibility (`_is_visible` below); nothing deletes or archives
the customer, and once `cooldown_days` elapses the same customer simply computes visible again on
the next read. `do_not_disturb=True` is the one permanent exception — it never expires on its own.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

FREELANCER_RULES = "customer_service_rules"
FREELANCER_CONTACTS = "customer_service_contacts"
FREELANCER_REWARD_OPTIONS = "customer_service_reward_options"
FREELANCER_REWARD_GRANTS = "customer_service_reward_grants"
FREELANCER_ESCALATIONS = "customer_service_escalations"
FREELANCER_NOTES = "customer_service_notes"

SATISFIED = "satisfied"
NEUTRAL = "neutral"
UNSATISFIED = "unsatisfied"
RATINGS = frozenset({SATISFIED, NEUTRAL, UNSATISFIED})

DISCOUNT = "discount"
POINTS = "points"
GIFT = "gift"
REWARD_KINDS = frozenset({DISCOUNT, POINTS, GIFT})

OPEN = "open"
RESOLVED = "resolved"


class FreelancerCrmError(Exception):
    """A refusal the caller (an API route) can show verbatim."""


def _now() -> int:
    return int(time.time())


@dataclass
class BusinessRules:
    tenant: str
    cooldown_days: int = 30
    daily_cap: int = 5            # max rewards one freelancer may grant per day, docs/جديد.txt §1
    quiet_start_minute: int = 0   # minutes from local midnight; 0+0 = no quiet-hours restriction
    quiet_end_minute: int = 0

    def public(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RewardOption:
    id: str
    tenant: str
    kind: str                     # discount | points | gift
    label: str                    # what the freelancer sees, e.g. "خصم 10%" / "50 نقطة" / "غسيل مجاني"
    # ONE of these is meaningful per `kind` — percent for discount, points for points, nothing extra
    # for gift (the label alone names it, docs/جديد.txt §"الهدايا المجانية").
    percent: int = 0
    points: int = 0
    active: bool = True

    def public(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FreelancerContact:
    tenant: str
    customer_id: str
    last_contacted_at: int = 0
    last_status: str = ""
    do_not_disturb: bool = False

    def public(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Escalation:
    id: str
    tenant: str
    customer_id: str
    freelancer_phone: str
    note: str
    status: str
    created: int
    resolved_at: int = 0
    resolved_by: str = ""
    resolution_note: str = ""

    def public(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CallNote:
    id: str
    tenant: str
    customer_id: str
    author_phone: str           # the freelancer's own phone, or a staff subject for the internal tab
    text: str
    status: str
    services: list[str] = field(default_factory=list)
    created: int = 0

    def public(self) -> dict[str, Any]:
        return asdict(self)


class FreelancerCrmService:
    def __init__(self, *, store: Any, customers: Any, loyalty: Any = None,
                notifier: Any = None, default_daily_cap: int = 5) -> None:
        self._s = store
        self._customers = customers     # CustomerStore
        self._loyalty = loyalty         # LoyaltyDesk — None-safe, see grant_reward()
        self._notifier = notifier       # InAppNotifier — None-safe, see escalate()
        self._default_cap = default_daily_cap

    # ── business rules ─────────────────────────────────────────────────────────────────────────
    async def get_rules(self, tenant: str) -> BusinessRules:
        raw = await self._s.get(FREELANCER_RULES, tenant)
        if raw is None:
            return BusinessRules(tenant=tenant, daily_cap=self._default_cap)
        return BusinessRules(**{k: v for k, v in raw.items() if k != "tenant_key"})

    async def set_rules(self, tenant: str, *, cooldown_days: int, daily_cap: int,
                        quiet_start_minute: int = 0, quiet_end_minute: int = 0) -> BusinessRules:
        if cooldown_days < 0 or daily_cap < 0:
            raise FreelancerCrmError("القيم المدخلة غير صحيحة")
        rules = BusinessRules(tenant=tenant, cooldown_days=cooldown_days, daily_cap=daily_cap,
                              quiet_start_minute=quiet_start_minute,
                              quiet_end_minute=quiet_end_minute)
        await self._s.put(FREELANCER_RULES, tenant, rules.public())
        return rules

    # ── reward catalog ─────────────────────────────────────────────────────────────────────────
    async def list_reward_options(self, tenant: str) -> list[RewardOption]:
        rows, _ = await self._s.find(FREELANCER_REWARD_OPTIONS, {"tenant": tenant, "active": True},
                                     limit=50)
        return [RewardOption(**{k: v for k, v in r.items() if k != "tenant_key"}) for r in rows]

    async def add_reward_option(self, tenant: str, *, kind: str, label: str,
                                percent: int = 0, points: int = 0) -> RewardOption:
        if kind not in REWARD_KINDS:
            raise FreelancerCrmError("نوع الترضية غير معروف")
        if not label.strip():
            raise FreelancerCrmError("اسم الترضية مطلوب")
        if kind == DISCOUNT and not (0 < percent <= 100):
            raise FreelancerCrmError("نسبة الخصم يجب أن تكون بين 1 و100")
        if kind == POINTS and points <= 0:
            raise FreelancerCrmError("عدد النقاط يجب أن يكون أكبر من صفر")
        opt = RewardOption(id=uuid.uuid4().hex, tenant=tenant, kind=kind, label=label.strip(),
                          percent=percent, points=points, active=True)
        await self._s.put(FREELANCER_REWARD_OPTIONS, f"{tenant}|{opt.id}", opt.public())
        return opt

    # ── contact/cooldown ────────────────────────────────────────────────────────────────────────
    async def _contact(self, tenant: str, customer_id: str) -> FreelancerContact:
        raw = await self._s.get(FREELANCER_CONTACTS, f"{tenant}|{customer_id}")
        if raw is None:
            return FreelancerContact(tenant=tenant, customer_id=customer_id)
        return FreelancerContact(**{k: v for k, v in raw.items() if k != "tenant_key"})

    async def _touch(self, tenant: str, customer_id: str, *, status: str = "") -> None:
        c = await self._contact(tenant, customer_id)
        c.last_contacted_at = _now()
        if status:
            c.last_status = status
        await self._s.put(FREELANCER_CONTACTS, f"{tenant}|{customer_id}", c.public())

    async def _is_visible(self, tenant: str, customer_id: str, rules: BusinessRules) -> bool:
        c = await self._contact(tenant, customer_id)
        if c.do_not_disturb:
            return False
        if c.last_contacted_at == 0:
            return True
        return _now() - c.last_contacted_at >= rules.cooldown_days * 86400

    async def filtered_customers(self, tenant: str, *, limit: int = 100, search: str = "",
                                 status_filter: str = "") -> list[dict[str, Any]]:
        """docs/جديد.txt §"قائمة العملاء" — name, last shop visit, cooldown-filtered. Reuses
        `CustomerStore.recent()` (the same recent-customers read every other screen already makes)
        as the candidate pool rather than draining the whole table on every freelancer page load.

        `search` matches name OR phone, case-insensitively — one box, no "search by" picker the
        freelancer has to think about first. `status_filter` is `""` (any), `"new"` (never
        contacted by this channel — `last_status` empty, the console's own "لم يتواصل معه أحد
        بعد" option), or one of `RATINGS` — read off the SAME `FreelancerContact` row
        `_is_visible` already reads, so it costs nothing extra beyond what this call already does
        per candidate."""
        rules = await self.get_rules(tenant)
        pool = await self._customers.recent(tenant, limit=max(limit * 4, 200))
        needle = search.strip().lower()
        out: list[dict[str, Any]] = []
        for cust in pool:
            if len(out) >= limit:
                break
            if needle and needle not in cust.name.lower() and needle not in cust.phone.lower():
                continue
            contact = await self._contact(tenant, cust.id)
            if contact.do_not_disturb:
                continue
            if contact.last_contacted_at and _now() - contact.last_contacted_at < rules.cooldown_days * 86400:
                continue
            last_status = contact.last_status
            if status_filter == "new" and last_status:
                continue
            if status_filter in RATINGS and last_status != status_filter:
                continue
            out.append({
                "customer_id": cust.id, "name": cust.name, "phone": cust.phone,
                "last_visit": cust.last_visit, "last_status": last_status,
            })
        return out

    # ── freelancer actions ──────────────────────────────────────────────────────────────────────
    async def rate(self, tenant: str, customer_id: str, *, status: str, by: str) -> None:
        if status not in RATINGS:
            raise FreelancerCrmError("تقييم غير معروف")
        await self._touch(tenant, customer_id, status=status)

    async def set_do_not_disturb(self, tenant: str, customer_id: str) -> None:
        c = await self._contact(tenant, customer_id)
        c.do_not_disturb = True
        c.last_contacted_at = _now()
        await self._s.put(FREELANCER_CONTACTS, f"{tenant}|{customer_id}", c.public())

    async def _today_grant_count(self, tenant: str, by: str) -> int:
        day_start = _now() - (_now() % 86400)
        rows, _ = await self._s.find(
            FREELANCER_REWARD_GRANTS, {"tenant": tenant, "granted_by": by}, limit=200)
        return sum(1 for r in rows if int(r.get("created", 0)) >= day_start)

    async def grant_reward(self, tenant: str, customer_id: str, *, option_id: str,
                           by: str, subject_ref: str = "") -> dict[str, Any]:
        """The daily cap (docs/جديد.txt §1 "الحد اليومي للمكافآت") is checked here, the one place
        a reward is ever granted — never trusted from a caller who could omit it."""
        rules = await self.get_rules(tenant)
        if await self._today_grant_count(tenant, by) >= rules.daily_cap:
            raise FreelancerCrmError("وصلت الحد اليومي للترضيات المسموحة")

        raw = await self._s.get(FREELANCER_REWARD_OPTIONS, f"{tenant}|{option_id}")
        if raw is None or not raw.get("active"):
            raise FreelancerCrmError("الترضية غير متاحة")
        opt = RewardOption(**{k: v for k, v in raw.items() if k != "tenant_key"})

        points_awarded = None
        if opt.kind == POINTS and self._loyalty is not None and subject_ref:
            points_awarded = await self._loyalty.award(
                tenant=tenant, subject_ref=subject_ref, points=opt.points,
                idempotency_key=f"freelancer_reward:{tenant}:{customer_id}:{uuid.uuid4().hex}",
                reason="freelancer_reward", actor=by)

        grant = {
            "id": uuid.uuid4().hex, "tenant": tenant, "customer_id": customer_id,
            "option_id": option_id, "kind": opt.kind, "label": opt.label,
            "percent": opt.percent, "points": opt.points,
            "granted_by": by, "created": _now(),
            # TRUE only when the real loyalty credit actually landed — a discount/gift grant is
            # recorded "pending honour" (the shop's own staff applies it manually at the next
            # visit), never claimed as already fulfilled when nothing was actually credited yet.
            "fulfilled": points_awarded is not None,
        }
        await self._s.put(FREELANCER_REWARD_GRANTS, f"{tenant}|{grant['id']}", grant)
        await self._touch(tenant, customer_id)
        return grant

    async def escalate(self, tenant: str, customer_id: str, *, note: str, freelancer_phone: str,
                       recipients: list[str]) -> Escalation:
        esc = Escalation(id=uuid.uuid4().hex, tenant=tenant, customer_id=customer_id,
                         freelancer_phone=freelancer_phone, note=note.strip()[:1000],
                         status=OPEN, created=_now())
        await self._s.put(FREELANCER_ESCALATIONS, f"{tenant}|{esc.id}", esc.public())
        await self._touch(tenant, customer_id, status="escalated")
        if self._notifier is not None:
            for user_id in recipients:
                await self._notifier.send(
                    tenant=tenant, user_id=user_id,
                    template_key="operations.freelancer_escalated",
                    variables={"customer_id": customer_id},
                    idempotency_key=f"freelancer_escalation:{esc.id}:{user_id}")
        return esc

    async def list_escalations(self, tenant: str, *, status: str = "") -> list[Escalation]:
        where: dict[str, Any] = {"tenant": tenant}
        if status:
            where["status"] = status
        rows, _ = await self._s.find(FREELANCER_ESCALATIONS, where, limit=100,
                                     sort=("created", "desc"))
        return [Escalation(**{k: v for k, v in r.items() if k != "tenant_key"}) for r in rows]

    async def resolve_escalation(self, tenant: str, escalation_id: str, *, resolved_by: str,
                                 resolution_note: str = "", new_status: str = SATISFIED) -> Escalation:
        """docs/جديد.txt §"تجاوز الحالة" — the shop's own resolution overrides the customer's
        last-known satisfaction read, since the freelancer's own escalation was the LAST signal
        before the shop stepped in and fixed it."""
        raw = await self._s.get(FREELANCER_ESCALATIONS, f"{tenant}|{escalation_id}")
        if raw is None or raw.get("tenant") != tenant:
            raise FreelancerCrmError("التصعيد غير موجود")
        esc = Escalation(**{k: v for k, v in raw.items() if k != "tenant_key"})
        if esc.status == RESOLVED:
            return esc
        esc.status = RESOLVED
        esc.resolved_at = _now()
        esc.resolved_by = resolved_by
        esc.resolution_note = resolution_note.strip()[:1000]
        await self._s.put(FREELANCER_ESCALATIONS, f"{tenant}|{esc.id}", esc.public())
        if new_status in RATINGS:
            await self._touch(tenant, esc.customer_id, status=new_status)
        return esc

    # ── call notes + export ─────────────────────────────────────────────────────────────────────
    async def add_note(self, tenant: str, customer_id: str, *, text: str, author_phone: str,
                       status: str, services: list[str] | None = None) -> CallNote:
        note = CallNote(id=uuid.uuid4().hex, tenant=tenant, customer_id=customer_id,
                        author_phone=author_phone, text=(text or "لا يوجد").strip()[:2000],
                        status=status, services=services or [], created=_now())
        await self._s.put(FREELANCER_NOTES, f"{tenant}|{note.id}", note.public())
        return note

    async def export_notes(self, tenant: str, *, since: int, until: int,
                           include_pii: bool = False) -> str:
        """docs/جديد.txt's own export update: notes + services + (optionally) personal data,
        filtered to [since, until). PII-safe by DEFAULT — `include_pii=True` is an explicit,
        logged choice the caller makes, never the quiet default (module docstring's own privacy
        posture, mirrored from every other export in this service)."""
        rows, _ = await self._s.find(FREELANCER_NOTES, {"tenant": tenant}, limit=5000,
                                     sort=("created", "asc"))
        customers: dict[str, Any] = {}
        if include_pii:
            ids = {r["customer_id"] for r in rows}
            customers = await self._customers.get_many(tenant, ids)

        lines: list[str] = []
        for r in rows:
            created = int(r.get("created", 0))
            if created < since or created >= until:
                continue
            who = ""
            if include_pii:
                cust = customers.get(r["customer_id"])
                who = f"{cust.name} ({cust.phone})" if cust else r["customer_id"]
            services = "، ".join(r.get("services") or []) or "—"
            lines.append(
                f"[{created}] {who or 'عميل'} — الحالة: {r.get('status','')} — "
                f"الخدمات: {services}\n{r.get('text','')}")
        return "\n\n".join(lines)
