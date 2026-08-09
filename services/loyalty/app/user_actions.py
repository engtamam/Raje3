"""loyalty — end-user (self-service) actions for the platform app catalog (Phase 36).

The app (GET /api/v1/app/catalog) aggregates what every service declares HERE. Each action is a
PURE literal dict — the safety:user-actions CI gate reads it with ast.literal_eval.

WHO "THE USER" IS ON THIS SURFACE. It is the person holding the field screen: the operator looking
a customer up and spending his points. That is why the balance, the affordable rewards, the history
and the redemption are all declared here rather than in `admin_actions` — they are one screen's
worth of work, performed in front of the customer, and the console renders exactly what is listed.

REDEMPTION IS AN OPERATOR ACTION AND NOT A MANAGER'S (spec §9.5). A manager approving every
redemption is a bottleneck in a busy shop, and the outcome is a programme nobody uses. The control
is the receipt the customer receives within seconds, plus a threshold above which the owner does
require a manager.
"""
from __future__ import annotations

from typing import Any


USER_ACTIONS: list[dict[str, Any]] = [
    {
        "id": "loyalty.balance", "label": "رصيد النقاط", "method": "GET",
        "path": "/api/v1/loyalty/balance/{subject_ref}", "capability": "loyalty.read",
        "params": [{"name": "subject_ref", "in": "path", "type": "string", "required": True}],
        "group": "الولاء",
        # Read on every customer lookup inside the five-second journey (spec §4.7), which is why
        # it returns a materialised total and only the rewards this balance can afford.
    },
    {
        "id": "loyalty.redeem", "label": "استبدال", "method": "POST",
        "path": "/api/v1/loyalty/redeem", "capability": "loyalty.redeem",
        "confirm": True, "group": "الولاء",
        # Confirmed, because it spends something the customer owns. The idempotency key is
        # REQUIRED by the route: a phone in a service lane retries, and a retry without a key is
        # a second spend the customer holds a receipt for.
    },
    {
        "id": "loyalty.history", "label": "حركة النقاط", "method": "GET",
        "path": "/api/v1/loyalty/history/{subject_ref}", "capability": "loyalty.read",
        "params": [{"name": "subject_ref", "in": "path", "type": "string", "required": True}],
        "group": "الولاء",
        # The answer to "where did my points go?" — asked at the counter, by the person whose
        # points they were, which is the moment the whole ledger design exists to serve.
    },
]
