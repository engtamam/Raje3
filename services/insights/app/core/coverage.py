"""When a field does not arrive — show the gap, and silence only the claim (spec §10.6.3).

Branch and operator are optional. A till may never send a branch; employees may not sign in. So an
indicator built on them is computed over part of the data, and the question is what to do about the
part that is missing.

HIDING THE INDICATOR IS THE WRONG ANSWER, and it was my first one. It denies the owner sight of the
problem: he cannot ask his POS vendor for a field he does not know is missing. So "غير محدَّد" is a
FULL ROW in the table, never a footnote under it — and that row is itself the request.

WHAT THE MISSING DATA SILENCES IS THE CLAIM, NOT THE TABLE.

    الرياض – شمال   340
    جدة – جنوب      280
    غير محدَّد       380

Every number there is true. But "Riyadh is your busiest branch" is FALSE if those 380 were Jeddah's
— and it is the sentence, not the table, that would mislead him. So the table always renders and
the superlative renders only when the unknown cannot overturn it:

    unknown < (first − second)

An arithmetic rule rather than a percentage somebody chose. A 70%-coverage table with a runaway
leader ranks honestly; a 95%-coverage table with two branches neck and neck does not, and any
fixed threshold gets exactly one of those two wrong.
"""
from __future__ import annotations

from typing import Any

from app.core.models import Coverage

UNKNOWN = "_unknown"


def group_by(rows: list[dict], field: str, *, value: str = "") -> dict[str, Any]:
    """Group rows by an optional field, keeping the unknowns as a first-class bucket.

    `value` names a numeric field to sum instead of counting rows — one function for "how many
    visits per branch" and "how much revenue per branch", because two would drift.
    """
    buckets: dict[str, int] = {}
    for r in rows:
        key = str(r.get(field) or "") or UNKNOWN
        buckets[key] = buckets.get(key, 0) + (int(r.get(value) or 0) if value else 1)

    known = sum(n for k, n in buckets.items() if k != UNKNOWN)
    total = sum(buckets.values())
    cov = Coverage(total=total, known=known)

    ordered = sorted(((k, n) for k, n in buckets.items() if k != UNKNOWN),
                     key=lambda kv: -kv[1])
    return {
        # The unknown row is NOT appended here — the caller renders it distinctly, with its cause.
        # Folding it in as just another bucket would let it be sorted into first place and read as
        # a branch called "unspecified", which is worse than not showing it at all.
        "rows": [{"key": k, "count": n} for k, n in ordered],
        "unknown": buckets.get(UNKNOWN, 0),
        "coverage": cov.to_dict(),
        "can_rank": can_rank(ordered, buckets.get(UNKNOWN, 0)),
    }


def can_rank(ordered: list[tuple[str, int]], unknown: int) -> bool:
    """May we say "the busiest"? Only if the unknown bucket cannot overturn it.

    A single known bucket cannot be ranked either: "your busiest branch is your only branch" is
    not a finding, and with an unknown bucket present it may not even be true.
    """
    if len(ordered) < 2:
        return False
    return unknown < (ordered[0][1] - ordered[1][1])


# ── the list of what cannot run yet, and who owns the fix ─────────────────────────────────────
# Each entry names the cause in the owner's words and WHO can act — because "branch comparison
# unavailable" tells him nothing, while "your POS does not send the branch" tells him whom to ask.
BLOCKED_REASONS = {
    "branch_comparison": {
        "why": "نظام الكاشير لا يرسل الفرع مع العملية",
        "owner": "pos_vendor",
        # The text he forwards. He presses copy and sends; he does not have to explain our API to
        # somebody else's engineer, which is the step that would otherwise never happen.
        "request": "نرجو إرسال حقل branch_id مع كل عملية في طلب تسجيل الزيارة.",
    },
    "staff_performance": {
        "why": "الموظفون لا يسجّلون دخولهم، فالعمليات غير منسوبة",
        "owner": "establishment",
        "request": "",
    },
    "associations": {
        "why": "لم تكتمل بيانات التعلّم بعد",
        "owner": "time",
        "request": "",
    },
}


def blocked(indicator: str, *, coverage: Coverage | None = None,
            learning: dict | None = None) -> dict[str, Any] | None:
    """Why this indicator is not showing, or None when it is fine.

    Returns the progress for the learning case so the panel can render a bar rather than a
    sentence: "after about 200 visits" with no sense of how close he is reads as indefinite, and
    indefinite reads as never.
    """
    if learning and learning.get("learning"):
        d = dict(BLOCKED_REASONS["associations"])
        d["progress"] = {"have": learning.get("have", 0), "need": learning.get("need", 0)}
        return d
    if coverage is not None and coverage.total and coverage.ratio < 0.4:
        return dict(BLOCKED_REASONS.get(indicator) or
                    {"why": "لا تكفي البيانات", "owner": "unknown", "request": ""})
    return None
