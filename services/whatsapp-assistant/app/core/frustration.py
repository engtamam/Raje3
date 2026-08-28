"""Frustration heuristic — a pure function over data ALREADY in `ConversationState`.

NO LLM CALL, NO I/O. The whole point of an early-escalation signal is that it must be cheap enough
to run on every `compose_reply` — a second model call purely to ask "is this customer frustrated?"
would double the cost of every turn to save some fraction of them, which is backwards. Everything
this reads (turn count, unconfirmed-proposal count, the raw window) is already sitting on the
`ConversationState` row `core/conversation.py` loaded for this turn anyway.

KEPT AS A STANDALONE FUNCTION, NOT A METHOD, so its thresholds can be unit tested directly against
constructed inputs — no store, no engine, no async — per the design point that asked for exactly
that.
"""
from __future__ import annotations


def normalize_for_duplicate_check(text: str) -> str:
    """Collapse whitespace and case so "الساعة كم؟" and "الساعة   كم؟" (or "  الساعة كم؟") count as
    the same question. Not a translation or a stem — cheap and good enough for "he asked this
    again", not for language understanding."""
    return " ".join((text or "").strip().lower().split())


def detect_frustration(*, unconfirmed_proposal_attempts: int, recent_user_texts: list[str],
                       unconfirmed_proposals_threshold: int,
                       duplicate_messages_threshold: int) -> bool:
    """True when either signal, ALONE, is enough to escalate early — before the raw turn ceiling:

      * REPEATED UNCONFIRMED PROPOSALS — a tool-proposal (propose_booking / suggest_redeemable_
        offer) is still sitting on the conversation, unconfirmed, `unconfirmed_proposals_threshold`
        turns running — the customer keeps typing instead of pressing a button, the shape of the
        assistant offering something that keeps missing what they actually want.

      * NEAR-DUPLICATE QUESTIONS — the same (normalized) customer message shows up
        `duplicate_messages_threshold` times in the raw window — the shape of someone repeating
        themselves because an earlier reply did not land.

    Both thresholds are config (app/config.py), not literals here — a tenant's actual tolerance is
    a product decision, not a number this function should own.
    """
    if unconfirmed_proposal_attempts >= max(1, unconfirmed_proposals_threshold):
        return True

    seen: dict[str, int] = {}
    threshold = max(1, duplicate_messages_threshold)
    for raw in recent_user_texts:
        norm = normalize_for_duplicate_check(raw)
        if not norm:
            continue
        seen[norm] = seen.get(norm, 0) + 1
        if seen[norm] >= threshold:
            return True
    return False
