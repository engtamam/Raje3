"""campaigns — end-user (self-service) actions for the platform app catalog (Phase 36).

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
    # NOTHING. A campaign is the establishment acting on its customers — never a customer acting
    # on their own data. What a customer controls about campaigns is the marketing switch, and
    # that lives in reminders where the preference is stored (spec 8.4.2 section 5).
    #
    # Declared empty and reviewed rather than left unwritten: an empty list a reader can see was
    # decided is worth more than one they have to guess about.
    # ── the owner's own surface, moved here from admin_actions ─────────────────────────
    # api-gateway builds the establishment's app from THIS file and no other
    # (app_catalog.py, field="user_actions"). These sat in the platform console's catalogue,
    # so the owner's app would have rendered a nav with almost nothing in it — and the reflex
    # fix is to call the paths directly, which is exactly the rule the UI is built on. The
    # test for which file a route belongs in is whose data it is: `platform.*` is ours;
    # everything else belongs to the establishment.
    {
        "id": "campaigns.goals", "label": "أهداف الحملات", "method": "GET",
        "path": "/api/v1/campaigns/goals", "capability": "campaigns.read", "group": "الحملات",
        # The five cards, with their locks and their reasons. The screen renders what this returns
        # rather than computing availability itself — two answers that disagree is worse than one.
        "help": "ماذا تريد أن تحقّق؟ خمس بطاقات، وكل واحدة تقول متى تتاح.",
    },
    {
        "id": "campaigns.preview", "label": "معاينة قبل الإرسال", "method": "POST",
        "path": "/api/v1/campaigns/preview", "capability": "campaigns.read", "group": "الحملات",
        # The middle screen and the one the whole feature rests on: the real message, and a count
        # of PEOPLE.
        "help": "الرسالة كما ستصل، وكم عميلاً تصلهم.",
    },
    {
        "id": "campaigns.create", "label": "أطلق الحملة", "method": "POST",
        "path": "/api/v1/campaigns", "capability": "campaigns.manage",
        "confirm": True, "group": "الحملات",
        "help": "يرسل الآن، أو يجدول، أو يشغّل قاعدة دائمة — بحسب الهدف.",
    },
    {
        "id": "campaigns.list", "label": "حملاتي", "method": "GET",
        "path": "/api/v1/campaigns", "capability": "campaigns.read", "group": "الحملات",
        "help": "ما يعمل الآن، وما انتهى، وما هو متوقف.",
    },
    {
        "id": "campaigns.runs", "label": "ماذا حدث", "method": "GET",
        "path": "/api/v1/campaigns/{campaign_id}/runs", "capability": "campaigns.read",
        "params": [{"name": "campaign_id", "in": "path", "type": "string", "required": True}],
        "group": "الحملات",
        # THE MOST IMPORTANT ONE. "It didn't arrive" is the only complaint this product generates,
        # and this is the only screen that answers it.
        "help": "كل إرسالة: كم وصلت، وكم امتنعت، ولماذا.",
    },
    {
        "id": "campaigns.pause", "label": "إيقاف حملة", "method": "POST",
        "path": "/api/v1/campaigns/{campaign_id}/pause", "capability": "campaigns.manage",
        "params": [{"name": "campaign_id", "in": "path", "type": "string", "required": True}],
        "confirm": True, "group": "الحملات",
        "help": "توقف القاعدة الدائمة. سجلّها يبقى.",
    },
]
