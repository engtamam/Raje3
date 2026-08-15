"""The middle screen — where an owner decides in four seconds."""
from __future__ import annotations

import pytest

from app.core.audience import Audience, Candidate
from app.core.preview import (PreviewError, build, describe_when, render_message,
                              sanitise_owner_text)

TEMPLATE = {"name": "mkt_winback_brief", "type": "mkt_winback", "class": "marketing",
            "body": "أهلاً {{1}}، لك {{3}} في زيارتك القادمة لـ{{2}}.",
            "variables": [1, 2, 3], "fills": ["system", "system", "owner"]}

NO_OWNER_FIELD = {"name": "mkt_announcement_brief", "type": "mkt_announcement",
                  "body": "أهلاً {{1}}، جديد في {{2}}: {{3}}.",
                  "variables": [1, 2, 3], "fills": ["system", "system", "catalogue"]}


def audience(n=3, excluded=0, truncated=False, why="آخر زيارة قبل 94 يوماً"):
    a = Audience(candidates=[Candidate(subject_ref=f"s{i}", why=why) for i in range(n)],
                 excluded=excluded)
    a.truncated = truncated
    return a


def preview(**kw):
    d = dict(goal="win_back", template=TEMPLATE, establishment="ورشة النخبة",
             owner_text="خصم 20%", audience=audience(), when="تُرسَل الآن.")
    d.update(kw)
    return build(**d)


# ── the message, as it will actually arrive ────────────────────────────────────────────────────
def test_the_message_is_rendered_not_described():
    """An owner who sees {{1}} does not know what their customer will see, so they either send
    blind or do not send."""
# arabic-indic-digits: intentional — fed in as a value the preview must refuse.
    p = preview()
    assert "{{" not in p.message
    assert "ورشة النخبة" in p.message and "خصم 20%" in p.message


def test_the_name_uses_the_same_fallback_the_send_uses():
    """Showing [name] would let an owner approve a message whose real form they never saw."""
    assert "عميلنا العزيز" in preview().message


def test_an_unknowable_system_value_reads_as_a_shape_not_as_braces():
    """The owner is judging the SHAPE of the message, and braces are not a shape."""
    t = dict(TEMPLATE, body="أهلاً {{1}}، عرضك {{3}} ساري حتى {{4}}.",
             variables=[1, 2, 3, 4], fills=["system", "system", "owner", "system"])
    out = render_message(template=t, establishment="x", owner_text="خصم")
    assert "{{4}}" not in out and "…" in out


# ── the number ─────────────────────────────────────────────────────────────────────────────────
def test_the_count_is_people_and_comes_from_the_resolver():
    p = preview(audience=audience(47))
    assert p.reaches == 47


def test_everyone_the_gate_would_refuse_is_already_out_of_the_count():
    """A preview that promises 47 and delivers 31 does not teach an owner about caps — it teaches
    them our numbers are decoration, and after that they check nothing we show."""
    p = preview(audience=audience(43, excluded=4))
    assert p.reaches == 43 and p.excluded == 4


def test_a_truncated_audience_is_surfaced():
    assert preview(audience=audience(3, truncated=True)).truncated


def test_three_examples_explain_the_rule_better_than_a_sentence():
    p = preview(audience=audience(9))
    assert len(p.samples) == 3 and "94" in p.samples[0]


# ── the owner's text, refused while they can still fix it ──────────────────────────────────────
@pytest.mark.parametrize("bad", [
    "خصم على https://evil.example", "زورونا على www.example.com",
    "تفاصيل على example.com", "اتصل 0501234567", "عرض\nجديد", "عرض​خفي",
])
def test_nothing_can_be_smuggled_into_an_approved_template(bad):
    with pytest.raises(PreviewError):
        preview(owner_text=bad)


def test_the_refusal_happens_on_the_screen_not_at_send_time():
    """Refusing later would mean a campaign the owner believed was scheduled quietly failing."""
    with pytest.raises(PreviewError) as exc:
        preview(owner_text="عرض على example.com")
    assert "رابط" in str(exc.value)


def test_an_empty_text_is_refused_only_when_the_template_needs_one():
    with pytest.raises(PreviewError):
        preview(owner_text="")
    p = preview(template=NO_OWNER_FIELD, owner_text="")
    assert p.message and "{{" not in p.message


def test_an_overlong_text_is_refused_with_the_limit_in_the_message():
    with pytest.raises(PreviewError) as exc:
        preview(owner_text="أ" * 200)
    assert "60" in str(exc.value)


def test_ordinary_arabic_passes_untouched():
    assert sanitise_owner_text("  خصم 20% على غيار الزيت  ", required=True) == \
        "خصم 20% على غيار الزيت"


# ── what will actually happen ──────────────────────────────────────────────────────────────────
def test_outside_the_window_the_owner_is_told_before_pressing_send():
    """'Sends tomorrow at 9am' is a thing an owner may want to change their mind about, and
    learning it afterwards is learning it too late."""
    s = describe_when(trigger="manual", inside_window=False)
    assert "غداً" in s and "خارج وقت الإرسال" in s


def test_a_standing_campaign_says_it_runs_daily():
    assert "كل يوم" in describe_when(trigger="standing", inside_window=True)


def test_inside_the_window_it_simply_sends_now():
    assert describe_when(trigger="manual", inside_window=True) == "تُرسَل الآن."


# ── the guarantee that keeps the two numbers equal ─────────────────────────────────────────────
def test_the_preview_does_not_compute_its_own_audience():
    """One implementation, not two that agree today. The preview takes the audience the send
    resolver produced — it cannot drift from it because it never derives it."""
    import inspect

    from app.core import preview as mod
    src = inspect.getsource(mod.build)
    assert "resolve(" not in src
    assert "audience.count" in src


# ── the discount, typed ────────────────────────────────────────────────────────────────────────
from app.core.preview import sanitise_offer_value   # noqa: E402


@pytest.mark.parametrize("good", ["20%", "5%", "90%", "50 ريال", "12.50 ريال"])
def test_a_discount_that_can_be_honoured_is_accepted(good):
    assert sanitise_offer_value(good, required=True) == good


@pytest.mark.parametrize("bad", ["خصم كبير", "٢٠٪", "20 %", "120%", "0%", "50 ريال فقط", "50"])
def test_a_discount_that_is_not_a_number_never_reaches_a_customer(bad):
    """«خصم كبير» promises nothing anybody can be held to, and Arabic-Indic digits are unreadable
    on half the phones in this market. Refused while he is looking at the field."""
    with pytest.raises(PreviewError):
        sanitise_offer_value(bad, required=True)


def test_a_goal_with_nowhere_to_put_a_discount_does_not_demand_one():
    """«أعلن جديدك» promises nothing — refusing it for a missing discount would be refusing a
    field it has no slot for."""
    assert sanitise_offer_value("", required=False) == ""
    with pytest.raises(PreviewError):
        sanitise_offer_value("", required=True)
