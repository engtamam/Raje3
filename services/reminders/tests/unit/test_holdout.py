"""proof 2 — the measurement group, and the four ways a holdout stops being one."""
from app.core import gate as G
from app.core import holdout as H
from app.core import engagement as E

NOW = 1_800_000_000


def _decide(cls: str, subject: str, *, enabled: bool = True) -> G.Decision:
    return G.evaluate(
        cls=cls, template_type="t", now=NOW, limits=G.Limits(),
        prefs_stopped={}, engagement_score=100.0, engagement_at=NOW,
        recent_sends=[], eng_cfg=E.EngagementConfig(),
        marketing_consent="granted",
        tenant="shop-1", subject_ref=subject,
        holdout_enabled=enabled, holdout_share=10,
    )


def _in_holdout(prefix: str = "c", n: int = 400) -> str:
    return next(f"{prefix}{i}" for i in range(n) if H.is_holdout("shop-1", f"{prefix}{i}"))


def test_membership_never_moves():
    """The one failure that destroys the comparison silently: a customer who changes group.

    Python's built-in hash is salted per process, so a bucket built on it would reshuffle on every
    restart — six months of messages, then none, counted as evidence that silence works.
    """
    who = _in_holdout()
    assert all(H.is_holdout("shop-1", who) for _ in range(50))
    assert H.bucket("shop-1", who) == H.bucket("shop-1", who)


def test_the_same_person_is_not_held_out_at_every_shop():
    who = _in_holdout()
    others = [H.is_holdout(f"shop-{i}", who) for i in range(2, 40)]
    assert not all(others), "the tenant must be inside the hash"


def test_a_receipt_still_reaches_the_holdout():
    """Withholding a visit confirmation would make the group a worse experience, not a quieter one —
    and the comparison is supposed to be about the ENGINE."""
    who = _in_holdout()
    assert _decide("service", who).allowed is True
    assert _decide("personal", who).allowed is True


def test_the_engine_is_withheld_and_says_why():
    who = _in_holdout()
    d = _decide("marketing", who)
    assert d.allowed is False
    assert "مجموعة القياس" in d.reason
    assert d.details.get("holdout") is True


def test_switching_it_off_merges_the_groups():
    who = _in_holdout()
    assert _decide("marketing", who, enabled=False).allowed is True


def test_roughly_a_tenth_and_not_a_third():
    held = sum(1 for i in range(3000) if H.is_holdout("shop-1", f"c{i}"))
    assert 200 <= held <= 400, held
