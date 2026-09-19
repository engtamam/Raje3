"""Real usage, aggregated from COST_LEDGER — what the console's pricing calculator reads instead
of a guessed average, when the operator picks "من قيمة النظام" over typing one by hand.

WINDOWED, NOT ALL-TIME. `days` bounds the scan (see `report()`) — an assistant running for a year
should not force this read to walk a year of rows to answer "what does last month look like",
and a recent window is the honest basis for a FORWARD projection anyway (a rate from a year ago
predicts nothing about next month's volume).

PLATFORM-WIDE BY DEFAULT — `tenant=None` (the operator route's own default) aggregates every shop,
which is the number a pricing DECISION needs (same reasoning as pricing_schedule.py and every
PRICING_* knob itself: "how much does running this feature cost us across every shop"). A real
`tenant` value scopes to just that one shop's own COST_LEDGER rows instead — added 2026-09-07 so a
FUTURE shop-facing screen (e.g. "محلي"'s own AI-usage stat) can call this same function safely,
without ever seeing another shop's numbers folded into its own. Never infer which mode a caller
wanted from anything but an explicit argument — see operator.py's own route for the one
platform-admin caller today, and never let a shop-scoped route omit `tenant`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.models import COST_LEDGER

# A CEILING, NOT A HARD LIMIT ON REALITY — bounds one read's own cost. If the platform ever
# genuinely produces more than this many LLM calls in the requested window, the report says so
# (`truncated`) rather than silently averaging over a partial, unmarked sample.
_MAX_ROWS = 50_000


@dataclass(frozen=True)
class UsageReport:
    days: int
    ai_enabled: bool           # AI_ASSISTANT_ENABLED at read time — see report()'s own note. When
                                # False every field below is None/False, NEVER a stale or zero
                                # number a caller could mistake for "genuinely zero conversations".
    calls: int | None                 # real LLM calls = real assistant replies sent
    conversations: int | None         # distinct subject_ref seen in the window
    input_tokens: int | None
    output_tokens: int | None
    truncated: bool            # _MAX_ROWS was hit — the numbers below are a floor, not exact

    @property
    def avg_input_tokens_per_call(self) -> float | None:
        if self.calls is None:
            return None
        return round(self.input_tokens / self.calls, 1) if self.calls else 0.0

    @property
    def avg_output_tokens_per_call(self) -> float | None:
        if self.calls is None:
            return None
        return round(self.output_tokens / self.calls, 1) if self.calls else 0.0

    @property
    def avg_calls_per_conversation(self) -> float | None:
        if self.calls is None:
            return None
        return round(self.calls / self.conversations, 1) if self.conversations else 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "days": self.days, "ai_enabled": self.ai_enabled,
            "calls": self.calls, "conversations": self.conversations,
            "input_tokens": self.input_tokens, "output_tokens": self.output_tokens,
            "avg_input_tokens_per_call": self.avg_input_tokens_per_call,
            "avg_output_tokens_per_call": self.avg_output_tokens_per_call,
            "avg_calls_per_conversation": self.avg_calls_per_conversation,
            "truncated": self.truncated,
        }


async def report(store: Any, *, days: int, now: int, tenant: str | None = None,
                 ai_enabled: bool = True) -> UsageReport:
    """Real calls/conversations/tokens over the trailing `days`, straight off COST_LEDGER.

    `find()` on this port needs a non-empty membership `where` (never a `>=`/`<=` range, and never
    "everything") — `scan_all` is what reads a whole collection, so this scans up to `_MAX_ROWS`
    rows and filters the window in Python. Fine at this collection's real size (one row per LLM
    call, not per message-character): a busy platform doing thousands of conversations a day is
    still a small fraction of `_MAX_ROWS` over 30 days; the day it is not, `truncated` says so
    rather than quietly answering with a stale-looking accurate number.

    `tenant=None` keeps the platform-wide aggregate (this module's own docstring). A real value
    filters to that one shop's own rows BEFORE the window/truncation math below, so `truncated`
    still means what it says for whichever scope was actually asked for.

    `ai_enabled=False` (config.py::AI_ASSISTANT_ENABLED, the platform kill switch) skips the
    COST_LEDGER read ENTIRELY — not "read then hide": once the switch is off this collection stops
    growing, so every number here would freeze at whatever it was the moment it flipped, which a
    caller could easily mistake for a genuine (accurate, current) answer. Every caller of this
    module must pass the real switch value explicitly — there is no way to ask this module for the
    switch's own state, by design (see config.py for the one place that owns it)."""
    if not ai_enabled:
        return UsageReport(days=days, ai_enabled=False, calls=None, conversations=None,
                           input_tokens=None, output_tokens=None, truncated=False)

    since = now - days * 86_400
    rows = await store.scan_all(COST_LEDGER, limit=_MAX_ROWS)
    scoped = rows if tenant is None else [r for r in (rows or []) if r.get("tenant") == tenant]
    windowed = [r for r in (scoped or []) if int(r.get("at") or 0) >= since]

    calls = len(windowed)
    conversations = len({r.get("subject_ref") for r in windowed if r.get("subject_ref")})
    input_tokens = sum(int(r.get("input_tokens") or 0) for r in windowed)
    output_tokens = sum(int(r.get("output_tokens") or 0) for r in windowed)

    return UsageReport(
        days=days, ai_enabled=True, calls=calls, conversations=conversations,
        input_tokens=input_tokens, output_tokens=output_tokens,
        truncated=len(rows or []) >= _MAX_ROWS)
