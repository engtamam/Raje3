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
                         # WHAT THE OPERATOR ROUTES ACTUALLY ENFORCE. Advertised because they are
                         # enforced here, not because we grant them to anyone: platform.* is ours,
                         # and authz denies the whole prefix to every tenant.
                         "platform.secrets", "platform.config"],
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
            # bookings' booking->visit gateway (§4): the ONE way an attended booking becomes a
            # real Visit — record_visit() itself, resolved by customer_id instead of phone.
            {"path": "/internal/operations/visits/from-customer", "tier": "internal", "method": "POST"},
            # bookings' one way to carry the pseudonym every peer already needs (§5, §6.5): the
            # DSAR fan-out target and the event this service's own reminders/campaigns key on.
            {"path": "/internal/operations/customers/subject-ref", "tier": "internal", "method": "POST"},
            {"path": "/internal/operations/visits/since", "tier": "internal", "method": "POST"},
            # Attribution: who brought this establishment. First key wins, permanently — the rule
            # that decides where commission goes (spec 16.6.3).
            # One customer's own history, shaped for their page: service names and a date, and
            # nothing else. Everything omitted is something a forwarded link could otherwise show.
            {"path": "/internal/operations/customer-visits", "tier": "internal", "method": "POST"},
            {"path": "/internal/operations/partner-stamp", "tier": "internal", "method": "POST"},
            {"path": "/internal/operations/partner-stamp/{}", "tier": "internal", "method": "GET"},
            {"path": "/internal/privacy/erase", "tier": "internal", "method": "POST",
             # DECLARED, because a data map built from manifests is how a DSAR fan-out
             # finds who holds a person. An undeclared holder is never asked, never acks,
             # and is therefore never MISSED — the request closes green on an erasure
             # that did not happen.
             "erasure_category": "subject"},
            {"path": "/api/v1/whoami", "tier": "user", "method": "GET"},
            # ── the field screen — the product, as far as the shop floor is concerned ──────
            {"path": "/api/v1/field/visits", "tier": "user", "method": "POST"},
            {"path": "/api/v1/field/visits/{}/offer", "tier": "user", "method": "POST"},
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
            # ── the back office ───────────────────────────────────────────────────────────
            {"path": "/api/v1/staff/operators", "tier": "user", "method": "POST"},
            {"path": "/api/v1/staff/members", "tier": "user", "method": "POST"},
            {"path": "/api/v1/staff/operators", "tier": "user", "method": "GET"},
            {"path": "/api/v1/staff/operators/{}", "tier": "user", "method": "PATCH"},
            {"path": "/api/v1/staff/operators/{}/working-hours", "tier": "user", "method": "PUT"},
            {"path": "/api/v1/staff/operators/{}/working-hours", "tier": "user", "method": "DELETE"},
            {"path": "/api/v1/staff/operators/verify-pin", "tier": "user", "method": "POST"},
            # How this shop runs its branches — one number for the brand, or one per branch.
            {"path": "/api/v1/staff/shop-name", "tier": "user", "method": "PUT"},
            {"path": "/api/v1/staff/mode", "tier": "user", "method": "GET"},
            {"path": "/api/v1/staff/mode", "tier": "user", "method": "PUT"},
            {"path": "/api/v1/staff/vehicles", "tier": "user", "method": "GET"},
            {"path": "/api/v1/staff/vehicles", "tier": "user", "method": "PUT"},
            {"path": "/api/v1/staff/branches", "tier": "user", "method": "POST"},
            {"path": "/api/v1/staff/branches", "tier": "user", "method": "GET"},
            {"path": "/api/v1/staff/branches/{}", "tier": "user", "method": "PATCH"},
            {"path": "/api/v1/staff/services", "tier": "user", "method": "GET"},
            {"path": "/api/v1/staff/services", "tier": "user", "method": "POST"},
            {"path": "/api/v1/staff/services/{}", "tier": "user", "method": "PATCH"},
            # ── the platform console: OURS, not an establishment's ────────────────────────
            # THE EVIDENCE FILE, for whoever is handling a complaint (task 283). Operator
            # surface: a capability a person holds, and an audit row that names them.
            {"path": "/api/v1/platform/evidence", "tier": "user", "method": "POST"},
            {"path": "/api/v1/platform/branches/locations", "tier": "user", "method": "GET"},
            {"path": "/api/v1/platform/whatsapp/diagnostics", "tier": "user", "method": "GET"},
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
            {"path": "/api/v1/subscription/payment", "tier": "user", "method": "GET"},
            {"path": "/api/v1/subscription/apps", "tier": "user", "method": "GET"},
            {"path": "/api/v1/whatsapp/connect", "tier": "user", "method": "POST"},
            {"path": "/api/v1/whatsapp/connect", "tier": "user", "method": "GET"},
            # FINISHING THE CONNECTION (base-services v0.16.10). The exchange stores a token; Meta
            # refuses to send until the number is REGISTERED with the business's own 6-digit PIN —
            # which we do not have and must never invent, so it is his act and separate.
            {"path": "/api/v1/whatsapp/connect/register", "tier": "user", "method": "POST"},
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
            {"path": "/api/v1/signup/code", "tier": "public", "method": "POST"},
            {"path": "/api/v1/signup/verify", "tier": "public", "method": "POST"},
            {"path": "/api/v1/signup/claim", "tier": "public", "method": "POST"},
            # The operator surface: credentials and policy an operator changes after launch.
            # Declared like anything else — a route table built from manifests that omits the
            # place credentials are set is a route table that hides the highest-privilege
            # surface the service has.
            {"path": "/api/v1/operator/secrets", "tier": "user", "method": "GET"},
            {"path": "/api/v1/operator/secrets", "tier": "user", "method": "PUT"},
            {"path": "/api/v1/operator/secrets/{}", "tier": "user", "method": "DELETE"},
            {"path": "/api/v1/operator/config", "tier": "user", "method": "GET"},
            {"path": "/api/v1/operator/config", "tier": "user", "method": "PUT"},
            {"path": "/api/v1/operator/config/{}", "tier": "user", "method": "DELETE"},
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
