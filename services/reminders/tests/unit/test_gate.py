"""The sending gate — one test per rule in spec 8.4.2, and one per way it could be wrong."""
from __future__ import annotations

from datetime import datetime

from app.core import engagement as E
from app.core import gate as G

LIM = G.Limits()
ECFG = E.EngagementConfig()


def at(hour: int, minute: int = 0, day: int = 15) -> int:
    """An epoch for a given RIYADH wall-clock time — the only clock this gate reasons about."""
    return int(datetime(2026, 6, day, hour, minute, tzinfo=G.RIYADH).timestamp())


def ev(**over):
    d = dict(cls="service", template_type="svc_service_reminder", now=at(10), limits=LIM,
             prefs_stopped={}, engagement_score=20.0, engagement_at=at(10), recent_sends=[],
             eng_cfg=ECFG)
    d.update(over)
    return G.evaluate(**d)


def sent(cls, when, outcome="sent"):
    return {"cls": cls, "at": when, "outcome": outcome}


# ── 1. the customer's own stop ─────────────────────────────────────────────────────────────────
def test_an_explicit_stop_outranks_everything_including_personal():
    """Someone who switched everything off has said what they want, and keeping a channel open
    over their objection is not a service to them (spec 8.4.2 section 5)."""
    for cls in ("service", "personal", "marketing", "awareness"):
        d = ev(cls=cls, template_type="per_account_notice", prefs_stopped={cls: True})
        assert not d.allowed and "أوقف" in d.reason


def test_stopping_one_class_does_not_stop_the_others():
    assert ev(cls="service", prefs_stopped={"marketing": True}).allowed


# ── 2. a class with no templates ───────────────────────────────────────────────────────────────
def test_a_class_with_no_templates_is_refused_legibly_here():
    """Otherwise it fails deep in the sender with a template lookup error — cryptic there."""
    d = ev(cls="warning", class_enabled=False)
    assert not d.allowed and "غير مفعّل" in d.reason


# ── 3. engagement ──────────────────────────────────────────────────────────────────────────────
def test_a_lapsed_customer_still_gets_service_messages():
    d = ev(cls="service", engagement_score=0.1, engagement_at=at(10, day=1))
    assert d.allowed and d.tier == E.TIER_MINIMAL


def test_a_lapsed_customer_gets_no_marketing_and_is_told_why():
    d = ev(cls="marketing", template_type="mkt_offer", engagement_score=0.0, engagement_at=1)
    assert not d.allowed and "زيارة واحدة تعيد كل شيء" in d.reason


# ── 4. the window ──────────────────────────────────────────────────────────────────────────────
def test_a_reminder_at_eleven_at_night_is_deferred_to_the_morning():
    d = ev(now=at(23))
    assert not d.allowed and d.retry_at > 0
    assert datetime.fromtimestamp(d.retry_at, G.RIYADH).hour == 7


def test_a_visit_confirmation_at_eleven_at_night_goes_out_now():
    """A reply to something the customer just did. After eight hours of silence it stops being a
    confirmation and becomes a message from a shop that is closed (spec 8.4.2 section 1)."""
    assert ev(now=at(23), template_type="svc_visit_confirmation").allowed
    assert ev(now=at(23), template_type="svc_receipt").allowed


def test_a_reminder_is_not_exempt_just_because_it_is_service_class():
    """The exemption is by template type, not by class: a reminder is ours, sent on our schedule,
    and it waits for the morning."""
    assert not ev(now=at(23), template_type="svc_service_reminder").allowed


def test_marketing_outside_the_window_is_dropped_not_deferred():
    """A weekend offer arriving on Tuesday is worse than no offer (spec 5.8)."""
    d = ev(cls="marketing", template_type="mkt_offer", now=at(23))
    assert not d.allowed and d.retry_at == 0 and "يُسقَط" in d.reason


def test_the_window_is_computed_in_riyadh_not_utc():
    """The classic timezone bug, and here it means messages at 4am to real people. 6am Riyadh is
    3am UTC — inside the window on a UTC clock, outside it on the right one."""
    assert not ev(now=at(6)).allowed
    assert ev(now=at(8)).allowed


# ── 5. the caps ────────────────────────────────────────────────────────────────────────────────
def test_the_daily_service_cap_holds():
    d = ev(recent_sends=[sent("service", at(9))])
    assert not d.allowed and "الحد اليومي" in d.reason


