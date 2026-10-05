# =============================================================================
# operations — Self-describing service manifest
# -----------------------------------------------------------------------------
# A machine-readable descriptor so a gateway/platform can discover what this
# service is, what it exposes, which ports (adapters) it uses, and which events
# it emits/consumes. Served at GET /internal/manifest. Phase 1: ports/events are
# empty; later phases populate them.
# =============================================================================
from __future__ import annotations

from typing import Any

from app.config import Settings


def _backup() -> dict:
    """This service's backup declaration (app/backup_manifest.py), or an empty one.

    Published in the manifest so the backup fan-out discovers what to capture the same way the DSAR
    fan-out discovers who holds a person — a holder nobody declares is one nobody backs up."""
    try:
        from app.backup_manifest import BACKUP
    except Exception:
        return {"object_prefix": "", "collections": [], "excluded": []}
    return BACKUP


def _admin_actions() -> list[dict[str, Any]]:
    """This service's declared admin actions (docs/contracts/admin-actions.schema.json), or [] if it
    declares none. Opt-in: a service with no app/admin_actions.py simply exposes nothing to the
    panel. The panel is a map — these decide what is SHOWN, never what an operator may DO."""
    try:
        from app.admin_actions import ADMIN_ACTIONS
    except Exception:
        return []
    return list(ADMIN_ACTIONS)


def _user_actions() -> list[dict[str, Any]]:
    """This service's declared end-user (self-service) actions
    (docs/contracts/user-actions.schema.json), or [] if it declares none. Opt-in: aggregated into
    GET /api/v1/app/catalog. The app is a map — these decide what is SHOWN, never what a user may DO."""
    try:
        from app.user_actions import USER_ACTIONS
    except Exception:
        return []
    return list(USER_ACTIONS)


