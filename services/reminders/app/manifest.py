# =============================================================================
# reminders — Self-describing service manifest
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
        # Three, and the split follows who is harmed by a mistake. Reading the schedule is what
        # an owner does to answer "why did my customer get this?". Tuning the rules changes what
        # every future customer receives, so it is the owner's alone. And `platform.reminders` is
        # OURS: the sending caps in spec 8.4.2 are not an establishment's to raise, because a
        # blocked number lowers the quality rating of every number on the product.
        "capabilities": ["reminders.read", "reminders.manage", "platform.reminders",
                         # WHAT api/v1/operator.py ACTUALLY ENFORCES. Advertised because they are
                         # enforced here — not because we grant them to a tenant: platform.* is
                         # ours, and authz denies the whole prefix to every establishment. The
                         # actions used to name platform.<service> instead, so the console rendered
                         # the credentials buttons for whoever held that and the service answered
                         # 403 to every one of them.
                         "platform.secrets", "platform.config"],  # e.g. ["files.upload", "files.read"] — atomic capability keys
        "endpoints": [
            # «اليوم» reads this once and gets the whole status: what went out, what waits, and
            # how much of Meta's ceiling is left. One call because a status screen that loads in
            # pieces is briefly wrong, and briefly wrong is worse than briefly blank.
            {"path": "/api/v1/reminders/today", "tier": "user", "method": "GET"},
            # From the generated scaffold, and kept: what a client calls to confirm its token is
            # accepted at all, which is the first question asked when something else is failing.
            # Undeclared in every service until a guard compared the manifest with the app itself.
            {"path": "/api/v1/admin/ping", "tier": "user", "method": "GET"},
            {"path": "/healthz", "tier": "public", "method": "GET"},
            {"path": "/readyz", "tier": "public", "method": "GET"},
            {"path": "/metrics", "tier": "public", "method": "GET"},
            {"path": "/internal/health", "tier": "internal", "method": "GET"},
            {"path": "/internal/manifest", "tier": "internal", "method": "GET"},
            {"path": "/internal/backup/export", "tier": "internal", "method": "POST"},
            {"path": "/internal/backup/import", "tier": "internal", "method": "POST"},
            {"path": "/internal/backup/verify", "tier": "internal", "method": "POST"},
            # THE HEARTBEAT. A cron in the values file drives this; without it the service holds
            # a perfect schedule and sends nothing, which is the quietest possible outage.
            {"path": "/internal/reminders/tick", "tier": "internal", "method": "POST"},
            # For campaigns: would the gate allow this, and send this. The second is the ONLY
            # way that service sends anything — there is no campaign-shaped shortcut.
            {"path": "/internal/reminders/eligibility", "tier": "internal", "method": "POST"},
            {"path": "/internal/reminders/send", "tier": "internal", "method": "POST"},
            {"path": "/internal/reminders/receipt", "tier": "internal", "method": "POST"},
            {"path": "/internal/reminders/dsar-code", "tier": "internal", "method": "POST"},
            # A COUNT of who consents, never who. The owner sees a number (§8.5).
            {"path": "/internal/reminders/consent/count", "tier": "internal", "method": "POST"},
            # For portal: the offers a customer is holding, read on his behalf. His page carries no
            # token — a public route here would be a way to ask "does this shop hold an offer for
            # this pseudonym", one guess at a time.
            {"path": "/internal/portal/offers", "tier": "internal", "method": "GET"},
            {"path": "/internal/privacy/erase", "tier": "internal", "method": "POST",
             # Declared, because a data map built from manifests is how a DSAR fan-out finds who
             # holds a person. An undeclared holder is never asked and therefore never missed.
             "erasure_category": "subject"},
            {"path": "/api/v1/whoami", "tier": "user", "method": "GET"},
            # ── the owner's surface ───────────────────────────────────────────────────────
            {"path": "/api/v1/reminders/schedule", "tier": "user", "method": "GET"},
            # The offer line above the field screen's service grid (§5.6.2).
            {"path": "/api/v1/reminders/offer", "tier": "user", "method": "GET"},
            # The owner's view of one customer's offers — including the expired ones, which the
            # customer's own page and the field screen must never show.
            {"path": "/api/v1/reminders/offers", "tier": "user", "method": "GET"},
            {"path": "/api/v1/reminders/dsar-code", "tier": "user", "method": "POST"},
            {"path": "/api/v1/reminders/schedule/{}", "tier": "user", "method": "DELETE"},
            {"path": "/api/v1/reminders/rules", "tier": "user", "method": "GET"},
            {"path": "/api/v1/reminders/rules/{}", "tier": "user", "method": "PUT"},
            {"path": "/api/v1/reminders/log", "tier": "user", "method": "GET"},
            # His own texts: written here, submitted from here, never edited by us.
            {"path": "/api/v1/reminders/templates", "tier": "user", "method": "GET"},
            {"path": "/api/v1/reminders/templates", "tier": "user", "method": "POST"},
            # What sends in the shop's name, and whether it sends at all (core/triggers.py).
            {"path": "/api/v1/reminders/triggers", "tier": "user", "method": "GET"},
            {"path": "/api/v1/reminders/triggers/{}", "tier": "user", "method": "PUT"},
            {"path": "/api/v1/reminders/triggers/{}/preview", "tier": "user", "method": "GET"},
            # Settings, three levels deep (spec 10.8.1). The owner never picks a level — they edit
            # a service and it becomes an override, with the way back offered where it happened.
            {"path": "/api/v1/reminders/settings", "tier": "user", "method": "GET"},
            {"path": "/api/v1/reminders/settings", "tier": "user", "method": "PUT"},
            {"path": "/api/v1/reminders/settings/service/{}", "tier": "user", "method": "PUT"},
            {"path": "/api/v1/reminders/settings/service/{}", "tier": "user", "method": "DELETE"},
            {"path": "/api/v1/reminders/settings/group/{}", "tier": "user", "method": "PUT"},
            {"path": "/api/v1/reminders/settings/group/{}", "tier": "user", "method": "DELETE"},
            {"path": "/api/v1/reminders/settings/group/{}/service/{}", "tier": "user",
             "method": "DELETE"},
            {"path": "/api/v1/reminders/settings/suggest-group", "tier": "user", "method": "GET"},
            # ── the customer's own switches — no token in the URL (spec 8.6.1) ────────────
            {"path": "/api/v1/prefs/{}", "tier": "user", "method": "GET"},
            {"path": "/api/v1/prefs/{}", "tier": "user", "method": "PUT"},
            # ── the platform console: the caps themselves ─────────────────────────────────
            {"path": "/api/v1/platform/limits", "tier": "user", "method": "GET"},
            # THE ALARM THAT DID NOT EXIST: shops with work queued and no way to send it.
            {"path": "/api/v1/platform/silent", "tier": "user", "method": "GET"},
            {"path": "/api/v1/platform/limits", "tier": "user", "method": "PUT"},
            {"path": "/api/v1/platform/limits", "tier": "user", "method": "DELETE"},
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
        # CONSUMED is the important half here. This service does nothing until a visit happens
        # somewhere else — it is the only one on the product whose entire input is another
        # service's event. An empty `consumed` would read as "wire nothing to me", which is
        # exactly the silent failure: a perfect scheduler with no schedules.
        "events": {"emitted": ["reminders.message.sent", "reminders.message.suppressed"],
                   "consumed": ["operations.visit.recorded"]},  # e.g. {"emitted": ["wallet.credited"], ...}
        "admin_actions": _admin_actions(),
        "backup": _backup(),
        "user_actions": _user_actions(),
    }
