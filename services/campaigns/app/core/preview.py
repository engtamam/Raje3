"""The middle screen — the real message, and a count of people (spec §10.9).

THIS IS THE SCREEN THE WHOLE FEATURE RESTS ON. The first screen is four cards; the third is a
confirmation. This one is where an owner decides whether to send something to hundreds of their
customers under their own name, and they decide in about four seconds.

TWO THINGS ON IT, AND NOTHING ELSE:

  The message, exactly as it will arrive on a phone — the template rendered with real values, not
  a summary of it and not the template with braces showing. An owner who sees `{{1}}` does not
  know what their customer will see, so they either send blind or do not send.

  One line under it: "reaches 47 customers". Not a percentage, not a chart, not the word
  "segment". A count of PEOPLE is the element someone who reads poorly still understands, and it
  is the number they are actually deciding about.

THE COUNT MUST BE THE TRUTH. It comes from the same resolver the send uses, with the gate already
applied — so everyone who would be refused is already out of it. A preview that promises 47 and
delivers 31 does not teach the owner about caps; it teaches them our numbers are decoration, and
after that they check nothing we show them.

AND THE OWNER'S TEXT IS SANITISED HERE, at the point they can still fix it. Refusing at send time
would mean a campaign they believed was scheduled quietly failing — the refusal has to happen while
they are looking at the screen.
"""
# arabic-indic-digits: intentional — named in a refusal message, as the shape we do NOT accept.
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# The same rules reminders applies (spec Appendix A): a free variable inside an approved template
# is an injection channel that goes out under the ESTABLISHMENT'S name and counts against OUR
# quality rating at Meta.
_URL = re.compile(r"(https?://|www\.|\b[a-z0-9-]+\.(com|net|org|sa|io|co)\b)", re.I)
_PHONE = re.compile(r"(?:\+?\d[\s-]?){7,}")
_CONTROL = re.compile(r"[\x00-\x1f\x7f​-‏‪-‮]")

MAX_OWNER_TEXT = 60

# ── the discount, TYPED ────────────────────────────────────────────────────────────────────────
# «20%» or «50 ريال», and nothing else. It used to live inside the owner's one free line, which
# meant «خصم كبير» (a promise nobody can be held to), «٢٠٪» in digits half the phones our
# customers hold render badly, or an offer that never named a number at all. The same shape the
# send validates (reminders/core/rendering.py) — checked here so he learns while looking at it.
#
# THAT LAST SENTENCE USED TO BE THE ONLY THING KEEPING THE TWO EQUAL, which is to say nothing was.
# The two are read at different moments — this one while he types, that one at the send — so if
# this copy is ever the looser of the two he is told the campaign launched and not one message
# renders. `ci/check_the_offer_a_shop_types_is_judged_the_same_everywhere.py` now compares them on
# every push: edit one and CI names the other.
REWARD_KINDS = ("percent", "fixed_halalas")


def format_discount_text(*, reward_kind: str, reward_amount: int) -> str:
    """"20%" or "50.00 ريال" — the DISPLAY text composed FROM the structured fields, the reverse
    of what the old free-text `offer_value` sanitiser used to do (parse display text and hope it
    was a number). This is the only place that turns the stored integer back into the sentence a
    customer reads."""
    if reward_kind == "percent":
        return f"{reward_amount}%"
    if reward_kind == "fixed_halalas":
        return f"{reward_amount / 100:.2f} ريال"
    return ""


def validate_discount_amount(*, reward_kind: str, reward_amount: int, required: bool) -> str:
    """Raise the same refusal `models.validate_reward` would, while he is still looking at the
    preview screen — same "refused at write time" posture the old string sanitiser had, now
    against an integer instead of a string shape. Returns the formatted display text."""
    if reward_amount <= 0 or reward_kind not in REWARD_KINDS:
        if required:
            raise PreviewError("حدّد قيمة الخصم — نسبة مثل 20% أو مبلغاً مثل 50 ريال.")
        return ""
    if reward_kind == "percent" and reward_amount > 100:
        raise PreviewError("نسبة الخصم لا يمكن أن تتجاوز 100%.")
    return format_discount_text(reward_kind=reward_kind, reward_amount=reward_amount)

FALLBACK_NAME = "عميلنا العزيز"


class PreviewError(Exception):
    """A refusal the owner can act on, while they are still looking at the screen."""