def test_a_suppressed_row_does_not_consume_the_cap():
    """Otherwise a customer who was refused yesterday is refused again today for having been
    refused — the cap counts what we SENT."""
    assert ev(recent_sends=[sent("service", at(9), outcome="suppressed")]).allowed


def test_the_absolute_daily_ceiling_catches_what_the_per_class_caps_let_through():
    """Four separate caps can each be satisfied while their sum is five messages in a day."""
    d = ev(cls="awareness", template_type="awr_care_tip",
           recent_sends=[sent("service", at(9)), sent("marketing", at(8))])
    assert not d.allowed and "الحد اليومي" in d.reason


def test_personal_messages_are_neither_counted_nor_capped():
    """A points-expiry notice held back by a cap arrives after the points expired."""
    d = ev(cls="personal", template_type="per_points_expiring",
           recent_sends=[sent("service", at(9)), sent("marketing", at(8))])
    assert d.allowed


def test_the_monthly_marketing_cap_holds():
    sends = [sent("marketing", at(10, day=d)) for d in (1, 3, 6, 9)]
    d = ev(cls="marketing", template_type="mkt_offer", recent_sends=sends)
    assert not d.allowed and "الحد الشهري" in d.reason


def test_a_quiet_customer_gets_half_the_marketing_and_is_told_so():
    sends = [sent("marketing", at(10, day=d)) for d in (1, 3)]
    d = ev(cls="marketing", template_type="mkt_offer", recent_sends=sends,
           engagement_score=2.0, engagement_at=at(10))
    assert not d.allowed and "نصف الحد" in d.reason


def test_the_marketing_cooldown_holds_and_says_when():
    d = ev(cls="marketing", template_type="mkt_offer",
           recent_sends=[sent("marketing", at(10, day=14))])
    assert not d.allowed and d.retry_at > at(10) and "72 ساعة" in d.reason


def test_marketing_after_the_cooldown_goes_out():
    assert ev(cls="marketing", template_type="mkt_offer",
              recent_sends=[sent("marketing", at(10, day=10))]).allowed


# ── the ladder ─────────────────────────────────────────────────────────────────────────────────
def test_the_priority_ladder_is_the_one_in_the_spec():
    assert [G.priority(c) for c in ("warning", "personal", "service", "awareness", "marketing")] \
        == [0, 1, 2, 3, 4]


def test_every_refusal_carries_a_reason():
    """'Not sent' is unanswerable, and it is the only question support ever gets about this
    service."""
    for kw in (dict(prefs_stopped={"service": True}), dict(now=at(23)),
               dict(recent_sends=[sent("service", at(9))]), dict(class_enabled=False)):
        d = ev(**kw)
        assert not d.allowed and len(d.reason) > 20


# ── the boot guards: a setting that silently disables the control it looks like it sets ─────────
import pytest

from app.config import Settings


def _s(**over):
    base = dict(ENV="production", INTERNAL_SERVICE_TOKEN="x" * 40,
                SENDER_DRIVER="http", NOTIFICATION_SERVICE_URL="http://n:8000",
                OPERATIONS_SERVICE_URL="http://o:8000")
    base.update(over)
    return Settings(**base)


def test_production_refuses_a_sender_that_sends_nothing():
    """Visits record, schedules are created, the tick runs green, the log fills with rows marked
    sent — and no customer receives anything. Every dashboard says the product works."""
    with pytest.raises(ValueError, match="not one message"):
        _s(SENDER_DRIVER="null").assert_sender_config_ok()


def test_production_refuses_http_without_the_recipient_resolver():
    """This service holds no phone numbers by design; without the resolver every send fails with
    no destination, and it looks like a notification-service outage."""
    with pytest.raises(ValueError, match="OPERATIONS_SERVICE_URL"):
        _s(OPERATIONS_SERVICE_URL="").assert_sender_config_ok()


def test_a_window_that_is_not_a_window_is_refused():
    """0-24 is not a generous setting — it is the absence of the control in the shape of one."""
    with pytest.raises(ValueError):
        _s(SEND_WINDOW_START_HOUR=0, SEND_WINDOW_END_HOUR=24).assert_caps_sane()


def test_an_absurd_cap_is_refused():
    with pytest.raises(ValueError, match="absence of a cap"):
        _s(MONTHLY_MARKETING_CAP=999).assert_caps_sane()


def test_the_real_defaults_pass_their_own_guards():
    s = _s()
    s.assert_sender_config_ok()
    s.assert_caps_sane()
