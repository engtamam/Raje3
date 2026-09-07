"""Real usage, aggregated from COST_LEDGER — what the console's pricing calculator reads instead
of a guessed average, when the operator picks "من قيمة النظام" over typing one by hand.

WINDOWED, NOT ALL-TIME. `days` bounds the scan (see `report()`) — an assistant running for a year
should not force this read to walk a year of rows to answer "what does last month look like",
and a recent window is the honest basis for a FORWARD projection anyway (a rate from a year ago
predicts nothing about next month's volume).

PLATFORM-WIDE ON PURPOSE. Same reasoning as pricing_schedule.py and every PRICING_* knob itself:
this is not a per-shop number, it is "how much does running this feature at all currently cost
us across every shop that has it" — the number a pricing DECISION needs.
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
    calls: int                 # real LLM calls = real assistant replies sent
    conversations: int         # distinct subject_ref seen in the window
    input_tokens: int
    output_tokens: int
    truncated: bool            # _MAX_ROWS was hit — the numbers below are a floor, not exact

    @property
    def avg_input_tokens_per_call(self) -> float:
        return round(self.input_tokens / self.calls, 1) if self.calls else 0.0

    @property
    def avg_output_tokens_per_call(self) -> float:
        return round(self.output_tokens / self.calls, 1) if self.calls else 0.0

    @property
    def avg_calls_per_conversation(self) -> float:
        return round(self.calls / self.conversations, 1) if self.conversations else 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "days": self.days, "calls": self.calls, "conversations": self.conversations,
            "input_tokens": self.input_tokens, "output_tokens": self.output_tokens,
            "avg_input_tokens_per_call": self.avg_input_tokens_per_call,
            "avg_output_tokens_per_call": self.avg_output_tokens_per_call,
            "avg_calls_per_conversation": self.avg_calls_per_conversation,
            "truncated": self.truncated,
        }


async def report(store: Any, *, days: int, now: int) -> UsageReport:
    """Real calls/conversations/tokens over the trailing `days`, straight off COST_LEDGER.

    `find()` on this port needs a non-empty membership `where` (never a `>=`/`<=` range, and never
    "everything") — `scan_all` is what reads a whole collection, so this scans up to `_MAX_ROWS`
    rows and filters the window in Python. Fine at this collection's real size (one row per LLM
    call, not per message-character): a busy platform doing thousands of conversations a day is
    still a small fraction of `_MAX_ROWS` over 30 days; the day it is not, `truncated` says so
    rather than quietly answering with a stale-looking accurate number.
    """
    since = now - days * 86_400
    rows = await store.scan_all(COST_LEDGER, limit=_MAX_ROWS)
    windowed = [r for r in (rows or []) if int(r.get("at") or 0) >= since]

    calls = len(windowed)
    conversations = len({r.get("subject_ref") for r in windowed if r.get("subject_ref")})
    input_tokens = sum(int(r.get("input_tokens") or 0) for r in windowed)
    output_tokens = sum(int(r.get("output_tokens") or 0) for r in windowed)

    return UsageReport(
        days=days, calls=calls, conversations=conversations,
        input_tokens=input_tokens, output_tokens=output_tokens,
        truncated=len(rows or []) >= _MAX_ROWS)
