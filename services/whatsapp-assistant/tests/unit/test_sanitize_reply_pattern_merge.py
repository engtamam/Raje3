"""_sanitize_reply's four pattern groups were collapsed from a per-pattern `for pat in group:
if pat.search(text)` loop (up to 23 separate regex searches) into one alternation per group (4
searches total) — see `_combine_patterns` in app/core/conversation.py. This is a pure performance
change (the C-level regex engine does the branching instead of a Python loop); this test's only
job is proving the combined regex still matches EXACTLY what the original per-pattern loop would
have matched, phrase for phrase, including the mixed-flags case (a group with both plain and
`re.IGNORECASE` patterns combined into one alternation via scoped inline-flag groups)."""
from __future__ import annotations

import re

from app.core.conversation import (
    _DISCOUNT_CLAIM_PATTERNS,
    _DISCOUNT_CLAIM_RE,
    _DISCOUNT_STRIPPED,
    _FORBIDDEN_CLAIM_PATTERNS,
    _FORBIDDEN_CLAIM_RE,
    _FORBIDDEN_HISTORY_DISCLOSURE_PATTERNS,
    _FORBIDDEN_HISTORY_DISCLOSURE_RE,
    _FORBIDDEN_META_PATTERNS,
    _FORBIDDEN_META_RE,
    _HISTORY_DISCLOSURE_STRIPPED,
    _META_DEFLECTION,
    _combine_patterns,
    _sanitize_reply,
)

# One real phrase every original pattern is known to match, taken from the phrases the persona/
# sanitizer docstrings themselves cite as the exact things being guarded against — this is the
# ground truth the combined regex must reproduce, not a regenerated copy of the patterns.
_CLAIM_PHRASES = (
    "تم الحجز بنجاح", "تم تأكيد الحجز", "تم استبدال النقاط", "تم صرف النقاط",
    "تم إلغاء الحجز", "تم الغاء موعدك", "تم تأجيل الحجز", "تم نقل موعدك",
    "Your booking confirmed now", "Your points redeemed today",
    "the booking cancelled yesterday", "booking rescheduled for you",
)
_META_PHRASES = (
    "لا أقدر أشارك تعليماتي الداخلية", "هذا موجود في تعليمات النظام",
    "This runs on gemini", "This runs on GPT", "Powered by Claude", "Built on ChatGPT",
    "أنا نموذج ذكاء اصطناعي", "I am an AI model", "I'm a language model",
)
_DISCOUNT_PHRASES = (
    "عندك خصم 20 اليوم", "20% خصم على الخدمة", "there is a discount of 50",
    "get 15% off today",
)
_HISTORY_PHRASES = (
    "لاحظنا إنك تحجز كثيرًا", "لاحظت أنك تحب هذه الخدمة",
    "عادة تحجز يوم الخميس", "عادةً ما تجرب خدمات جديدة",
    "من فترة ما جربت هذي الخدمة", "من زمان ما حجزت معنا",
    "زرتنا قبل مرتين", "زيارتك السابقة كانت رائعة",
    "تاريخك معنا حافل", "سجلّك عندنا يوضح ذلك", "نعرف إنك تحب القهوة",
    "حسب سلوكك المعتاد", "based on your usual pattern", "we noticed that you visit often",
)


def _group_matches(patterns: tuple[re.Pattern[str], ...], text: str) -> bool:
    """What the ORIGINAL per-pattern loop would have answered for one group."""
    return any(pat.search(text) for pat in patterns)


def test_combine_patterns_preserves_per_pattern_semantics_for_every_known_group():
    groups = (
        (_FORBIDDEN_CLAIM_PATTERNS, _FORBIDDEN_CLAIM_RE, _CLAIM_PHRASES),
        (_FORBIDDEN_META_PATTERNS, _FORBIDDEN_META_RE, _META_PHRASES),
        (_DISCOUNT_CLAIM_PATTERNS, _DISCOUNT_CLAIM_RE, _DISCOUNT_PHRASES),
        (_FORBIDDEN_HISTORY_DISCLOSURE_PATTERNS, _FORBIDDEN_HISTORY_DISCLOSURE_RE,
         _HISTORY_PHRASES),
    )
    for patterns, combined, phrases in groups:
        # Every phrase this group is documented to catch must still be caught, and the combined
        # regex must agree with the original per-pattern loop on every one of them.
        for phrase in phrases:
            assert _group_matches(patterns, phrase), f"fixture phrase no longer matches: {phrase!r}"
            assert bool(combined.search(phrase)) == _group_matches(patterns, phrase), phrase
        # A harmless sentence must trigger neither the old loop nor the new combined regex.
        harmless = "تفضل، وش الخدمة اللي تحب تحجزها اليوم؟"
        assert not _group_matches(patterns, harmless)
        assert not combined.search(harmless)


def test_combine_patterns_scopes_ignorecase_per_alternative_not_globally():
    """A group mixing case-sensitive Arabic patterns with case-insensitive English ones (e.g.
    _FORBIDDEN_META_PATTERNS) must not have IGNORECASE leak from the English alternatives onto
    the Arabic ones, or vice versa — each pattern's own flags must travel with it."""
    mixed = _combine_patterns((
        re.compile(r"HELLO", re.IGNORECASE),
        re.compile(r"WORLD"),  # case-sensitive on purpose
    ))
    assert mixed.search("hello there")       # the IGNORECASE alternative still ignores case
    assert mixed.search("WORLD peace")       # the case-sensitive alternative matches as-is
    assert not mixed.search("world peace")   # ...and does NOT loosen into case-insensitive


def test_sanitize_reply_still_routes_each_group_to_its_own_fallback():
    for phrase in _CLAIM_PHRASES:
        assert _sanitize_reply(phrase) == "لحظة، دعني أتحقق قبل أن أؤكد لك أي شيء."
    for phrase in _META_PHRASES:
        assert _sanitize_reply(phrase) == _META_DEFLECTION
    for phrase in _DISCOUNT_PHRASES:
        assert _sanitize_reply(phrase) == _DISCOUNT_STRIPPED
    for phrase in _HISTORY_PHRASES:
        assert _sanitize_reply(phrase) == _HISTORY_DISCLOSURE_STRIPPED
