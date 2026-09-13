"""A shop owner's own kill switch for the WhatsApp AI assistant — off means CLOSED, exactly as if
`feature.whatsapp` had never been bought at all, never a softer "paused" state.

WHY THIS EXISTS, SEPARATE FROM THE SUBSCRIPTION. Buying the assistant and wanting it silent right
now are two different decisions, and until this file the platform only had the first one: a shop
that pays for `feature.whatsapp` gets an AI turn on every message, for ever, with no owner-facing
way to stop it short of cancelling the whole app. An owner handling a sensitive customer by hand,
or one who simply wants a quiet week, had no lever — the only "off" available was "unsubscribe",
which drops the entitlement itself, not just the behaviour.

ABSENT MEANS ON, same discipline as `ai_notes.py`/`msg_limits.py`: a row exists only because an
owner actually pressed the switch, never because he subscribed. Every shop that has never touched
this reads back enabled, which is today's behaviour unchanged.

THE ENFORCEMENT LIVES IN whatsapp-assistant/core/licence.py, NOT HERE. This module only stores the
owner's choice and answers it; the shop-name peer call (api/internal.py::shop_name) already rides
once per turn and is where whatsapp-assistant learns it, exactly like `ai_notes`/`msg_word_limit`
before it — a fourth peer call for a fourth switch would be the wrong direction.
"""
from __future__ import annotations

import time
from typing import Any

AI_TOGGLE = "shop_ai_toggle"


class AiToggleStore:
    """One row per establishment. Absent means «on» — most shops never touch this."""

    def __init__(self, store: Any) -> None:
        self._s = store

    async def get(self, tenant: str) -> bool:
        if not tenant:
            return True
        try:
            row = await self._s.get(AI_TOGGLE, tenant)
        except Exception:                                                    # noqa: BLE001
            # UNREADABLE READS AS «ON» — the same asymmetry `AiNotesStore.get` takes, but mirrored:
            # there, unreadable degrades to the harmless empty string; here, unreadable degrades to
            # today's unchanged behaviour (the AI still runs) rather than silently switching a
            # shop's assistant off because a read blinked.
            return True
        if row is None:
            return True
        return bool(row.get("enabled", True))

    async def set(self, tenant: str, enabled: bool) -> dict[str, Any]:
        row = {"tenant": tenant, "enabled": enabled, "updated_at": int(time.time())}
        await self._s.put(AI_TOGGLE, tenant, row)
        return row
