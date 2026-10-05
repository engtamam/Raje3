"""Customer service freelancers — docs/جديد.txt's own spec, implementation plan at
docs/خطة-تنفيذ-خدمة-العملاء.md. A shop may hand its own post-visit customer-service work to an
EXTERNAL person it brought in itself (never a marketplace we introduce — the module never lists,
ranks or recommends a freelancer; a shop types in a phone number it already has a relationship
with, same "the platform is a tool, never a broker" posture `core/coupons.py`'s own module
docstring takes for shop-to-shop discounts).

THIS MODULE IS THE AUTHORIZATION BOUNDARY, NOT JUST A LINK TABLE — read this section before
touching anything here, it is the whole point of the file.

A freelancer is NOT a staff role. `deploy/seed/roles.json` governs who on the shop's OWN payroll
may do what; this table governs an OUTSIDE person who holds no capability from that file at all.
The two systems never merge:

  * `operations.freelancer_manage` (granted to owner/manager/marketer/supervisor in roles.json,
    explicitly withheld from `operator` — the field role does not run customer-service escalations
    — AND from `partner` — the till-reseller role, which is walled off from ever seeing a shop's
    own customers or their phone numbers by DESIGN, `deploy/seed/roles.json`'s own
    `partner.description`; granting it here would be the exact leak that role exists to prevent,
    owner's own explicit call, 2026-10-05) is what lets a shop's OWN staff manage this table —
    add/remove a freelancer, set the business rules, resolve an escalation.

  * A freelancer's OWN session, once built (docs/خطة-تنفيذ-خدمة-العملاء.md's own Stage 6), is an
    ORDINARY tenant-scoped token exactly like any staff member's — same `Principal` shape, same
    single-tenant claim, same `require_capability` machinery — carrying EXACTLY ONE capability,
    `operations.freelancer_portal`, and NEVER any other. The token is minted by looking a phone
    number up in THIS table instead of in `roles.json`, which is the only place the two systems
    touch. A freelancer token can therefore never carry `operations.manage`, `operations.record`,
    or anything else no matter how the issuing code is later changed, because this table has no
    column that could ever produce one.

MAX 3 ACTIVE LINKS PER TENANT (docs/جديد.txt §3, "الربط... حد أقصى 3") — enforced here, in
`add()`, the one place a link is ever created; never trusted from a caller who could omit the
check. The shop must deactivate or remove one before adding a fourth — never silently replaced.

TENANT ISOLATION. Every read in this module is scoped by `tenant` in the store query itself
(`find(..., where={"tenant": tenant, ...})`), never filtered in Python after a broader read — the
same discipline `core/mutual_benefit.py`'s own module docstring states for its cross-tenant rows,
applied here even though every row here belongs to exactly one tenant (defence in depth: a bug
that widens the query must still not widen what is returned without a second bug alongside it).

A FREELANCER'S OWN PHONE NUMBER IS THE LOOKUP KEY FOR ITS SESSION (Stage 6), so it is stored
CANONICAL (`core/signup.py::canonical_phone`), the same normalized "+<digits>" shape every other
phone-keyed table in this service already uses — a session lookup that compared un-normalized
strings would silently fail to find a real, already-linked freelancer typed in a second time with
different formatting.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass
from typing import Any

from app.core.signup import canonical_phone

FREELANCER_LINKS = "customer_service_freelancers"
MAX_ACTIVE_FREELANCERS_PER_TENANT = 3

FREELANCER_PORTAL_CAPABILITY = "operations.freelancer_portal"


class FreelancerError(Exception):
    """A refusal the caller (an API route) can show verbatim."""


def _now() -> int:
    return int(time.time())


@dataclass
class FreelancerLink:
    id: str
    tenant: str
    phone: str                # canonical "+<digits>" — see module docstring
    display_name: str          # the freelancer's own chosen display name, never forced to show a
                               # real photo/identity to the shop (docs/جديد.txt §"حماية الهوية")
    active: bool
    created: int
    created_by: str             # the staff member's own subject — who actually added this person

    def public(self) -> dict[str, Any]:
        return asdict(self)


class FreelancerService:
    """Add/remove/list the freelancers a shop has linked. Nothing in this class ever reaches
    across tenants — see module docstring's own "TENANT ISOLATION" section."""

    def __init__(self, *, store: Any, default_cc: str) -> None:
        self._s = store
        self._cc = default_cc

    async def list(self, tenant: str, *, include_inactive: bool = False) -> list[FreelancerLink]:
        where: dict[str, Any] = {"tenant": tenant}
        if not include_inactive:
            where["active"] = True
        rows, _ = await self._s.find(FREELANCER_LINKS, where, limit=50, sort=("created", "asc"))
        return [FreelancerLink(**{k: v for k, v in r.items() if k != "tenant_key"}) for r in rows]

    async def add(self, tenant: str, *, phone: str, display_name: str, actor: str) -> FreelancerLink:
        """Refuses past the cap (docs/جديد.txt §3 — 3 active links at a time) and refuses a phone
        already linked to this SAME tenant twice (re-adding an existing freelancer silently would
        hide that a second row now exists for the same person, each with its own id)."""
        phone_c = canonical_phone(phone, default_cc=self._cc)
        if not phone_c:
            raise FreelancerError("رقم الجوال غير صحيح")
        name = display_name.strip()
        if not name:
            raise FreelancerError("اسم المستقل مطلوب")

        active = await self.list(tenant)
        if any(f.phone == phone_c for f in active):
            raise FreelancerError("هذا الرقم مرتبط بمنشأتك بالفعل")
        if len(active) >= MAX_ACTIVE_FREELANCERS_PER_TENANT:
            raise FreelancerError(
                f"وصلت الحد الأقصى ({MAX_ACTIVE_FREELANCERS_PER_TENANT} مستقلين) — "
                "احذف أو عطّل أحدهم أولاً")

        row = FreelancerLink(
            id=uuid.uuid4().hex, tenant=tenant, phone=phone_c, display_name=name,
            active=True, created=_now(), created_by=actor,
        )
        await self._s.put(FREELANCER_LINKS, f"{tenant}|{row.id}", row.public())
        return row

    async def deactivate(self, tenant: str, link_id: str) -> FreelancerLink:
        """Deactivate, never delete — a deactivated link's own id stays a stable reference for
        anything already pointing at it (an escalation row, a redeemed reward's own audit trail),
        same "never truly gone, just no longer live" posture every other soft-stop row in this
        service already takes."""
        raw = await self._s.get(FREELANCER_LINKS, f"{tenant}|{link_id}")
        if raw is None or raw.get("tenant") != tenant:
            raise FreelancerError("المستقل غير موجود")
        row = FreelancerLink(**{k: v for k, v in raw.items() if k != "tenant_key"})
        if not row.active:
            return row
        row.active = False
        await self._s.put(FREELANCER_LINKS, f"{tenant}|{row.id}", row.public())
        return row

    async def tenants_for_phone(self, phone: str) -> list[str]:
        """Every tenant a phone number is an ACTIVE freelancer for — Stage 6's own "pick a shop"
        step reads this, nothing else does. Scans by phone across tenants on purpose (the one
        intentional exception to this module's own tenant-scoped-query rule, since a freelancer's
        identity is phone-first, not tenant-first) — returns only tenant ids, never another
        tenant's own data about the freelancer, so a shop can never learn which OTHER shops a
        freelancer works for from this call."""
        phone_c = canonical_phone(phone, default_cc=self._cc)
        if not phone_c:
            return []
        rows, _ = await self._s.find(
            FREELANCER_LINKS, {"phone": phone_c, "active": True}, limit=50)
        return sorted({r["tenant"] for r in rows if r.get("tenant")})
