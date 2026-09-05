"""The rating app's own call-to-action line — a whole sentence, never a template-level condition.

WHATSAPP REFUSES AN EMPTY TEMPLATE VARIABLE, same rule `core/invite.py` is built around: a shop
with no participation points configured must get a full, different sentence here, never a blank
and never the points sentence with a zero written into it.

BASED ON RESEARCH ON RATING-REQUEST WORDING (see rating-app-feature.md's phase-3 discussion): the
incentive line is phrased as a reward for PARTICIPATING, never for a specific (positive) rating —
wording it around the star value itself would bias what comes back, which is worse data than
having none.
"""
from __future__ import annotations

NO_POINTS = "نحب نسمع رأيك بزيارتك اليوم"


def line(points: int) -> str:
    """`points` — the shop's own configured reward for answering (0 = disabled/not configured).
    Never negative in practice (rating_settings.py's own bound), but treated the same as zero here
    regardless — a whole sentence either way, never a number close to but not quite right."""
    if points > 0:
        return f"شاركنا رأيك بزيارتك واكسب {points} نقطة"
    return NO_POINTS
