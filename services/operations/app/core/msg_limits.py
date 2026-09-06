"""How many words a customer's single WhatsApp message may be before the AI assistant refuses it
outright — never calling the model at all — and asks for something shorter.

WHY THIS EXISTS: a message that is already far longer than anyone would type on WhatsApp is either
someone testing the bot's limits or an attempt to pad the prompt itself (both cost real tokens
either way) — refusing it before the model is ever called is strictly cheaper AND strictly safer
than any prompt-side instruction, which a long-enough message could in principle still influence.

SAME SHAPE AS `ai_notes.py`: ABSENT MEANS THE DEFAULT, never an error — a shop that has never
touched this setting gets `DEFAULT_MSG_WORD_LIMIT` words, not a missing-config failure. One row per
tenant, one collection, no schema migration.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

MSG_WORD_LIMITS = "shop_msg_word_limits"

#: The out-of-the-box ceiling — generous enough for a real question, short enough that a customer
#: padding a message to influence the prompt gains nothing from it.
DEFAULT_MSG_WORD_LIMIT = 100

#: An owner can tighten this (a shop that wants terser customers) or loosen it somewhat, but never
#: past a bound that would either make the field useless (too low to ever hold a real sentence) or
#: defeat the whole point of the feature (high enough that a padded message reaches the model
#: essentially uncapped).
MIN_MSG_WORD_LIMIT = 20
MAX_MSG_WORD_LIMIT = 300


class MsgWordLimitError(Exception):
    """A refusal the owner can act on."""


def sanitise(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise MsgWordLimitError("القيمة يجب أن تكون رقماً صحيحاً.")
    if value < MIN_MSG_WORD_LIMIT or value > MAX_MSG_WORD_LIMIT:
        raise MsgWordLimitError(
            f"يجب أن تكون القيمة بين {MIN_MSG_WORD_LIMIT} و{MAX_MSG_WORD_LIMIT} كلمة.")
    return value


@dataclass
class MsgWordLimitRow:
    limit: int
    updated_at: int


class MsgWordLimitStore:
    """One row per establishment. Absent means «use the default», most shops."""

    def __init__(self, store: Any) -> None:
        self._s = store

    async def get(self, tenant: str) -> int:
        if not tenant:
            return DEFAULT_MSG_WORD_LIMIT
        try:
            row = await self._s.get(MSG_WORD_LIMITS, tenant)
        except Exception:                                                    # noqa: BLE001
            # UNREADABLE FALLS BACK TO THE DEFAULT, never a 500 — same asymmetry as
            # AiNotesStore.get: worst case a shop's own limit resets to the default for one turn.
            return DEFAULT_MSG_WORD_LIMIT
        if not row:
            return DEFAULT_MSG_WORD_LIMIT
        try:
            return int(row.get("limit"))
        except (TypeError, ValueError):
            return DEFAULT_MSG_WORD_LIMIT

    async def set(self, tenant: str, limit: int) -> dict[str, Any]:
        row = {"tenant": tenant, "limit": limit, "updated_at": int(time.time())}
        await self._s.put(MSG_WORD_LIMITS, tenant, row)
        return row
