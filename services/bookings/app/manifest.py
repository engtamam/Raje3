# =============================================================================
# bookings — Self-describing service manifest
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
        # THE PLATFORM OPERATOR SURFACE, inherited from _template and kept: `platform.secrets` and
        # `platform.config` are what admin_actions.py's operator routes enforce (secrets/config
        # get/set/clear, the ping check). `bookings.read`/`bookings.write` (Stage 6,
        # docs/خطة-تنفيذ-الحجوزات.md) are the domain capabilities app/api/v1/bookings.py enforces —
        # matching app/core/licence.py's own read/write asymmetry: read opens the grid, write is
        # everything that grows or changes a commitment (create/edit/cancel), and licence itself
        # decides underneath which of those a lapsed subscription may still do (attend/no_show).
        # `bookings.manage` (Stage 8/9): the shop-wide policy underneath the grid — its own weekly
        # working hours and the "auto" tie-breaker among an "auto" service's eligible operators.
        # Was enforced by `api/v1/bookings.py`'s `_MANAGE` from day one but never advertised here —
        # an under-declaration, not a design choice: the two routes below existed, worked, and
        # refused correctly, but no console/mobile screen could ever ask the catalogue "may this
        # operator save these" — the button had to render unconditionally or not at all.
        "capabilities": ["platform.secrets", "platform.config", "bookings.read", "bookings.write",
                         "bookings.manage"],
        "endpoints": [
            {"path": "/healthz", "tier": "public", "method": "GET"},
            {"path": "/readyz", "tier": "public", "method": "GET"},
            {"path": "/metrics", "tier": "public", "method": "GET"},
            {"path": "/internal/health", "tier": "internal", "method": "GET"},
            {"path": "/internal/manifest", "tier": "internal", "method": "GET"},
            {"path": "/internal/backup/export", "tier": "internal", "method": "POST"},
            {"path": "/internal/backup/import", "tier": "internal", "method": "POST"},
            {"path": "/internal/backup/verify", "tier": "internal", "method": "POST"},
            # Stage 2's own first caller (docs/خطة-تنفيذ-الحجوزات.md §2/§7) — the availability
            # derivation exposed as the same clean interface a peer, the console and a future
            # portal client will all call, from day one, never a parallel path.
            {"path": "/internal/availability/check", "tier": "internal", "method": "POST"},
            {"path": "/internal/availability/nearest", "tier": "internal", "method": "POST"},
            {"path": "/internal/privacy/erase", "tier": "internal", "method": "POST",
             # DECLARED, because a data map built from manifests is how a DSAR fan-out
             # finds who holds a person. An undeclared holder is never asked, never acks,
             # and is therefore never MISSED — the request closes green on an erasure
             # that did not happen.
             "erasure_category": "subject"},
            {"path": "/api/v1/bookings/admin/ping", "tier": "user", "method": "GET"},
            {"path": "/api/v1/bookings/whoami", "tier": "user", "method": "GET"},
            # The operator surface: policy an operator changes after launch. The credential-
            # management routes that used to sit here (a dead SecretStore nothing ever consumed)
            # were removed — see git history for the incident.
            {"path": "/api/v1/bookings/operator/config", "tier": "user", "method": "GET"},
            {"path": "/api/v1/bookings/operator/config", "tier": "user", "method": "PUT"},
            {"path": "/api/v1/bookings/operator/config/{}", "tier": "user", "method": "DELETE"},
            # Stage 6 (docs/خطة-تنفيذ-الحجوزات.md §6): the grid's own read, and every write
            # app/core/operations.py::BookingOperations exposes.
            {"path": "/api/v1/bookings", "tier": "user", "method": "GET"},
            {"path": "/api/v1/bookings", "tier": "user", "method": "POST"},
            # The month/year view's own read (docs/خطة-تصميم-تقويم-الحجوزات.md §1) — how many
            # bookings land on each day of a range, never the bookings themselves.
            {"path": "/api/v1/bookings/counts", "tier": "user", "method": "GET"},
            # Stage 8 (docs/وصف-تطبيق-الحجوزات.md §2.6/§6.2): read at the moment it is useful.
            {"path": "/api/v1/bookings/risk", "tier": "user", "method": "GET"},
            # His own history, newest first, across every branch (customer page's own section).
            {"path": "/api/v1/bookings/for-customer", "tier": "user", "method": "GET"},
            # THE SHOP'S OWN WEEKLY POLICY (`bookings.manage` guards the write half only — reading
            # it needs no more than the grid itself already holds).
            {"path": "/api/v1/bookings/working-hours", "tier": "user", "method": "GET"},
            {"path": "/api/v1/bookings/working-hours", "tier": "user", "method": "PATCH"},
            # THE "AUTO" TIE-BREAKER among an "auto" service's several eligible operators — same
            # `bookings.manage` gate as the hours PATCH above.
            {"path": "/api/v1/bookings/assignment-settings", "tier": "user", "method": "GET"},
            {"path": "/api/v1/bookings/assignment-settings", "tier": "user", "method": "PATCH"},
            {"path": "/api/v1/bookings/nearest", "tier": "user", "method": "GET"},
            # THE «أي متاح» MERGE (app/core/assignment.py, Phase 0) — one call across several
            # eligible operators, replacing BookingDialog.tsx's own sequential loop against the
            # single-operator route above.
            {"path": "/api/v1/bookings/nearest-any", "tier": "user", "method": "GET"},
            {"path": "/api/v1/bookings/{}/reschedule", "tier": "user", "method": "PATCH"},
            {"path": "/api/v1/bookings/{}/services", "tier": "user", "method": "PATCH"},
            {"path": "/api/v1/bookings/{}/note", "tier": "user", "method": "PATCH"},
            {"path": "/api/v1/bookings/{}/payment", "tier": "user", "method": "PATCH"},
            {"path": "/api/v1/bookings/{}/reward", "tier": "user", "method": "PATCH"},
            {"path": "/api/v1/bookings/{}/cancel", "tier": "user", "method": "PATCH"},
            {"path": "/api/v1/bookings/{}/attend", "tier": "user", "method": "PATCH"},
            {"path": "/api/v1/bookings/{}/no-show", "tier": "user", "method": "PATCH"},
            # THE APP-STORE CARD'S OWN CONTENT (app/core/features.py) — deliberately `tier: user`
            # with no `bookings.read`/`bookings.write` requirement: a shop deciding whether to buy
            # this app has to be able to read what it would get, same posture as the price list.
            {"path": "/api/v1/bookings/features", "tier": "user", "method": "GET"},
        ],
        "ports": ports or [],  # port -> driver, from the composition root
        # FILL THIS too, or leave it empty deliberately. Same trap as capabilities: an empty
        # `emitted` reads as "this service publishes nothing", so a consumer wiring against it
        # subscribes to nothing and fails silently rather than at boot.
        # `bookings.booking.changed` (§5): what `reminders` schedules the confirmation from.
        "events": {"emitted": ["bookings.booking.changed"], "consumed": []},
        "admin_actions": _admin_actions(),
        "backup": _backup(),
        "user_actions": _user_actions(),
    }