def build_manifest(
    settings: Settings, ports: list[dict[str, str]] | None = None
) -> dict[str, Any]:
    return {
        "name": settings.SERVICE_NAME,
        "version": settings.SERVICE_VERSION,
        "env": settings.ENV,
        # FILL THIS. An empty list is a CLAIM — "this service grants no capabilities" — that an
        # adopter's client app reads as fact and renders nothing from. A blank app is the usual
        # symptom of a service that shipped this untouched. If a service genuinely grants none,
        # leaving it empty is correct; the point is that it must be a decision, not a leftover.
        # Three, and the split is a product decision rather than a modelling one. Recording a
        # visit is what every operator does all day. Reading the customer book is a different
        # privilege — a shop that hires seasonal help should grant the first without the second.
        # Managing the catalogue, the staff and the branches is the owner's.
        "capabilities": ["operations.record", "operations.read", "operations.manage",
                         # WHAT staff.py ACTUALLY ENFORCES (require_capability/require_any_capability)
                         # but this list never named: a field operator's own "خدماتي ومنتجاتي"/
                         # "الفريق"/"الفروع" screens declared these on their own USER_ACTIONS rows,
                         # and nobody could ever hold either — found by ci/check_deploy_wiring.py's
                         # own guard 17 the day it was run for real.
                         "operations.manage_services", "bookings.read",
                         # OURS. No tenant token carries it: a tyre shop must not be able to
                         # rename "بنشر" for every other tyre shop on the product.
                         "platform.operations",
                         # THE FIRST ROLE ON THIS PRODUCT THAT IS NEITHER A TENANT NOR US. A
                         # partner has a real claim on some rows of a tenant it does not own, and
                         # none at all on the rest — see api/v1/partner.py.
                         "partner.read",
                         # THE OWNER ACTING ON HIS OWN ACCOUNT — subscribing, and connecting his
                         # WhatsApp. Not an operator capability and not one of ours: a route that
                         # needed either would mean no shop could buy or connect without us on the
                         # call, which is the opposite of a self-service product.
                         "billing.self",
                         # WHAT THE OPERATOR ROUTES ACTUALLY ENFORCE. Advertised because it is
                         # enforced here, not because we grant it to anyone: platform.* is ours,
                         # and authz denies the whole prefix to every tenant. platform.secrets was
                         # here too until the credential-management routes it gated were removed
                         # (dead SecretStore — see git history: nothing in this service ever
                         # consumed a value written through it).
                         "platform.config",
                         # SHOP-TO-SHOP COUPONS — the visit-linked door and the standalone-tab
                         # door, deliberately two capabilities (see staff.py's own comment on
                         # `_GRANT_COUPON`/`_GRANT_COUPON_DIRECT`).
                         "operations.grant_coupon", "operations.grant_coupon_direct",
                         # MOBILE/ON-THE-GO SERVICE REQUESTS — _manage is the review queue itself
                         # (owner/manager/supervisor: accept/reject/assign/complete/no-show on
                         # anything). _execute is the field operator's own SCOPED half added
                         # 2026-09-15 (assignment) — list only what THEY were assigned, and only
                         # مark تم/لم يتم on it, never accept/reject/assign (see api/v1/
                         # mobile_requests.py's own dual-capability route docstring).
                         "operations.mobile_requests_manage", "operations.mobile_requests_execute",
                         # NARROWER THAN operations.read. Gates 5 specific reads — affiliates.py's
                         # list/get/settlements and referral_reports.py's leaderboard/affiliate
                         # breakdown — that hand back an individual's phone number and payout
                         # balance, not the aggregate-only figures every operations.read holder
                         # already sees. An ordinary staff role reads the customer book without
                         # also reading who is owed money and by what phone.
                         "operations.affiliates_read"],
        "endpoints": [
            # `/api/v1/admin/ping` USED TO BE DECLARED HERE and this service has never served it.
            # It came from the generated scaffold, survived every review, and the gate that catches
            # exactly this ("the manifest declares routes this service does not serve — the console
            # renders a button that 404s") had been failing on it. /whoami answers the question it
            # was there for — is my token accepted — and that one exists.
            {"path": "/healthz", "tier": "public", "method": "GET"},
            {"path": "/readyz", "tier": "public", "method": "GET"},
            {"path": "/metrics", "tier": "public", "method": "GET"},
            {"path": "/internal/health", "tier": "internal", "method": "GET"},
            {"path": "/internal/manifest", "tier": "internal", "method": "GET"},
            {"path": "/internal/backup/export", "tier": "internal", "method": "POST"},
            {"path": "/internal/backup/import", "tier": "internal", "method": "POST"},
            {"path": "/internal/backup/verify", "tier": "internal", "method": "POST"},
            {"path": "/internal/operations/visits/batch", "tier": "internal", "method": "POST"},
            # A visit performed for no money, bought with points. Identified by PSEUDONYM because
            # the caller (`loyalty`) holds no phone number and must not be handed one.
            {"path": "/internal/operations/visits/by-ref", "tier": "internal", "method": "POST"},
            # The rating app's own write — reminders resolves the hosted rating page's submit back
            # to a visit and hands the rating here as a plain fact.
            {"path": "/internal/operations/visits/{}/rating", "tier": "internal", "method": "POST"},
            # The rating app's own READ — portal's hosted rating page asks what to show before the
            # customer answers anything ([[task-service-procedure-checklists]] phase 2).
            {"path": "/internal/operations/visits/{}/rating-context",
             "tier": "internal", "method": "POST"},
            {"path": "/internal/operations/seed-tenant", "tier": "internal", "method": "POST"},
            {"path": "/internal/signup/partner-invite", "tier": "internal", "method": "POST"},
            # The most sensitive surface this service has: it turns a pseudonym back into a phone
            # number for a peer that is about to send. One subject per call, never a list.
            {"path": "/internal/operations/recipient", "tier": "internal", "method": "POST"},
            # The read that makes the visit event self-healing. The bus is at-most-once, so a
            # consumer that misses an event must be able to catch up by reading — see the route.
            # The template library and the customer list, for campaigns. Customers are
            # PSEUDONYMS with a visit count — never a phone, never a name.
            {"path": "/internal/operations/templates", "tier": "internal", "method": "GET"},
            # Registers every connected shop's library and keeps it moving through Meta's queue —
            # the safety net behind the publish that runs at the moment of connection.
            {"path": "/internal/operations/templates/publish", "tier": "internal",
             "method": "POST"},
            # Service names and cycles, for insights. Includes retired services on purpose.
            {"path": "/internal/operations/catalogue", "tier": "internal", "method": "POST"},
            {"path": "/internal/operations/catalogue-with-prices", "tier": "internal", "method": "POST"},
            # The photo itself, for a peer with no owner bearer token (whatsapp-assistant's
            # catalog provider) — same bytes GET /api/v1/staff/{services,packages}/{id}/image
            # streams to an owner, under the internal token instead.
            {"path": "/internal/operations/catalogue/{}/{}/image", "tier": "internal", "method": "GET"},
            # THE EVIDENCE FILE (task 283). Assembled from ledgers written at the moment each
            # thing happened, never reconstructed — and the extraction is itself audited.
            {"path": "/internal/operations/evidence", "tier": "internal", "method": "POST"},
            {"path": "/internal/operations/branches", "tier": "internal", "method": "POST"},
            {"path": "/internal/operations/operators", "tier": "internal", "method": "POST"},
            # Who may see which branch — the staffing join no other service can make.
            {"path": "/internal/operations/branch-scope", "tier": "internal", "method": "POST"},
            {"path": "/internal/operations/customers", "tier": "internal", "method": "POST"},
            # bookings' one question of this service (docs/خطة-تنفيذ-الحجوزات.md §3):
            # what does a set of service_ids cost in minutes, right now.
            {"path": "/internal/operations/service-durations", "tier": "internal", "method": "POST"},
            # notification-service's subscription-renewal WhatsApp Flow (platform v0.19.12's
            # LoyaltyEngine(name="subscription_renewal")): balance/rewards/redeem over one due invoice.
            {"path": "/internal/whatsapp/renewal-provider", "tier": "internal", "method": "POST"},
            # the owner's own early "جدد الآن" tap on the 2-day-ahead WhatsApp heads-up — forces
            # this ONE subscription's cycle now; the automatic sweep itself is untouched.
            {"path": "/internal/operations/subscriptions/renew-now", "tier": "internal", "method": "POST"},
            # the daily read-only scan (billing v0.24.1) + the durable claim loop that turns each
            # renewing-soon row into a real WhatsApp heads-up — see core/renewal_heads_up.py.
            {"path": "/internal/operations/subscriptions/renewal-heads-up/scan", "tier": "internal", "method": "POST"},
            {"path": "/internal/operations/subscriptions/renewal-heads-up/jobs/run", "tier": "internal", "method": "POST"},
            # bookings' booking->visit gateway (§4): the ONE way an attended booking becomes a
            # real Visit — record_visit() itself, resolved by customer_id instead of phone.
            {"path": "/internal/operations/visits/from-customer", "tier": "internal", "method": "POST"},
            # whatsapp-assistant's own creation door for a mobile/on-the-go service request —
            # starts PENDING, never a Visit by itself (core/mobile_requests.py's own docstring).
            {"path": "/internal/operations/mobile-requests", "tier": "internal", "method": "POST"},
            # Read by whatsapp-assistant before it ever proposes request_mobile_visit — the shop's
            # own real working hours, so the customer is asked for a time that will be accepted.
            {"path": "/internal/operations/mobile-visit-hours", "tier": "internal", "method": "GET"},
            # WhatsApp Direct Ordering's own order-creation door (Step 4) — resolves the nearest
            # branch from the customer's real coordinates and creates the real orders.py Order.
            {"path": "/internal/operations/whatsapp-orders", "tier": "internal", "method": "POST"},
            {"path": "/internal/operations/whatsapp-orders/{}/points", "tier": "internal",
             "method": "POST"},
            # Read by whatsapp-assistant before every auto-registration attempt — see
            # core/whatsapp_auto_register.py's own docstring.
            {"path": "/internal/operations/whatsapp-auto-register", "tier": "internal",
             "method": "GET"},
            # `/internal/operations/customer-id-by-phone` already covers the actual write this flag
            # gates — see that route's own docstring; nothing new to declare here for the create.
            # insights' own lead-conversion indicator — see internal_customer_conversion's own
            # docstring and CustomerStore.conversion_by_source's.
            {"path": "/internal/operations/customer-conversion", "tier": "internal",
             "method": "GET"},
            # bookings' one way to carry the pseudonym every peer already needs (§5, §6.5): the
            # DSAR fan-out target and the event this service's own reminders/campaigns key on.
            {"path": "/internal/operations/customers/subject-ref", "tier": "internal", "method": "POST"},
            {"path": "/internal/operations/visits/since", "tier": "internal", "method": "POST"},
            # Attribution: who brought this establishment. First key wins, permanently — the rule
            # that decides where commission goes (spec 16.6.3).
            # One customer's own history, shaped for their page: service names and a date, and
            # nothing else. Everything omitted is something a forwarded link could otherwise show.
            {"path": "/internal/operations/customer-visits", "tier": "internal", "method": "POST"},
            # ADDED for services/whatsapp-assistant — resolve an inbound WhatsApp number to a
            # pseudonym and a visit-count pattern, never a name or the number back. See the
            # route's own docstring in api/internal.py for why nothing like this existed before.
            {"path": "/internal/operations/customer-by-phone", "tier": "internal", "method": "POST"},
            {"path": "/internal/operations/partner-stamp", "tier": "internal", "method": "POST"},
            {"path": "/internal/operations/partner-stamp/{}", "tier": "internal", "method": "GET"},
            {"path": "/internal/privacy/erase", "tier": "internal", "method": "POST",
             # DECLARED, because a data map built from manifests is how a DSAR fan-out
             # finds who holds a person. An undeclared holder is never asked, never acks,
             # and is therefore never MISSED — the request closes green on an erasure
             # that did not happen.
             "erasure_category": "subject"},
            {"path": "/api/v1/operations/whoami", "tier": "user", "method": "GET"},
            # PLATFORM-WIDE LANGUAGE PREFERENCE — any logged-in account, owner included (see
            # api/v1/__init__.py's own note; supersedes /staff/operators/me/locale below, which an
            # owner could never reach).
            {"path": "/api/v1/account/me/locale", "tier": "user", "method": "GET"},
            {"path": "/api/v1/account/me/locale", "tier": "user", "method": "PATCH"},
            {"path": "/api/v1/account/me/name", "tier": "user", "method": "GET"},
            {"path": "/api/v1/account/me/name", "tier": "user", "method": "PATCH"},
            {"path": "/api/v1/account/me/mobile-ai-assistant", "tier": "user", "method": "GET"},
            # ── the field screen — the product, as far as the shop floor is concerned ──────
            {"path": "/api/v1/field/visits", "tier": "user", "method": "POST"},
            {"path": "/api/v1/field/visits/offer/preview", "tier": "user", "method": "GET"},
            {"path": "/api/v1/field/visits/{}/offer", "tier": "user", "method": "POST"},
            {"path": "/api/v1/field/visits/{}/points", "tier": "user", "method": "GET"},
            {"path": "/api/v1/field/visits/{}/points", "tier": "user", "method": "POST"},
            {"path": "/api/v1/field/customers/{}", "tier": "user", "method": "PATCH"},
            {"path": "/api/v1/field/customers/{}/erase", "tier": "user", "method": "POST"},
            {"path": "/api/v1/field/customers/recent", "tier": "user", "method": "GET"},
            {"path": "/api/v1/field/customers/by-phone", "tier": "user", "method": "GET"},
            {"path": "/api/v1/field/customers/by-plate", "tier": "user", "method": "GET"},
            # The keypad's suggestion list. It reaches search-service through us so the reader's
            # branch can be resolved from his token — the browser used to call that service itself,
            # and no route over there has ever known what a branch is (ط-3).
            {"path": "/api/v1/field/customers/suggest", "tier": "user", "method": "GET"},
            # Resolve-or-create by phone, WITH NO VISIT (docs/خطة-تنفيذ-الحجوزات.md §6.2) —
            # bookings' console dialog needs a customer_id before it can create a booking; this is
            # the SAME act record_visit already makes, exposed on its own.
            {"path": "/api/v1/field/customers/ensure", "tier": "user", "method": "POST"},
            {"path": "/api/v1/field/privacy-requests", "tier": "user", "method": "GET"},
            {"path": "/api/v1/field/privacy-requests/{}/close", "tier": "user", "method": "POST"},
            {"path": "/internal/operations/privacy-request", "tier": "internal", "method": "POST"},
            # Pseudonyms to customers — the join «عملائي» needs for its overdue tab, since the
            # schedule comes from reminders and reminders holds no names.
            {"path": "/api/v1/field/customers/resolve", "tier": "user", "method": "POST"},
            {"path": "/api/v1/field/customers/{}", "tier": "user", "method": "GET"},
            {"path": "/api/v1/field/catalogue", "tier": "user", "method": "GET"},
            # Read-only mirrors of the manage-only image routes below (§9.4) — an operator
            # recording a visit sees the same photos without carrying manage_services.
            {"path": "/api/v1/field/catalogue/services/{}/image", "tier": "user", "method": "GET"},
            {"path": "/api/v1/field/catalogue/packages/{}/image", "tier": "user", "method": "GET"},
            # The console's «التقييمات» tab (rating-app-feature.md phase 5) — every rated visit,
            # and marking one handled.
            {"path": "/api/v1/field/ratings", "tier": "user", "method": "GET"},
            {"path": "/api/v1/field/ratings/{}/handled", "tier": "user", "method": "PATCH"},
            # The rating app's own staff-comparison report (rating-app-feature.md phase 7).
            {"path": "/api/v1/field/staff/performance", "tier": "user", "method": "GET"},
            # Same report, as a branded document (docx/pdf) instead of JSON (phase 8).
            {"path": "/api/v1/field/staff/performance/export", "tier": "user", "method": "POST"},
            # ── the back office ───────────────────────────────────────────────────────────
            {"path": "/api/v1/staff/members", "tier": "user", "method": "POST"},
            {"path": "/api/v1/staff/operators", "tier": "user", "method": "GET"},
            {"path": "/api/v1/staff/operators/{}", "tier": "user", "method": "PATCH"},
            {"path": "/api/v1/staff/operators/{}/working-hours", "tier": "user", "method": "PUT"},
            {"path": "/api/v1/staff/operators/{}/working-hours", "tier": "user", "method": "DELETE"},
            {"path": "/api/v1/staff/operators/me", "tier": "user", "method": "GET"},
            {"path": "/api/v1/staff/operators/me/locale", "tier": "user", "method": "PATCH"},
            # The mobile app's own bottom-bar personalisation — see staff.py's own docstring.
            {"path": "/api/v1/staff/operators/me/pinned-nav", "tier": "user", "method": "PATCH"},
            # How this shop runs its branches — one number for the brand, or one per branch.
            {"path": "/api/v1/staff/shop-name", "tier": "user", "method": "PUT"},
            {"path": "/api/v1/staff/mode", "tier": "user", "method": "GET"},
            {"path": "/api/v1/staff/mode", "tier": "user", "method": "PUT"},
            {"path": "/api/v1/staff/vehicles", "tier": "user", "method": "GET"},
            {"path": "/api/v1/staff/vehicles", "tier": "user", "method": "PUT"},
            {"path": "/api/v1/staff/whatsapp-auto-register", "tier": "user", "method": "GET"},
            {"path": "/api/v1/staff/whatsapp-auto-register", "tier": "user", "method": "PUT"},
            # What the owner told the WhatsApp AI assistant about his own shop — see ai_notes.py.
            {"path": "/api/v1/staff/ai-notes", "tier": "user", "method": "GET"},
            {"path": "/api/v1/staff/ai-notes", "tier": "user", "method": "PUT"},
            # The owner's own kill switch for the WhatsApp AI assistant — see ai_toggle.py.
            {"path": "/api/v1/staff/ai-toggle", "tier": "user", "method": "GET"},
            {"path": "/api/v1/staff/ai-toggle", "tier": "user", "method": "PUT"},
            # The customer-message word limit — see msg_limits.py.
            {"path": "/api/v1/staff/msg-word-limit", "tier": "user", "method": "GET"},
            {"path": "/api/v1/staff/msg-word-limit", "tier": "user", "method": "PUT"},
            {"path": "/api/v1/staff/branches", "tier": "user", "method": "POST"},
            {"path": "/api/v1/staff/branches", "tier": "user", "method": "GET"},
            {"path": "/api/v1/staff/branches/{}", "tier": "user", "method": "PATCH"},
            {"path": "/api/v1/staff/resolve-maps-link", "tier": "user", "method": "GET"},
            {"path": "/api/v1/staff/services", "tier": "user", "method": "GET"},
            {"path": "/api/v1/staff/services", "tier": "user", "method": "POST"},
            {"path": "/api/v1/staff/services/{}", "tier": "user", "method": "PATCH"},
            {"path": "/api/v1/staff/services/bulk_import", "tier": "user", "method": "POST"},
            {"path": "/api/v1/staff/services/{}/image", "tier": "user", "method": "POST"},
            {"path": "/api/v1/staff/services/{}/image", "tier": "user", "method": "GET"},
            {"path": "/api/v1/staff/packages", "tier": "user", "method": "GET"},
            {"path": "/api/v1/staff/packages", "tier": "user", "method": "POST"},
            {"path": "/api/v1/staff/packages/{}", "tier": "user", "method": "PATCH"},
            {"path": "/api/v1/staff/packages/{}/image", "tier": "user", "method": "POST"},
            {"path": "/api/v1/staff/packages/{}/image", "tier": "user", "method": "GET"},
            {"path": "/api/v1/staff/procedure-steps", "tier": "user", "method": "GET"},
            {"path": "/api/v1/staff/procedure-steps", "tier": "user", "method": "POST"},
            {"path": "/api/v1/staff/procedure-steps/{}", "tier": "user", "method": "PATCH"},
            {"path": "/api/v1/staff/operators/{}/step-stats", "tier": "user", "method": "GET"},
            {"path": "/api/v1/staff/procedure-checklist/export", "tier": "user", "method": "POST"},
            {"path": "/api/v1/staff/coupons/grant", "tier": "user", "method": "POST"},
            {"path": "/api/v1/staff/coupons/history", "tier": "user", "method": "GET"},
            {"path": "/api/v1/staff/coupons/stats", "tier": "user", "method": "GET"},
            {"path": "/api/v1/staff/coupons/check", "tier": "user", "method": "GET"},
            {"path": "/api/v1/staff/coupons/preferences", "tier": "user", "method": "GET"},
            {"path": "/api/v1/staff/coupons/preferences", "tier": "user", "method": "PATCH"},
            # REFERRAL PARTNERSHIP — NOT coupons above, see core/mutual_benefit.py's own
            # module docstring. Every route owner/manager-only (`operations.manage`, already
            # declared above), never a plain operator capability — a commitment against another
            # shop entirely, same posture the design doc requires explicitly.
            {"path": "/api/v1/staff/mutual-benefit/agreements", "tier": "user",
             "method": "POST"},
            {"path": "/api/v1/staff/mutual-benefit/agreements", "tier": "user",
             "method": "GET"},
            {"path": "/api/v1/staff/mutual-benefit/agreements/{}", "tier": "user",
             "method": "GET"},
            {"path": "/api/v1/staff/mutual-benefit/agreements/{}/accept", "tier": "user",
             "method": "POST"},
            {"path": "/api/v1/staff/mutual-benefit/agreements/{}/reject", "tier": "user",
             "method": "POST"},
            {"path": "/api/v1/staff/mutual-benefit/agreements/{}/cancel-request",
             "tier": "user", "method": "POST"},
            {"path": "/api/v1/staff/mutual-benefit/agreements/{}/cancel-confirm",
             "tier": "user", "method": "POST"},
            {"path": "/api/v1/staff/mutual-benefit/agreements/{}/audit-log", "tier": "user",
             "method": "GET"},
            {"path": "/api/v1/staff/mutual-benefit/kpis", "tier": "user", "method": "GET"},
            {"path": "/api/v1/platform/coupons/settings", "tier": "user", "method": "GET"},
            {"path": "/api/v1/platform/coupons/settings", "tier": "user", "method": "PATCH"},
            {"path": "/api/v1/platform/coupons/tenant-lookup", "tier": "user", "method": "GET"},
            {"path": "/api/v1/platform/coupons/tenants/{}", "tier": "user", "method": "GET"},
            {"path": "/api/v1/platform/coupons/tenants/{}", "tier": "user", "method": "PATCH"},
            {"path": "/api/v1/platform/app-visibility", "tier": "user", "method": "GET"},
            {"path": "/api/v1/platform/app-visibility", "tier": "user", "method": "PUT"},
            # ── the platform console: OURS, not an establishment's ────────────────────────
            # THE EVIDENCE FILE, for whoever is handling a complaint (task 283). Operator
            # surface: a capability a person holds, and an audit row that names them.
            {"path": "/api/v1/platform/evidence", "tier": "user", "method": "POST"},
            # THE WALLET TOP-UP RECONCILE POLL, on demand — the same sweep the CronJob runs every
            # 5 minutes (see app/core/wallet_topup_reconcile.py's own header).
            {"path": "/api/v1/platform/wallet-topups/reconcile-now", "tier": "user", "method": "POST"},
            {"path": "/api/v1/platform/branches/locations", "tier": "user", "method": "GET"},
            {"path": "/api/v1/platform/tenants/{}/capacity", "tier": "user", "method": "GET"},
            {"path": "/api/v1/platform/whatsapp/diagnostics", "tier": "user", "method": "GET"},
            # THE META CATEGORY'S "STATUS" TAB (Raje3 Meta-panel Phase 1) — platform-wide delivery,
            # bound-numbers and connection-state figures, never one shop's.
            {"path": "/api/v1/platform/whatsapp/platform-status", "tier": "user", "method": "GET"},
            # ONE SHOP'S OWN CONNECTED NUMBER (platform v0.19.9) — messaging-limit tier, subscribed
            # webhook fields, business verification, and the two-step PIN set/rotate write.
            {"path": "/api/v1/platform/whatsapp/messaging-limit", "tier": "user", "method": "GET"},
            {"path": "/api/v1/platform/whatsapp/subscribed-fields", "tier": "user", "method": "GET"},
            {"path": "/api/v1/platform/whatsapp/business-verification", "tier": "user", "method": "GET"},
            {"path": "/api/v1/platform/whatsapp/two-step-pin", "tier": "user", "method": "POST"},
            # ONE FLOW'S REAL GENERATED SCREENS, for the admin panel's own interactive preview
            # (`WhatsAppTemplatePreview`, rj-ui) — see `platform.py::whatsapp_flow_json`.
            {"path": "/api/v1/platform/whatsapp/flow-json", "tier": "user", "method": "GET"},
            # The «الامتثال» support screen's own customer lookup, cross-shop: same exact-match
            # weak-role search as the shop's own /api/v1/field/customers/by-phone, gated by
            # platform.operations with an explicit tenant instead of the caller's own claim.
            {"path": "/api/v1/platform/customers/by-phone", "tier": "user", "method": "GET"},
            # «نجاح العملاء» — the caller supplies the tenant list it already holds (tenant.list is
            # tenant-service's own route, not this service's); this only checks OUR OWN visit/service
            # records, two bounded existence reads per tenant.
            {"path": "/api/v1/platform/customers/success-scan", "tier": "user", "method": "POST"},
            {"path": "/api/v1/platform/flows/subscription-renewal/seed", "tier": "user",
             "method": "POST"},
            {"path": "/api/v1/platform/templates", "tier": "user", "method": "GET"},
            {"path": "/api/v1/platform/templates/{}", "tier": "user", "method": "PUT"},
            {"path": "/api/v1/platform/templates/{}", "tier": "user", "method": "DELETE"},
            # ── the partner console: their shops and their money, never a shop's customers ──
            {"path": "/api/v1/platform/partners", "tier": "user", "method": "GET"},
            {"path": "/api/v1/platform/partners", "tier": "user", "method": "POST"},
            {"path": "/api/v1/platform/partners/{}/rotate", "tier": "user", "method": "POST"},
            {"path": "/api/v1/platform/partners/{}", "tier": "user", "method": "DELETE"},
            # The statements, from our side. The partner could always read his own; we could read
            # nobody's — see the routes for what that cost.
            {"path": "/api/v1/platform/partners/{}/health", "tier": "user", "method": "GET"},
            {"path": "/api/v1/platform/sandbox", "tier": "user", "method": "POST"},
            {"path": "/api/v1/platform/statements", "tier": "user", "method": "GET"},
            {"path": "/api/v1/platform/statements/{}/{}/paid", "tier": "user", "method": "POST"},
            {"path": "/api/v1/platform/statements/{}/{}/dispute", "tier": "user",
             "method": "POST"},
            {"path": "/api/v1/partner/shops", "tier": "user", "method": "GET"},
            {"path": "/api/v1/partner/statements", "tier": "user", "method": "GET"},
            {"path": "/api/v1/partner/statements/{}", "tier": "user", "method": "GET"},
            # ── the owner's own account: buying, and connecting the channel he sends on ──
            # Undeclared until now, and the gap was invisible because the completeness gate reads
            # DECLARED ACTIONS: a route with no action behind it is a route nothing checks. The
            # subscribe path had been live and unlisted since it was written.
            {"path": "/api/v1/subscription", "tier": "user", "method": "POST"},
            {"path": "/api/v1/subscription/checkout-link", "tier": "user", "method": "POST"},
            {"path": "/api/v1/subscription/checkout", "tier": "user", "method": "POST"},
            {"path": "/api/v1/subscription/checkout/link", "tier": "user", "method": "POST"},
            {"path": "/api/v1/subscription/checkout/preview", "tier": "user", "method": "POST"},
            {"path": "/api/v1/subscription/renew-now", "tier": "user", "method": "POST"},
            {"path": "/api/v1/subscription/payment", "tier": "user", "method": "GET"},
            {"path": "/api/v1/subscription/apps", "tier": "user", "method": "GET"},
            {"path": "/api/v1/subscription/apps/static-features", "tier": "user", "method": "GET"},
            {"path": "/api/v1/subscription/apps/visibility-overrides", "tier": "user", "method": "GET"},
            {"path": "/api/v1/whatsapp/connect", "tier": "user", "method": "POST"},
            {"path": "/api/v1/whatsapp/connect", "tier": "user", "method": "GET"},
            # WHAT THE CONSOLE NEEDS TO EVEN OPEN THE POPUP — App ID/Config ID, read live from
            # notification-service's own sealed values. Not secret; see connect.py's own note.
            {"path": "/api/v1/whatsapp/config", "tier": "user", "method": "GET"},
            # FINISHING THE CONNECTION (base-services v0.16.10). The exchange stores a token; Meta
            # refuses to send until the number is REGISTERED with the business's own 6-digit PIN —
            # which we do not have and must never invent, so it is his act and separate.
            {"path": "/api/v1/whatsapp/connect/register", "tier": "user", "method": "POST"},
            # ONE FLOW'S REAL GENERATED SCREENS, for «رسائلي»'s own interactive preview — the
            # shop-facing twin of the admin route above; see `connect.py::shop_whatsapp_flow_json`.
            {"path": "/api/v1/whatsapp/flow-json", "tier": "user", "method": "GET"},
            # ── the door ──────────────────────────────────────────────────────────────────
            # PUBLIC, and it is the only user-facing surface here that is. One route creates the
            # account a token would come from and the other exchanges a phone and a password for
            # one; neither can require the thing it produces. Declared as `public` so a route
            # table built from manifests shows them for what they are rather than hiding two
            # unauthenticated paths inside a list of guarded ones.
            {"path": "/api/v1/signup", "tier": "public", "method": "POST"},
            {"path": "/api/v1/signup/signin", "tier": "public", "method": "POST"},
            # ── the shop's own till ───────────────────────────────────────────────────────
            # `user` tier, not `internal`: it carries an ordinary Bearer token — the one identity
            # mints for a service account — and it is capability-gated like every other user
            # route. It is here rather than on the internal tier precisely so an outside party
            # never needs the shared internal secret, which opens every internal door in the
            # product.
            {"path": "/api/v1/till/visits", "tier": "user", "method": "POST"},
            # AND THE ANSWER BACK. The till asked and we said nothing — see the routes for what
            # that cost at the counter. Same tier, same one capability.
            {"path": "/api/v1/till/customer", "tier": "user", "method": "GET"},
            {"path": "/api/v1/till/redeem", "tier": "user", "method": "POST"},
            {"path": "/api/v1/till/offer/apply", "tier": "user", "method": "POST"},
            {"path": "/api/v1/till/points/available", "tier": "user", "method": "GET"},
            {"path": "/api/v1/till/points/redeem", "tier": "user", "method": "POST"},
            # FOUND UNDECLARED BY test_manifest_covers_routes.py — six real, served till.py routes
            # with no manifest row at all, so no gate that reads this list (capability review,
            # action coverage, the route table) ever looked at them.
            {"path": "/api/v1/till/status", "tier": "user", "method": "GET"},
            {"path": "/api/v1/till/branches", "tier": "user", "method": "GET"},
            {"path": "/api/v1/till/bookings", "tier": "user", "method": "GET"},
            {"path": "/api/v1/till/bookings/{}/attend", "tier": "user", "method": "POST"},
            {"path": "/api/v1/till/rating-request", "tier": "user", "method": "POST"},
            {"path": "/api/v1/till/coupons/grant", "tier": "user", "method": "POST"},
            {"path": "/api/v1/till/referral/register", "tier": "user", "method": "POST"},
            # ── Phase 4 of the referral/affiliate app — see api/v1/affiliates.py's own docstring.
            {"path": "/api/v1/affiliates", "tier": "user", "method": "POST"},
            {"path": "/api/v1/affiliates", "tier": "user", "method": "GET"},
            {"path": "/api/v1/affiliates/{}", "tier": "user", "method": "GET"},
            {"path": "/api/v1/affiliates/{}/active", "tier": "user", "method": "PUT"},
            {"path": "/api/v1/affiliates/{}/settle", "tier": "user", "method": "POST"},
            {"path": "/api/v1/affiliates/{}/settlements", "tier": "user", "method": "GET"},
            # ── Phase 5a of the referral/affiliate app — read-only performance reporting.
            {"path": "/api/v1/referrals/reports/summary", "tier": "user", "method": "GET"},
            {"path": "/api/v1/referrals/reports/leaderboard", "tier": "user", "method": "GET"},
            {"path": "/api/v1/referrals/reports/campaigns", "tier": "user", "method": "GET"},
            {"path": "/api/v1/referrals/reports/affiliates", "tier": "user", "method": "GET"},
            # ── Salla — see api/v1/salla.py's own module docstring for the install/callback split.
            {"path": "/api/v1/staff/salla/install", "tier": "user", "method": "GET"},
            {"path": "/api/v1/staff/salla/status", "tier": "user", "method": "GET"},
            {"path": "/api/v1/staff/salla/disconnect", "tier": "user", "method": "POST"},
            # ── mobile/on-the-go service requests — see api/v1/mobile_requests.py's own note.
            {"path": "/api/v1/staff/mobile-requests", "tier": "user", "method": "GET"},
            {"path": "/api/v1/staff/mobile-requests", "tier": "user", "method": "POST"},
            {"path": "/api/v1/staff/mobile-requests/{}/risk", "tier": "user", "method": "GET"},
            {"path": "/api/v1/staff/mobile-requests/{}/assign", "tier": "user", "method": "POST"},
            {"path": "/api/v1/staff/mobile-requests/{}/accept", "tier": "user", "method": "POST"},
            {"path": "/api/v1/staff/mobile-requests/{}/reject", "tier": "user", "method": "POST"},
            {"path": "/api/v1/staff/mobile-requests/{}/complete", "tier": "user", "method": "POST"},
            {"path": "/api/v1/staff/mobile-requests/{}/no-show", "tier": "user", "method": "POST"},
            {"path": "/api/v1/staff/freelancers", "tier": "user", "method": "GET"},
            {"path": "/api/v1/staff/freelancers", "tier": "user", "method": "POST"},
            {"path": "/api/v1/staff/freelancers/{}/deactivate", "tier": "user", "method": "POST"},
            {"path": "/api/v1/staff/freelancers/rules", "tier": "user", "method": "GET"},
            {"path": "/api/v1/staff/freelancers/rules", "tier": "user", "method": "POST"},
            {"path": "/api/v1/staff/freelancers/reward-options", "tier": "user", "method": "GET"},
            {"path": "/api/v1/staff/freelancers/reward-options", "tier": "user", "method": "POST"},
            {"path": "/api/v1/staff/freelancers/escalations", "tier": "user", "method": "GET"},
            {"path": "/api/v1/staff/freelancers/escalations/{}/resolve", "tier": "user", "method": "POST"},
            {"path": "/api/v1/staff/freelancers/notes/export", "tier": "user", "method": "GET"},
            {"path": "/api/v1/staff/freelancer-portal/customers", "tier": "user", "method": "GET"},
            {"path": "/api/v1/staff/freelancer-portal/customers/{}/rate", "tier": "user", "method": "POST"},
            {"path": "/api/v1/staff/freelancer-portal/customers/{}/do-not-disturb", "tier": "user", "method": "POST"},
            {"path": "/api/v1/staff/freelancer-portal/customers/{}/reward", "tier": "user", "method": "POST"},
            {"path": "/api/v1/staff/freelancer-portal/customers/{}/escalate", "tier": "user", "method": "POST"},
            {"path": "/api/v1/staff/freelancer-portal/customers/{}/notes", "tier": "user", "method": "POST"},
            # ── WhatsApp Direct Ordering, Step 7 -- see api/v1/whatsapp_orders.py's own note.
            {"path": "/api/v1/staff/whatsapp-orders", "tier": "user", "method": "GET"},
            {"path": "/api/v1/staff/whatsapp-orders/pause", "tier": "user", "method": "GET"},
            {"path": "/api/v1/staff/whatsapp-orders/pause", "tier": "user", "method": "POST"},
            {"path": "/api/v1/staff/whatsapp-orders/share-toggle", "tier": "user", "method": "GET"},
            {"path": "/api/v1/staff/whatsapp-orders/share-toggle", "tier": "user", "method": "POST"},
            {"path": "/api/v1/staff/whatsapp-orders/{}", "tier": "user", "method": "GET"},
            {"path": "/api/v1/staff/whatsapp-orders/{}/preparing", "tier": "user", "method": "POST"},
            {"path": "/api/v1/staff/whatsapp-orders/{}/ready", "tier": "user", "method": "POST"},
            {"path": "/api/v1/staff/whatsapp-orders/{}/out-for-delivery", "tier": "user",
             "method": "POST"},
            {"path": "/api/v1/staff/whatsapp-orders/{}/delivered", "tier": "user", "method": "POST"},
            {"path": "/api/v1/staff/whatsapp-orders/{}/cancel", "tier": "user", "method": "POST"},
            {"path": "/api/v1/staff/whatsapp-orders/{}/resolve-mismatch", "tier": "user",
             "method": "POST"},
            # PUBLIC, deliberately, same posture as signup's own pair right below: Salla's browser
            # redirect and Salla's own server call carry no Bearer token to check.
            {"path": "/api/v1/salla/callback", "tier": "public", "method": "GET"},
            {"path": "/api/v1/salla/webhook", "tier": "public", "method": "POST"},
            # PUBLIC, deliberately — see api/v1/public_catalog.py's own module docstring: Meta's
            # WhatsApp Catalog crawler has no bearer token to give, and the capability TOKEN in the
            # path is the real gate (core/public_catalog_image.py), not a missing auth check.
            {"path": "/api/v1/public_catalog/{}", "tier": "public", "method": "GET"},
            {"path": "/api/v1/signup/code", "tier": "public", "method": "POST"},
            {"path": "/api/v1/signup/verify", "tier": "public", "method": "POST"},
            {"path": "/api/v1/signup/claim", "tier": "public", "method": "POST"},
            # The operator surface: policy an operator changes after launch. The credential-
            # management routes that used to sit here (a dead SecretStore nothing ever consumed)
            # were removed — see git history for the incident.
            {"path": "/api/v1/operations/operator/config", "tier": "user", "method": "GET"},
            {"path": "/api/v1/operations/operator/config", "tier": "user", "method": "PUT"},
            {"path": "/api/v1/operations/operator/config/{}", "tier": "user", "method": "DELETE"},
        ],
        "ports": ports or [],  # port -> driver, from the composition root
        # FILL THIS too, or leave it empty deliberately. Same trap as capabilities: an empty
        # `emitted` reads as "this service publishes nothing", so a consumer wiring against it
        # subscribes to nothing and fails silently rather than at boot.
        # ONE event, and it is the spine of the product: reminders schedules from it, insights
        # counts it, loyalty will award from it. Published rather than called, so this service
        # stays ignorant of who consumes a visit — a service that knows its consumers has to be
        # changed every time one is added. The payload carries subject_ref, never the phone.
        "events": {"emitted": ["operations.visit.recorded"], "consumed": []},
        "admin_actions": _admin_actions(),
        "backup": _backup(),
        "user_actions": _user_actions(),
    }
