"""core/conversation.py::_estimate_input_tokens — the fast, local, real-measurement estimate that
replaced a flat one-size-fits-all token guess for the wallet reserve. Pure function, no I/O.
"""
from __future__ import annotations

from app.core.conversation import _CHARS_PER_TOKEN_ESTIMATE, _estimate_input_tokens


def test_a_bigger_context_block_estimates_more_tokens():
    small = _estimate_input_tokens("persona", "خدمة واحدة فقط", "", [], "مرحبا")
    big = _estimate_input_tokens(
        "persona", "خدمة " * 500, "", [], "مرحبا")
    assert big > small


def test_every_part_of_the_turn_is_actually_counted():
    """system_prompt, context_block, summary, recent_messages, AND user_message all count —
    missing even one would under-price the exact thing the real LLM call is about to send."""
    baseline = _estimate_input_tokens("", "", "", [], "")
    assert baseline == 0

    with_system_prompt = _estimate_input_tokens("ABCDEFGHIJ", "", "", [], "")
    assert with_system_prompt > baseline

    with_context = _estimate_input_tokens("", "ABCDEFGHIJ", "", [], "")
    assert with_context > baseline

    with_summary = _estimate_input_tokens("", "", "ABCDEFGHIJ", [], "")
    assert with_summary > baseline

    with_recent = _estimate_input_tokens("", "", "", [{"role": "user", "text": "ABCDEFGHIJ"}], "")
    assert with_recent > baseline

    with_user_message = _estimate_input_tokens("", "", "", [], "ABCDEFGHIJ")
    assert with_user_message > baseline


def test_the_estimate_rounds_up_never_down():
    """An odd character count must not silently truncate to a cheaper token count — the reserve
    exists to never under-price, the same discipline `estimated_hold_halalas`'s own `math.ceil`
    already holds for the halala amount itself."""
    odd_length_text = "x" * (_CHARS_PER_TOKEN_ESTIMATE * 3 + 1)   # not an exact multiple
    tokens = _estimate_input_tokens(odd_length_text, "", "", [], "")
    assert tokens == 4   # ceil((3*N + 1) / N) == 4, never 3