@dataclass
class Preview:
    # The message as it will arrive. Rendered, not described.
    message: str = ""
    # The number the owner is deciding about.
    reaches: int = 0
    # Matched but refused by the gate. Shown as a second line only when it is non-zero, because a
    # permanent "0 excluded" is noise that teaches people to stop reading the area.
    excluded: int = 0
    # HELD OUT BY THE CYCLE LOCK — they took this service too recently (spec §10.9.1). Kept apart
    # from `excluded` because this one has a reason the owner should READ: a reach number that
    # drops with no explanation looks like a fault, and the same number beside its cause looks
    # like a system that knows his shop.
    too_recent: int = 0
    truncated: bool = False
    # Why a sample of them matched — three at most. An owner who cannot see the rule cannot judge
    # it, and three examples explain a rule better than a sentence describing it.
    samples: list[str] = field(default_factory=list)
    # What will actually happen, in a sentence: "sends now", "sends tomorrow at 9am — it is
    # outside the permitted hours", "runs every day".
    when: str = ""

    @property
    def held_out_line(self) -> str:
        """The sentence under the reach number, or nothing at all.

        SAID ONLY WHEN IT HAPPENED. A permanent «استُثني 0» is noise that teaches an owner to stop
        reading the line — and the line is exactly what makes the lock read as intelligence rather
        than as a number that shrank.
        """
        if self.too_recent <= 0:
            return ""
        return f"استُثني {self.too_recent} لأنهم أخذوا الخدمة قريباً"


def sanitise_owner_text(value: str, *, required: bool) -> str:
    """Clean the owner's single field, or refuse it with a reason they can fix.

    REFUSED, NOT ESCAPED — the same decision as reminders. An escaped link is still a link a
    customer reads and retypes, and silently mangling the text produces a message the owner did not
    write and cannot explain when a customer asks about it.
    """
    v = (value or "").strip()
    if not v:
        if required:
            raise PreviewError("اكتب نص العرض — بدونه لا رسالة.")
        return ""
    if _CONTROL.search(v):
        raise PreviewError("النص يحتوي رموزاً غير مرئية — احذفها وأعد الكتابة.")
    if "\n" in v or "\r" in v:
        raise PreviewError("النص لا يقبل أسطراً جديدة — الرسالة سطر واحد.")
    if _URL.search(v):
        raise PreviewError("لا يُسمح برابط داخل الرسالة. القالب معتمَد من ميتا، ورابطٌ داخله "
                           "يجعله ناقلاً لما لم يُعتمد — والمحاسبة علينا لا عليك.")
    if _PHONE.search(v):
        raise PreviewError("لا يُسمح برقم هاتف داخل الرسالة — رقمك يظهر في ملفك أصلاً.")
    if len(v) > MAX_OWNER_TEXT:
        raise PreviewError(f"النص أطول من {MAX_OWNER_TEXT} حرفاً — اختصره ليقرأه العميل بنظرة.")
    return v


def compose_reward(*, reward_type: str, reward_kind: str, reward_amount: int, service_text: str,
                   reward_points: int) -> str:
    """The one composed sentence a `reward` fill resolves to — settled wording, matched exactly to
    reminders' own `rendering.campaign_slots` (the real send composes the identical three shapes;
    this is the screen showing the owner the same sentence before he presses launch).

    RAISES, LIKE `validate_discount_amount` ABOVE, rather than showing a placeholder for a reward
    that cannot compose — a preview promising a sentence the send will refuse is worse than a
    refusal now, while he is still looking at the screen.
    """
    if reward_type == "gift":
        if not service_text:
            raise PreviewError("الهدية تحتاج خدمة محدَّدة من كتالوجك — اختر واحدة على الأقل.")
        return f"هديتك: {service_text}"
    if reward_type == "points":
        if reward_points <= 0:
            raise PreviewError("عدد نقاط الهدية يجب أن يكون أكبر من صفر.")
        return f"منحناك {reward_points} نقطة هدية"
    value = validate_discount_amount(reward_kind=reward_kind, reward_amount=reward_amount,
                                     required=True)
    text = f"لك خصم {value}"
    if service_text:
        text += f" على {service_text}"
    return text


def render_message(*, template: dict[str, Any], establishment: str, owner_text: str,
                   sample_name: str = "", offer_value: str = "", ends_at: str = "",
                   service_text: str = "", reward_text: str = "") -> str:
    """The template filled, as one line of text.

    Rendered with a REAL customer's name when we have one and the fallback when we do not — the
    same fallback the send uses. Showing "[name]" here would let an owner approve a message whose
    real form they have never seen.
    """
    body = str(template.get("body") or "")
    fills = list(template.get("fills") or [])
    variables = list(template.get("variables") or [])

    values: dict[int, str] = {}
    for i, number in enumerate(variables):
        source = fills[i] if i < len(fills) else "system"
        if number == 1:
            values[number] = sample_name or FALLBACK_NAME
        elif number == 2:
            values[number] = establishment
        elif source == "owner":
            values[number] = owner_text
        elif source == "amount" and offer_value:
            values[number] = offer_value
        elif source == "date" and ends_at:
            values[number] = ends_at
        elif source == "catalogue" and service_text:
            values[number] = service_text
        elif source == "reward" and reward_text:
            values[number] = reward_text
        else:
            # A system value we cannot know at preview time — a date, an amount, a service name.
            # Rendered as a readable placeholder rather than left as {{4}}: the owner is judging
            # the SHAPE of the message, and braces are not a shape they can judge.
            values[number] = "…"

    out = body
    for number, value in values.items():
        out = out.replace("{{%d}}" % number, value)
    return out.strip()


