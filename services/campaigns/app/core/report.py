"""What happened — transparency instead of options (spec §10.9).

"IT DIDN'T ARRIVE" IS THE ONLY COMPLAINT THIS PRODUCT GENERATES, and this is the only place it can
be answered. Everywhere else shows what happened; a campaign report has to show what DIDN'T, with
the reason, or every rule we wrote becomes a suspected bug in the owner's mind.

The shape is one sentence, in their words:

    وصلت 43، وتأجّلت 3 لبلوغ الحد اليومي، وامتنعت 1 لأن العميل أوقف الدعائية

Not a table of codes, not a percentage, and not "delivery rate: 91.5%". A rate hides the three
customers whose messages were held; the sentence names them as a number the owner can act on.

PER RUN, NEVER AGGREGATED, for a standing campaign. An owner asking why it reached nobody last
Tuesday needs Tuesday — an average across forty runs answers a question they did not ask and hides
the one they did.

AND THE REASONS ARE THE GATE'S OWN WORDS. They arrive from reminders verbatim and are shown
verbatim. Translating them here would give the same refusal two vocabularies, and the owner reading
this would be told something subtly different from what actually happened.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RunReport:
    at: int
    matched: int
    sent: int
    suppressed: int
    failed: int
    reasons: dict[str, int] = field(default_factory=dict)
    fired_by: str = "system"
    # The one sentence. Built here rather than in the console so every surface says the same
    # thing — a screen that composes its own wording is a screen that drifts from the API.
    summary: str = ""


def build(run: dict[str, Any]) -> RunReport:
    matched = int(run.get("matched") or 0)
    sent = int(run.get("sent") or 0)
    suppressed = int(run.get("suppressed") or 0)
    failed = int(run.get("failed") or 0)
    reasons = dict(run.get("reasons") or {})

    return RunReport(
        at=int(run.get("at") or 0), matched=matched, sent=sent,
        suppressed=suppressed, failed=failed, reasons=reasons,
        fired_by=str(run.get("fired_by") or "system"),
        summary=summarise(sent=sent, suppressed=suppressed, failed=failed, reasons=reasons))


def summarise(*, sent: int, suppressed: int, failed: int,
              reasons: dict[str, int]) -> str:
    """One sentence an owner reads without deciding to.

    NAMES THE TOP REASONS RATHER THAN ALL OF THEM. A sentence listing nine causes is a paragraph,
    and a paragraph on a summary line is not read — the two largest explain almost every run, and
    the rest are one tap away.
    """
    if sent == 0 and suppressed == 0 and failed == 0:
        # A REAL ANSWER, not an empty state. "Nobody matched" is information — it means the rule
        # found nobody, which is different from a run that did not happen.
        return "لم تنطبق على أحد هذه المرة."

    parts = [f"وصلت {sent}"]
    if suppressed:
        top = sorted(reasons.items(), key=lambda kv: -kv[1])[:2]
        named = "، و".join(f"{n} {_reason_phrase(r)}" for r, n in top if n)
        parts.append(f"وامتنعت {suppressed}" + (f" — {named}" if named else ""))
    if failed:
        parts.append(f"وتعذّرت {failed}")
    return "، ".join(parts) + "."


def _reason_phrase(reason: str) -> str:
    """The gate's sentence, shortened for a summary line but never rewritten.

    Truncation only — no paraphrase. A reason the owner reads here must match the reason in the
    detail view word for word, or they will believe they are two different problems.
    """
    r = reason.strip()
    return r if len(r) <= 42 else r[:41] + "…"


def history(runs: list[dict[str, Any]], *, limit: int = 30) -> list[RunReport]:
    """A standing campaign's runs, newest first.

    NOT AGGREGATED. Forty runs are forty questions, and an average answers none of them — the
    owner asking about last Tuesday needs Tuesday's row.
    """
    ordered = sorted(runs, key=lambda r: int(r.get("at") or 0), reverse=True)
    return [build(r) for r in ordered[:limit]]


def totals(runs: list[dict[str, Any]]) -> dict[str, int]:
    """The lifetime numbers, for the one place a total is the right answer: the card that says
    'this campaign has brought back 61 customers'. Kept separate from `history` so nobody is
    tempted to render a total where a run belongs."""
    out = {"runs": len(runs), "matched": 0, "sent": 0, "suppressed": 0, "failed": 0}
    for r in runs:
        for k in ("matched", "sent", "suppressed", "failed"):
            out[k] += int(r.get(k) or 0)
    return out
