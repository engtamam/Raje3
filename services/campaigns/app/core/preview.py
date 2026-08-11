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


def render_message(*, template: dict[str, Any], establishment: str, owner_text: str,
                   sample_name: str = "") -> str:
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
          audience, when: str) -> Preview:
    """The whole screen. Raises PreviewError on anything the owner must fix first."""
    needs_text = any(f == "owner" for f in (template.get("fills") or []))
    clean = sanitise_owner_text(owner_text, required=needs_text)

    return Preview(
        message=render_message(template=template, establishment=establishment,
                               owner_text=clean),
        reaches=audience.count,
        excluded=getattr(audience, "excluded", 0),
        too_recent=getattr(audience, "too_recent", 0),
        truncated=getattr(audience, "truncated", False),
        samples=[c.why for c in list(audience.candidates)[:3] if c.why],
        when=when)


def describe_when(*, trigger: str, inside_window: bool, next_open_hour: int = 7) -> str:
    """What will actually happen, in the owner's words.

    The third screen says this after they press send, and this line says it before — because
    "sends tomorrow at 9am" is a thing an owner may want to change their mind about, and learning
    it afterwards is learning it too late.
    """
    if trigger == "standing":
        return "تعمل تلقائياً كل يوم، وتصل من تنطبق عليه."
    if not inside_window:
        return (f"تُرسَل غداً الساعة {next_open_hour} صباحاً — "
                f"الآن خارج وقت الإرسال المسموح.")
    if trigger == "scheduled":
        return "تُرسَل في الموعد الذي حدّدته."
    return "تُرسَل الآن."
