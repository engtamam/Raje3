"""whatsapp-assistant — auditable actions: what this service must be able to PROVE it did.

See services/loyalty/app/auditable_actions.py for the full house-style explanation of this file's
format and the four action sources. The two CRITICAL actions here are exactly the two state-
changing tools this service can ever fire on a customer's behalf (app/core/tools.py) — both reached
only from a button_reply match, never from the model's own decision.
"""
from __future__ import annotations

from typing import Any

AUDITABLE_ACTIONS: list[dict[str, Any]] = [
    {
        "action": "whatsapp_assistant.booking_confirmed",
        "source": "internal",
        "critical": True,
        "resource": "booking",
        "why": "a booking made on a customer's behalf with nobody standing at a counter to "
               "witness it. If the audit log cannot record it, the action must not happen — an "
               "unprovable auto-booking is indistinguishable from a bug that double-booked a slot",
    },
    {
        "action": "whatsapp_assistant.points_redeemed",
        "source": "internal",
        "critical": True,
        "resource": "reward",
        "why": "spends something the customer owns, with no cashier present. Same reasoning as "
               "loyalty's till redemption: an unattributable spend of a customer's balance is the "
               "one thing a dispute months later cannot be resolved without",
    },
    {
        "action": "whatsapp_assistant.proposal_rejected",
        "source": "system",
        "critical": False,
        "resource": "proposal",
        "why": "the server-side re-validation gate (core/tools.py) refused a model's proposal — "
               "a slot that filled, a reward that no longer qualifies. Not critical: refusing to "
               "record a REFUSAL because the log is down protects nothing, and the refusal itself "
               "already means nothing was spent or booked",
    },
]
