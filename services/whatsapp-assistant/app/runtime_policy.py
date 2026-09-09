"""The settings an operator may change at runtime, for this service.

DECLARING A KEY HERE IS A PROMISE THAT SOMETHING READS IT through RuntimeConfig at the point of
use. That promise is the entire point: offering every settable field to the panel instead fails in
the most convincing way available — the panel accepts the change, the audit log records it with an
actor and a timestamp, and behaviour does not move, because nothing consults the override. The
operator ends up holding a receipt for a change that never happened.

FIRST SLICE — the console's "المزوّدين الخارجيين ← الذكاء الاصطناعي ← الإدارة" screen
needs live control over the model and a couple of behavioural knobs without a redeploy; these three
are read through RuntimeConfig at the exact points named below, in the same change that added them
here. Everything else this service tunes (thresholds, session timing, feature toggles) stays
deploy-time env until a later slice wires its own read the same way — never declared ahead of that.

SECOND SLICE, SAME DAY — the AI-unit pricing keys below (المحاسبة, the calculator tab). These do
NOT apply instantly like the three above: see core/pricing_schedule.py's own docstring for why a
pricing change is scheduled with a delay rather than set live the moment an operator confirms it.
They still belong in THIS policy (the promise this file's docstring makes) because the same
`RuntimeConfig.set()` is what a due scheduled change is ultimately applied through, once the tick
finds it due — core/ai_unit_pricing.py's own resolve function is the real per-request read.
"""
from __future__ import annotations

from typing import Any

from app.core.runtime_config import RuntimeConfigError

RUNTIME_POLICY: frozenset[str] = frozenset({
    # Which Gemini model the assistant calls — app/adapters/llm/assistant_service.py::respond()
    # reads it per turn, so a switch takes effect on the very next conversation turn, no redeploy.
    "ASSISTANT_MODEL_NAME",
    # Soft-decline (core/soft_decline.py) — core/conversation.py::compose_reply reads it per turn.
    "SOFT_DECLINE_THRESHOLD",
    # The carousel size ceiling — core/tools.py::validate_and_render reads it per
    # suggest_services_carousel call, via the value ConversationEngine now resolves live rather
    # than freezing at construction (see core/conversation.py's own note on this field).
    "MAX_CAROUSEL_CARDS",
    # The output-token cost ceiling — app/adapters/llm/assistant_service.py::respond()
    # reads it per turn, same live-override shape as ASSISTANT_MODEL_NAME just above. A technical
    # safety knob, never a shop-facing one — see MAX_REPLY_TOKENS's own config.py note.
    "MAX_REPLY_TOKENS",
    # ── AI-unit pricing (core/ai_unit_pricing.py, read by core/conversation.py's own reserve math
    # and the console's calculator "وحدات الذكاء" tab) — see core/pricing_schedule.py's own
    # docstring for why these are scheduled with a delay rather than applied instantly.
    "PRICING_AI_UNIT_UNITS_PER_HALALA",
    "PRICING_AI_UNIT_INPUT_MARGIN_MULTIPLIER",
    "PRICING_AI_UNIT_OUTPUT_MARGIN_MULTIPLIER",
    "PRICING_AI_UNIT_USD_TO_SAR",
    "PRICING_AI_UNIT_MODEL_COSTS_JSON",
})


# THE BOOT GUARD'S RULES, APPLIED TO A LIVE OVERRIDE TOO — this module's own docstring already
# promises it ("THE BOOT GUARD'S RULES APPLY AT RUNTIME TOO"), but `RuntimeConfig.set()`'s
# `_coerce` only casts to the field's TYPE, never re-runs the Settings class's own
# `field_validator`s (core/runtime_config.py's own `_coerce` docstring says so explicitly). Without
# this wired in as `RuntimeConfig`'s `validate=`, a value like `SOFT_DECLINE_THRESHOLD=0` or
# `MAX_CAROUSEL_CARDS=500` passed type-coercion cleanly and broke the very next conversation that
# touched it — exactly the "typo breaks production" gap this closes. Mirrors
# api/v1/operator.py's own `_ai_unit_bounds_violation`, same reasoning, for the three
# INSTANT-apply keys rather than the scheduled pricing ones.
def validate_runtime_override(key: str, value: Any) -> None:
    if key == "SOFT_DECLINE_THRESHOLD" and not (isinstance(value, int) and value > 0):
        raise RuntimeConfigError(
            f"{key}: {value!r} — must be a positive whole number; zero or negative would "
            f"escalate every single turn, or never respect a decline at all")
    if key == "MAX_CAROUSEL_CARDS" and not (isinstance(value, int) and 2 <= value <= 10):
        raise RuntimeConfigError(
            f"{key}: {value!r} — Meta's own WhatsApp carousel bounds are 2-10 cards")
    if key == "MAX_REPLY_TOKENS" and not (isinstance(value, int) and 1 <= value <= 4_000):
        raise RuntimeConfigError(
            f"{key}: {value!r} — must be a positive token count up to 4,000; a WhatsApp reply "
            f"is a few sentences at most")