def build(*, goal: str, template: dict[str, Any], establishment: str, owner_text: str,
          audience, when: str, reward_kind: str = "", reward_amount: int = 0, ends_at: str = "",
          service_text: str = "", reward_type: str = "discount",
          reward_points: int = 0) -> Preview:
    """The whole screen. Raises PreviewError on anything the owner must fix first."""
    fills = list(template.get("fills") or [])
    needs_text = any(f == "owner" for f in fills)
    clean = sanitise_owner_text(owner_text, required=needs_text)
    needs_reward = any(f == "reward" for f in fills)
    # THE DISCOUNT IS CHECKED WHILE HE IS LOOKING AT IT, not at the launch. A bad amount typed into
    # the value field and discovered a screen later is a screen later than it needed to be.
    #
    # NOT REQUIRED WHEN THE TEMPLATE'S OWN SLOT IS "reward" RATHER THAN "amount" — a gift or a
    # points reward carries no discount value at all, and `compose_reward` below does its own
    # checking of whatever field THAT reward actually needs.
    value = validate_discount_amount(reward_kind=reward_kind, reward_amount=reward_amount,
                                     required=any(f == "amount" for f in fills))
    # SAME DOOR, SAME LOCK — fixed 2026-09-12, a real gap a QA audit found: `service_name`/
    # `package_name` fill this exact "catalogue" template variable and reach reminders verbatim as
    # `service_names`, but only `owner_text` ever passed through the URL/phone/control-character
    # filter. A caller with `campaigns.manage` could put a link or number in a catalogue name and
    # have it rendered, under the establishment's own approved-template quota, straight to a
    # customer. `required=False`: an empty catalogue name is the normal, already-handled "…" case,
    # not a refusal.
    clean_service_text = sanitise_owner_text(service_text, required=False)
    reward_text = (compose_reward(reward_type=reward_type, reward_kind=reward_kind,
                                  reward_amount=reward_amount, service_text=clean_service_text,
                                  reward_points=reward_points)
                  if needs_reward else "")

    return Preview(
        message=render_message(template=template, establishment=establishment,
                               owner_text=clean, offer_value=value, ends_at=ends_at,
                               service_text=clean_service_text, reward_text=reward_text),
        reaches=audience.count,
        excluded=getattr(audience, "excluded", 0),
        too_recent=getattr(audience, "too_recent", 0),
        truncated=getattr(audience, "truncated", False),
        samples=[c.why for c in list(audience.candidates)[:3] if c.why],
        when=when)


_WEEKDAY_NAMES_AR = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]


def window_sentence(*, start_hour: int, end_hour: int, weekdays: list[int] | None) -> str:
    """"بين الساعة 8 و20، أيام السبت والأحد فقط" — or "" when the campaign has no window of its
    own (the `0, 24`/`[]` defaults) — that "" is what lets `describe_when` below append nothing
    for every campaign that predates this field, unchanged.
    """
    if start_hour == 0 and end_hour == 24 and not weekdays:
        return ""
    parts = [f"بين الساعة {start_hour} و{end_hour}"]
    if weekdays:
        names = [_WEEKDAY_NAMES_AR[w] for w in sorted(set(weekdays)) if 0 <= w <= 6]
        if names:
            parts.append(f"أيام {'، '.join(names)} فقط")
    return "، ".join(parts)


def describe_when(*, trigger: str, inside_window: bool, next_open_hour: int = 7,
                  own_window: str = "") -> str:
    """What will actually happen, in the owner's words.

    The third screen says this after they press send, and this line says it before — because
    "sends tomorrow at 9am" is a thing an owner may want to change their mind about, and learning
    it afterwards is learning it too late.

    `own_window` — this CAMPAIGN's own configured window (`window_sentence()`, above), a separate
    fact from `inside_window` (the platform's own daily send-window, reminders' `gate.py`). Both
    can apply at once: a standing campaign still only fires within its own hours, and a scheduled
    one still only fires within them once its `fire_at` arrives.
    """
    suffix = f" تُرسَل فقط {own_window}." if own_window else ""
    if trigger == "standing":
        return "تعمل تلقائياً كل يوم، وتصل من تنطبق عليه." + suffix
    if not inside_window:
        return (f"تُرسَل غداً الساعة {next_open_hour} صباحاً — "
                f"الآن خارج وقت الإرسال المسموح.") + suffix
    if trigger == "scheduled":
        return "تُرسَل في الموعد الذي حدّدته." + suffix
    return "تُرسَل الآن." + suffix
