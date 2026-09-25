"""Which of this product's domains a branch actually means something to — the single answer,
read from here, instead of re-litigated per screen and per route.

WHY THIS REGISTRY EXISTS. The owner's own words drew the real line: a shop with «فرع جدة» and
«فرع الشرقية», each with its own manager, and that manager must never read the other branch's
customers, visits or ratings. But not every domain in this product has a branch dimension at all —
جهات الاتصال and نقاط الولاء answer to the SHOP, not to a physical location, and forcing a branch filter
onto them would be inventing a restriction nobody asked for. Getting this wrong in either direction
is a real defect: too little scoping leaks one manager's customers to another (the exact bug this
session found already shipped once, see `campaigns_send_log` below); too much scoping breaks a
domain that is legitimately shop-wide.

THIS FILE IS THE AUTHORITY, NOT EACH ROUTE'S OWN JUDGMENT — the same convention already used by
`apps/console/src/apps.ts` (`APP_ROWS`) and `apps/console/src/nav.ts` (`SECTIONS`): a screen or a
route reads this list rather than re-deciding "does branch apply here" inline, so the decision is
made once, with its evidence attached, and never drifts between two files that quietry disagree.

WHERE THIS LIVES. `services/operations` is where it started because operations already carries the
cross-cutting, non-domain-specific registries this codebase keeps (`core/apps.py`'s own `APPS`).
No shared package that every service imports exists yet in this repo (each service keeps its own
`app/core/*`, not a common library) — so for now only operations reads this file. A future service
that needs the same classification (insights, loyalty, bookings themselves, to check their own
routes against this file rather than trust their own memory of "is this domain branch-scoped") should
either import this module directly (services already reach across each other's `app/api/internal.py`
routes over HTTP, so a straight Python import across service boundaries is not this codebase's
pattern) or, more likely, this file should move into a real shared package the day a second service
needs it. That move is deliberately NOT done here — it is a bigger change than one review pass
should carry, and nothing today reads this file except operations.

STEP 1 OF A LARGER PLAN. This module is the registry ONLY — no route, store, adapter or screen has
been wired to it yet. That wiring is later work, done after a human review of this file, so that
review stays small enough to read line by line.

`apps/console/src/branch-domains.ts` IS A HAND-WRITTEN MIRROR OF THIS FILE for the console's own
use — no Python→TypeScript codegen exists in this repo, and this file stays the one source of
truth an edit here is expected to be carried over there by hand (and vice versa).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class BranchDomainInfo:
    """One product domain's real branch-scoping answer, with its evidence attached — never an
    unbacked claim (`evidence` is required, not optional, for exactly that reason)."""

    id: str
    #: The Arabic name already used for this domain elsewhere in the codebase (apps.ts / nav.ts),
    #: reused verbatim so this file never invents a second name for the same thing.
    label_ar: str
    branch_scoped: bool
    #: Set ONLY for `mobile_requests` — its scoping is not a plain `branch_id` filter but derived
    #: from whichever operator is currently assigned to the request. `None` for every other domain,
    #: including every platform-level one.
    derived_from: Optional[str]
    #: A short pointer to the real file:line (or file + comment) this classification was read
    #: from, so nobody has to re-audit the codebase to trust the entry.
    evidence: str


# ── branch-scoped: a manager at one branch must not see another branch's records ────────────────
_BRANCH_SCOPED: tuple[BranchDomainInfo, ...] = (
    BranchDomainInfo(
        id="visit",
        label_ar="تسجيل زيارة",
        branch_scoped=True,
        derived_from=None,
        evidence="services/operations/app/api/v1/staff.py ~L1138: \"visits, points movements "
                  "and schedules all carry a `branch_id`\"",
    ),
    BranchDomainInfo(
        id="customers",
        label_ar="جهات الاتصال",
        branch_scoped=True,
        derived_from=None,
        evidence="services/operations/app/api/v1/field.py: recent_customers/resolve_customers/"
                  "suggest_customers all resolve branch_scope(...) before filtering",
    ),
    BranchDomainInfo(
        id="rating",
        label_ar="التقييم",
        branch_scoped=True,
        derived_from=None,
        evidence="services/operations/app/api/v1/field.py: ratings/staff_performance, same "
                  "branch_scope pattern as customers",
    ),
    BranchDomainInfo(
        id="bookings",
        label_ar="الحجوزات",
        branch_scoped=True,
        derived_from=None,
        evidence="services/bookings/app/api/internal.py takes real branch_id filters; its own "
                  "services/bookings/app/adapters/branch_scope.py",
    ),
    BranchDomainInfo(
        id="shop_insights",
        label_ar="محلّي",
        branch_scoped=True,
        derived_from=None,
        evidence="services/insights/app/api/v1/insights.py _snapshot/dashboard take branch_id; "
                  "ci/check_branch_scope.py's own BRANCH_READS lists branch_rows/"
                  "branch_comparison/branch_snapshot/branch_can_rank/branch_stats",
    ),
    BranchDomainInfo(
        id="team",
        label_ar="فريقي",
        branch_scoped=True,
        derived_from=None,
        evidence="services/operations/app/api/v1/staff.py: an operator's own branch_id (station) "
                  "and visible_branch_ids (what they may see) are real first-class fields",
    ),
    BranchDomainInfo(
        id="whatsapp_connect",
        label_ar="ربط واتساب",
        branch_scoped=True,
        derived_from=None,
        evidence="services/operations/app/api/v1/connect.py whatsapp_connect_status(branch_id=...), "
                  "one connection per branch",
    ),
    BranchDomainInfo(
        id="campaigns_send_log",
        label_ar="الحملات",
        branch_scoped=True,
        derived_from=None,
        evidence="services/reminders/app/api/v1/owner.py send_log: real branch_scope-enforced GET, "
                  "with its own in-code comment about the past bug where a manager assigned to "
                  "Jeddah read every message sent in Riyadh's name",
    ),
    BranchDomainInfo(
        id="mobile_requests",
        label_ar="خدمات متنقلة",
        branch_scoped=True,
        derived_from="assigned_operator_branch",
        evidence="owner decision (this session): same branch boundaries as everything else, but "
                 "via the ASSIGNED technician — a mobile request carries no branch_id of its own "
                 "(the technician travels to the customer, not to a shop branch); unassigned "
                 "requests stay visible to every branch's manager, and only narrow to the "
                 "assigned technician's own branch once someone is assigned",
    ),
)

# ── platform-level: shop-wide, branch has no meaning here at all ────────────────────────────────
_PLATFORM_LEVEL: tuple[BranchDomainInfo, ...] = (
    BranchDomainInfo(
        id="services_catalogue",
        label_ar="خدماتي ومنتجاتي",
        branch_scoped=False,
        derived_from=None,
        evidence="no branch_id anywhere in services/operations/app/api/v1/catalogue.py",
    ),
    BranchDomainInfo(
        id="loyalty_points",
        label_ar="نقاط الولاء",
        branch_scoped=False,
        derived_from=None,
        evidence="services/loyalty/app/api/internal.py's own comment: \"A chain's balance is one "
                  "across its branches (§12.2)\" — every branch_id inside loyalty is "
                  "write-attribution metadata only, never a read filter",
    ),
    BranchDomainInfo(
        id="partner_loyalty",
        label_ar="ولاء الشركاء",
        branch_scoped=False,
        derived_from=None,
        evidence="shop-to-shop discount on the OTHER shop's own subscription — no branch concept "
                  "applies to a cross-tenant subscription grant",
    ),
    BranchDomainInfo(
        id="referral_partnership",
        label_ar="شراكة استراتيجية",
        branch_scoped=False,
        derived_from=None,
        evidence="cross-tenant, company-wide by definition — core/referral_partnership.py's own "
                  "module docstring",
    ),
    BranchDomainInfo(
        id="whatsapp_assistant",
        label_ar="المساعد الذكي عبر واتساب",
        branch_scoped=False,
        derived_from=None,
        evidence="the paid AI-agent app, distinct from whatsapp_connect above — no branch "
                  "dimension in its own routes",
    ),
    BranchDomainInfo(
        id="mobile_ai_assistant",
        label_ar="المساعد الذكي (تطبيق الجوال)",
        branch_scoped=False,
        derived_from=None,
        evidence="on-device mobile-app assistant, no server-side branch concept at all",
    ),
    BranchDomainInfo(
        id="support",
        label_ar="الدعم الفني",
        branch_scoped=False,
        derived_from=None,
        evidence="ticket-service's tickets.self capability is granted per owner/manager, never "
                  "per branch",
    ),
    BranchDomainInfo(
        id="billing_account",
        label_ar="حسابي",
        branch_scoped=False,
        derived_from=None,
        evidence="billing is one subscription per shop, not per branch",
    ),
    BranchDomainInfo(
        id="campaigns_authoring",
        label_ar="الحملات",
        branch_scoped=False,
        derived_from=None,
        evidence="composing/sending a campaign and choosing its audience is explicitly not "
                  "branch-restricted — existing product decision: a branch checkbox there is an "
                  "audience CHOICE, never an access boundary (see campaigns_send_log above for "
                  "the split)",
    ),
)

#: The full registry — the only thing outside code should ever iterate.
BRANCH_DOMAINS: tuple[BranchDomainInfo, ...] = _BRANCH_SCOPED + _PLATFORM_LEVEL

#: Lookup by id, built once at import time — the shape every future caller actually wants.
BRANCH_DOMAINS_BY_ID: dict[str, BranchDomainInfo] = {d.id: d for d in BRANCH_DOMAINS}


def is_branch_scoped(domain_id: str) -> bool:
    """Whether `domain_id` should be filtered/restricted by branch. Raises `KeyError` for an
    unknown id on purpose — a typo here must fail loudly, not silently read as platform-level."""
    return BRANCH_DOMAINS_BY_ID[domain_id].branch_scoped
