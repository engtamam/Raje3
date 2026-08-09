"""reminders — end-user (self-service) actions for the platform app catalog (Phase 36).

The end-user app (GET /api/v1/app/catalog) aggregates what every service declares HERE — the twin of
`admin_actions`, but for a USER acting on their OWN data (their files, their profile, their
subscription), never platform-operator routes. The code is the source, so the app can never drift.

Declaring nothing is fine — keep the list empty and reviewed rather than forgotten. Each action is a
PURE literal dict (the safety:user-actions CI gate reads it with ast.literal_eval — no variables, no
f-strings). Shape (docs/contracts/user-actions.schema.json):

    {
        "id": "svc.do_thing",              # stable, kebab/dot, unique
        "label": "Do the thing",           # what the control says
        "method": "POST",                  # GET|POST|PUT|PATCH|DELETE (allow-listed)
        "path": "/api/v1/things/{id}",     # RELATIVE — no scheme/host; must be a real manifest route
        "capability": "things.write",      # the cap the route ENFORCES; must be advertised in the manifest
        "params": [{"name": "id", "in": "path", "type": "string", "required": True}],
        "confirm": True,                   # UX: ask before firing (auto-true when danger)
        "danger": True,                    # UX: destructive for the user (e.g. delete my account)
        "group": "Things",                 # UX: section
    }

Rules the gate enforces: the path must exist in this service's manifest `endpoints`; the capability
must be in the manifest's advertised `capabilities`. The app is a MAP, never the AUTHORITY — every
action is re-checked AND re-scoped to the caller's own tenant/identity at its route. Only declare the
user's OWN self-service (`_SELF` / ordinary user-cap) routes; operator (platform.*) and internal-token
routes belong in admin_actions or nowhere.
"""
from __future__ import annotations

from typing import Any


USER_ACTIONS: list[dict[str, Any]] = [
    # THE CUSTOMER'S OWN SWITCHES. Reached from the link at the end of a message — no token in the
    # URL, because that link is forwardable and anyone who receives it must not see whose it is
    # (spec 8.6.1). The route re-scopes to the signed reference it was opened with.
    {
        "id": "reminders.get_prefs", "label": "إشعاراتي", "method": "GET",
        "path": "/api/v1/prefs/{ref}", "capability": "reminders.read", "group": "إشعاراتي",
        "params": [{"name": "ref", "in": "path", "type": "string", "required": True}],
        "help": "أي أنواع الرسائل تصلك من هذا المحل.",
    },
    {
        "id": "reminders.set_prefs", "label": "تعديل إشعاراتي", "method": "PUT",
        "path": "/api/v1/prefs/{ref}", "capability": "reminders.read", "group": "إشعاراتي",
        "params": [{"name": "ref", "in": "path", "type": "string", "required": True}],
        # FIVE SWITCHES, INCLUDING THE PERSONAL ONE. An earlier draft exempted personal messages
        # because the customer started them — true at the time, and not true forever. Someone who
        # switches everything off has said what they want, and keeping a channel open over their
        # objection is not a service to them (spec 8.4.2 section 5).
        "help": "أوقف أي نوع من الخمسة على حدة، أو أوقفها كلها.",
    },
]
