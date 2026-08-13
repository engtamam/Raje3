"""insights — end-user (self-service) actions for the app catalog (Phase 36).

NOTHING, and declared empty rather than left unwritten.

This service has no end-user surface at all. A customer never sees an indicator: the dashboard is
the establishment's view of its own business, and every route here is the owner's or ours. What a
CUSTOMER controls about being measured is their notification preferences and their erasure, and
both live where the data does — `reminders` and `compliance`.

An empty list a reader can see was decided is worth more than one they have to guess about.
"""
from __future__ import annotations

from typing import Any


USER_ACTIONS: list[dict[str, Any]] = [    # ── the owner's own surface, moved here from admin_actions ─────────────────────────
    # api-gateway builds the establishment's app from THIS file and no other
    # (app_catalog.py, field="user_actions"). These sat in the platform console's catalogue,
    # so the owner's app would have rendered a nav with almost nothing in it — and the reflex
    # fix is to call the paths directly, which is exactly the rule the UI is built on. The
    # test for which file a route belongs in is whose data it is: `platform.*` is ours;
    # everything else belongs to the establishment.
    {
        "id": "insights.dashboard", "label": "لوحة المؤشرات", "method": "GET",
        "path": "/api/v1/insights/dashboard", "capability": "insights.read", "group": "المؤشرات",
        # Everything in one read: eleven indicators fetched separately is eleven round trips on a
        # phone, and the screen would paint itself in pieces.
    },
    {
        "id": "insights.refresh", "label": "حدّث المؤشرات", "method": "POST",
        "path": "/api/v1/insights/refresh", "capability": "insights.read", "group": "المؤشرات",
        # SAME CAPABILITY AS READING, deliberately: it computes nothing new about the shop, it
        # only computes it EARLIER. Whoever may see the numbers may ask for today's.
    },
    {
        "id": "insights.associations", "label": "الترابطات", "method": "GET",
        "path": "/api/v1/insights/associations", "capability": "insights.read",
        "group": "المؤشرات",
        # Returns the verdict and the count, never the arithmetic — the engine is ours.
    },
    {
        "id": "insights.bundles", "label": "الباقات المقترحة", "method": "GET",
        "path": "/api/v1/insights/bundles", "capability": "insights.read", "group": "المؤشرات",
        # We say where the relationship is and how many customers it covers. He sets the price.
    },
    {
        "id": "insights.branches", "label": "مقارنة الفروع", "method": "GET",
        "path": "/api/v1/insights/branches", "capability": "insights.read", "group": "المؤشرات",
    },
    {
        "id": "insights.digest", "label": "التقرير الأسبوعي", "method": "PUT",
        "path": "/api/v1/insights/digest", "capability": "insights.read", "group": "المؤشرات",
        # Per person, not per establishment: a manager may want it and the owner may not.
    },
]
