"""Soft-decline heuristic — a pure function, no LLM, no I/O. Same shape and same reasoning as
core/frustration.py right beside it: cheap enough to run on every compose_reply, built from data
already on ConversationState.

DIFFERENT SIGNAL FROM FRUSTRATION, ON PURPOSE. frustration.py answers "should this conversation
escalate to a human" — a hard stop. This answers a narrower question: "did the customer just wave
off ONE promotional suggestion" — no escalation, the conversation continues completely normally;
only the PROMOTIONAL tools (core/tools.py::PROMO_TOOLS) go quiet for the rest of this session. A
customer who says "لا شكراً" to a package suggestion is not frustrated — pushing a SECOND pitch at
him right after is what would make him frustrated. Two declines this session is the line: one is
normal conversation, two is a pattern worth respecting.

DELIBERATELY BROAD, SAME TOLERANCE AS EVERY OTHER REGEX BACKSTOP IN THIS SERVICE (see
conversation.py's `_FORBIDDEN_HISTORY_DISCLOSURE_PATTERNS` docstring): a false positive costs one
turn where a promo tool was needlessly withheld — cheap. A miss costs one more unwanted pitch —
also cheap, and the NEXT decline still catches it. Neither failure mode is the customer's business
being lost, which is exactly why this stays a cheap heuristic rather than a second LLM call.
"""
from __future__ import annotations

import re

_DECLINE_PATTERNS = (
    re.compile(r"^\s*لا\s*(شكرا|شكراً)?\s*$"), re.compile(r"لا\s+ابغى|لا\s+أبغى|ما\s+ابغى|ما\s+أبغى"),
    re.compile(r"ما\s+احتاج|ما\s+أحتاج|بلاش|خلاص\s*$"), re.compile(r"مو\s+الحين|مو\s+الآن|بعدين\s*$"),
    re.compile(r"\bno\s+thanks\b", re.IGNORECASE), re.compile(r"^\s*no\s*$", re.IGNORECASE),
)


def is_decline(text: str) -> bool:
    """True when the customer's own message reads as waving off a suggestion — short, dismissive,
    no real question inside it. A long message that HAPPENS to contain "لا" somewhere is not
    this — every pattern here anchors to the message being SHORT and essentially only the
    dismissal, so a genuine follow-up question is never mistaken for a decline."""
    stripped = (text or "").strip()
    if not stripped or len(stripped) > 20:
        return False
    return any(p.search(stripped) for p in _DECLINE_PATTERNS)
