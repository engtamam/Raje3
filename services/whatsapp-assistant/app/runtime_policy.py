"""The settings an operator may change at runtime, for this service.

DECLARING A KEY HERE IS A PROMISE THAT SOMETHING READS IT through RuntimeConfig at the point of
use. That promise is the entire point: offering every settable field to the panel instead fails in
the most convincing way available — the panel accepts the change, the audit log records it with an
actor and a timestamp, and behaviour does not move, because nothing consults the override. The
operator ends up holding a receipt for a change that never happened.

FIRST SLICE (2026-09-07) — the console's "المزوّدين الخارجيين ← الذكاء الاصطناعي ← الإدارة" screen
needs live control over the model and a couple of behavioural knobs without a redeploy; these three
are read through RuntimeConfig at the exact points named below, in the same change that added them
here. Everything else this service tunes (thresholds, session timing, feature toggles) stays
deploy-time env until a later slice wires its own read the same way — never declared ahead of that.
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
})
