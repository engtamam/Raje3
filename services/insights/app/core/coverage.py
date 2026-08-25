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
# FOUR FIELDS, AND THE FIRST ONE WAS MISSING FOR A YEAR.
#
# The panel used to print `why` alone — «نظام الكاشير لا يرسل الفرع مع العملية» — under a heading
# that said «مؤشرات تحتاج بيانات أكثر». A cause with no consequence and no next step, to somebody
# who never asked the question. The owner's own reading of it was «ماني فاهم».
#
#   lost   WHAT HE CANNOT SEE. The consequence, first, because it is the only part he has a reason
#          to care about. «لا تقدر تقارن فروعك» is a loss; «التغطية دون 40%» is a statistic.
#   why    the cause, in the words of somebody who has never seen our API.
#   do     THE ONE NEXT STEP. Not a list — one sentence, and it is an instruction rather than a
#          description, because a description leaves him deciding whether it was addressed to him.
#   owner  who can actually act. It decides the sentence above, and the screen shows it as a chip
#          so the answer to «is this mine?» arrives before he finishes reading.
#
# `request` IS FOR A STRANGER'S ENGINEER, NOT FOR HIM. It carries our field name, so the screen
# keeps it behind a copy button and never in the body: printed inline it reads as an instruction
# to the owner, and he cannot act on «حقل branch_id» in any way at all.
BLOCKED_REASONS = {
    "branch_comparison": {
        "lost": "لا تقدر تقارن فروعك",
        # SHORT, AND WITH THE NUMBER IN IT — the reading on a shop that had just signed
        # up: «احذفها، ايش هذا الكلام؟ هو مسوي حساب جديد يشوف هذا قدامه! ولازم يعرف الارقام».
        #
        # Two long sentences stood here, explaining our own history to a man on his first day:
        # visits recorded before we knew their branch, and a promise that new ones carry theirs
        # automatically. Both true, neither his business, and neither told him WHEN the indicator
        # opens. The progress below answers that, and the bar draws itself from the same numbers.
        "why": "أكثر زياراتك بلا فرع.",
        "do": "",
        "owner": "time",
        # The text he forwards, KEPT for the one case that still needs somebody else's engineer: a
        # register that refuses to send a branch and therefore has all its sales rejected at the
        # door. He presses copy and sends; he does not have to explain our own field names to a
        # vendor, which is the step that would otherwise never happen.
        "request": "نرجو إرسال branch_id مع كل عملية — صار حقلاً إلزامياً وترفض راجِع العملية بدونه.",
    },
    "staff_performance": {
        "lost": "لا تقدر تعرف إنتاجية كل موظف",
        "why": "الزيارات تُسجَّل بلا اسم من سجّلها، فلا تُنسب إلى أحد.",
        "do": "اطلب من فريقك تسجيل الدخول بحساباتهم قبل تسجيل أي زيارة.",
        "owner": "establishment",
        "request": "",
    },
    "associations": {
        "lost": "لا نعرف بعد ما الذي يُطلب مع ماذا",
        "why": "التعرّف على الاقترانات يحتاج زياراتٍ أكثر ليصير الاستنتاج صحيحاً لا صدفة.",
        "do": "لا شيء عليك — يكتمل وحده مع زيارات محلّك.",
        "owner": "time",
        "request": "",
    },
}

#: Who can act, in his words. Shown as a chip so «هل هذه عليّ أنا؟» is answered before the sentence
#: is finished — and «الوقت» is on the list because «nobody has to do anything» is an answer too,
#: and the most reassuring one.
BLOCKED_OWNER_LABEL = {
    "pos_vendor": "على مزوّد الكاشير",
    "establishment": "عليك أنت",
    "time": "على الوقت",
    "unknown": "غير محدّد",
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
        d = dict(BLOCKED_REASONS.get(indicator) or
                    # AN INDICATOR WE HAVE NO SENTENCE FOR STILL SAYS WHAT IS LOST. The fallback
                    # used to carry `why` alone, so a new indicator would draw a bullet reading
                    # «لا تكفي البيانات» — the exact shape of unhelpfulness this table exists to
                    # end. Whoever adds the indicator adds its three sentences; until then this is
                    # honest about being unspecific rather than pretending to be a cause.
                    {"lost": "مؤشّر لا يعمل بعد",
                     "why": "لا تكفي البيانات المسجّلة حتى الآن.",
                     "do": "", "owner": "unknown", "request": ""})
        # THE NUMBER, BECAUSE «قريباً» IS NOT AN ANSWER. `have` is what already carries the field,
        # and `need` is where the indicator opens — the same 40% this branch is decided by, so the
        # bar and the rule cannot drift apart. Told «60 من 100» he knows both that it is coming and
        # roughly when; told a sentence, he knows neither.
        d["progress"] = {"have": coverage.known, "need": -(-coverage.total * 2 // 5)}
        return d
    return None
