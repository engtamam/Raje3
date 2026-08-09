"""The estimate the owner sees before he presses send — and when we refuse to give him one."""
from __future__ import annotations

from app.core.share import compute
from app.core.spread import plan, sentence

FALLBACK = 200


def estimate(*, audience: int, ceiling: int, reserved: int, used: int,
             expires_at: int = 0, now: int = 0):
    """The whole chain the preview runs: share, then plan, then the sentence."""
    share = compute(ceiling=ceiling, reserved=reserved, used=used, fallback=FALLBACK)
    if not share.known:
        return None, ""
    p = plan(audience=audience, available_per_day=share.per_day,
             expires_at=expires_at, now=now)
    return p, sentence(p)


def test_he_is_told_the_days_when_the_ceiling_is_known():
    p, says = estimate(audience=10_000, ceiling=2500, reserved=400, used=100)
    assert p.days == 5 and "5" in says


def test_the_reserve_lengthens_the_campaign_rather_than_silencing_the_shop():
    """The engine's share is not the campaign's to spend. Taking it would finish sooner and leave
    the customer who walks in this evening with no confirmation."""
    without = estimate(audience=10_000, ceiling=2500, reserved=0, used=0)[0].days
    with_reserve = estimate(audience=10_000, ceiling=2500, reserved=1500, used=0)[0].days
    assert with_reserve > without


def test_what_the_engine_already_spent_today_counts_too():
    """Reserving 400 on a ceiling of 2,500 leaves 2,100 only at midnight."""
    morning = estimate(audience=10_000, ceiling=2500, reserved=400, used=0)[0]
    evening = estimate(audience=10_000, ceiling=2500, reserved=400, used=1800)[0]
    assert evening.days > morning.days


def test_no_estimate_at_all_when_the_ceiling_is_unknown():
    """A promise made on a guess is worse than no promise: he plans around it, and we are the
    reason he was wrong."""
    p, says = estimate(audience=10_000, ceiling=0, reserved=400, used=100)
    assert p is None and says == ""


def test_an_expiring_offer_is_refused_at_the_preview_not_on_day_four():
    p, says = estimate(audience=10_000, ceiling=2500, reserved=500, used=0,
                       expires_at=200 * 86400, now=198 * 86400)
    assert not p.ok and "صغّر" in says and "مدّد" in says
