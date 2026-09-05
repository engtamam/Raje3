"""portal — end-user (self-service) actions for the platform app catalog (Phase 36).

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
    # THE CUSTOMER'S OWN, and the only actions this service declares. Reached from the link at the
    # end of a message -- no account, no session, and no capability, because the person taking them
    # has none and never will (spec 8.6.1).
    #
    # THE FULL CUSTOMER PAGE (points, visits, preferences) IS DELETED, so its actions ("صفحتي",
    # "تعديل إشعاراتي") are gone too -- there is no route left for them to point at.
    #
    # POST /p/{ref}/data (the DSAR request) IS DELIBERATELY NOT DECLARED HERE. The route's code
    # is kept (see app/api/page.py) for reuse, but it must not be linked from any UI that ships
    # today -- an app-catalog entry would be exactly that link.
    {
        "id": "portal.stop", "label": "إيقاف العروض", "method": "GET",
        "path": "/p/{ref}/stop", "capability": "", "group": "صفحتي",
        "params": [{"name": "ref", "in": "path", "type": "string", "required": True}],
        "danger": True,
        # ONE TAP (spec 8.3). A customer who wants out is already annoyed, and making them navigate
        # is how a stop becomes a block on the shop's number. It stops MARKETING only — someone
        # unsubscribing from offers still wants to know their car is ready.
        "help": "يوقف العروض فوراً. رسائل الخدمة تستمر.",
    },
    {
        "id": "portal.allow", "label": "تفعيل العروض", "method": "GET",
        "path": "/p/{ref}/allow", "capability": "", "group": "صفحتي",
        "params": [{"name": "ref", "in": "path", "type": "string", "required": True}],
        # ASKING IS A SCREEN, GRANTING IS THE POST. A GET that granted would make WhatsApp's own
        # link preview a consent record — see api/page.py.
        "help": "يعرض شاشة واحدة: ما الذي سيصلك، وكم مرة، وكيف توقفه. الموافقة بضغطة الزر.",
    },
    {
        "id": "portal.grant", "label": "أرسلوا لي العروض", "method": "POST",
        "path": "/p/{ref}/allow", "capability": "", "group": "صفحتي",
        "params": [{"name": "ref", "in": "path", "type": "string", "required": True}],
        "help": "يسجّل موافقتك على استقبال العروض، بالنصّ الذي عُرض عليك ونسخته.",
    },
]


# Routes deliberately NOT rendered as app controls, each with the reason. The wiring gate reads
# this list and refuses an entry without a `why`.
UNDECLARED_ROUTES: list[dict[str, str]] = [
    {"method": "POST", "path": "/p/{}/data",
     "why": "the DSAR request route survives the full customer page's deletion on purpose, kept "
            "callable for reuse (e.g. wired to WhatsApp, or a future UI) — but there is no page "
            "left to put its button on, and declaring it here would be exactly that button"},
]
