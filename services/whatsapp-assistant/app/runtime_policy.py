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

SECOND SLICE, SAME DAY — the seven PRICING_* keys (المحاسبة, the calculator tab). These do NOT
apply instantly like the three above: see core/pricing_schedule.py's own docstring for why a
pricing change is scheduled with a delay rather than set live the moment an operator confirms it.
They still belong in THIS policy (the promise this file's docstring makes) because the same
`RuntimeConfig.set()` is what a due scheduled change is ultimately applied through, once the tick
finds it due — core/pricing.py::PricingConfig.from_runtime() is the real per-request read.
"""
from __future__ import annotations

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
    # ── pricing (core/pricing.py::PricingConfig.from_runtime, read by api/internal.py::price()) ──
    "PRICING_STRATEGY",
    "PRICING_TIER_BASE_HALALAS",
    "PRICING_TIER_INCLUDED_CONVERSATIONS",
    "PRICING_TIER_OVERAGE_HALALAS_PER_CONVERSATION",
    "PRICING_ADDON_FLAT_HALALAS",
    "PRICING_USAGE_HALALAS_PER_1K_TOKENS",
    "PRICING_USAGE_HALALAS_PER_CONVERSATION",
    # ── AI-unit pricing (core/ai_unit_pricing.py, read by core/conversation.py's own reserve math
    # and the console's calculator "وحدات الذكاء" tab) — same scheduled-change reasoning as the
    # seven above, extending the SAME mechanism rather than a second one.
    "PRICING_AI_UNIT_UNITS_PER_HALALA",
    "PRICING_AI_UNIT_INPUT_MARGIN_MULTIPLIER",
    "PRICING_AI_UNIT_OUTPUT_MARGIN_MULTIPLIER",
    "PRICING_AI_UNIT_USD_TO_SAR",
    "PRICING_AI_UNIT_MODEL_COSTS_JSON",
})
