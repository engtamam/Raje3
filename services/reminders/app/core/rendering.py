"""Choosing a template and filling its variables — the last step before a message exists.

WE DO NOT STORE THE TEXT. `operations` owns the template library and `notification-service` owns
the per-tenant registry that Meta approved. This service decides WHICH template and WHAT goes in
each numbered slot, and hands both to the sender. Copying the body here would be a third place the
wording lives, and the third place is always the stale one.

THE FILL CONTRACT (spec Appendix A, operations' template library). Every template declares who
supplies each variable:

  system      from the record — the customer's name, the establishment, a date, an amount.
  catalogue   from the tenant's own service list — a tap, not a sentence.
  owner       the single free-text field, written once when the message was set up.
  amount      a discount or a price — «20%» or «50 ريال», nothing else.
  date        the day an offer ends, phrased by us.

THE LAST TWO ARE TYPED, AND THAT IS THE WHOLE POINT. They used to be `owner` free text, which
let a shop promise «خصم كبير» (nothing a customer can hold anybody to), write «٢٠٪» in digits our
own screens refuse, or run an offer with no end at all. A typed slot is checked against its shape
here — where a bad value stops one message rather than reaching a customer under the shop's name.

AND THE OWNER'S FIELD IS SANITISED, ALWAYS. This is the security boundary of the whole messaging
path: a free variable inside a template Meta approved is an injection channel that goes out under
the ESTABLISHMENT'S name and counts against OUR quality rating. An owner who writes a link into
"the offer" turns an approved template into a carrier for something nobody approved, and Meta bills
us, not them.

So: no URLs, no phone numbers, no control characters, no newlines, length-capped. Refused rather
than escaped — an escaped link is still a link a customer can read and retype, and silently
mangling what an owner wrote produces a message they did not intend and cannot explain.

VARIABLE 1 IS NEVER EMPTY. Meta rejects a template with a blank variable at send time, and the
name is optional in our own model — a customer recorded by phone alone has none. So it falls back
to a greeting rather than an empty string, which is a rejection three days later blaming the
wording.
"""
# arabic-indic-digits: intentional — named in a refusal message, as the shape we do NOT accept.
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from app.core import links as L
from app.core.riyadh import local

# A blank {{1}} is a Meta rejection at send time. This is what goes in instead.
FALLBACK_NAME = "عميلنا العزيز"

MAX_OWNER_FIELD = 60

# ── the shapes the typed slots accept ────────────────────────────────────────────────────────
# WESTERN DIGITS ONLY, here as everywhere: Arabic-Indic digits render inconsistently across the
# phones our customers actually hold, and a discount nobody can read is worse than no discount.
# Kept character-for-character equal to campaigns' `_OFFER` by a gate, not by a promise: see
# `ci/check_the_offer_a_shop_types_is_judged_the_same_everywhere.py`. 1-99% and no 100, because an
# offer that gives the whole thing away is a mistake far more often than it is an intention.
_AMOUNT = re.compile(r"^(?:[1-9][0-9]?%|[0-9]{1,6}(?:\.[0-9]{1,2})? ريال)$")

# What may not appear in an owner-written value. Deliberately blunt and refusing rather than clever
# and escaping: this list guards a channel that carries somebody else's brand.
_URL = re.compile(r"(https?://|www\.|\b[a-z0-9-]+\.(com|net|org|sa|io|co)\b)", re.I)
_PHONE = re.compile(r"(?:\+?\d[\s-]?){7,}")
_CONTROL = re.compile(r"[\x00-\x1f\x7f​-‏‪-‮]")


class RenderError(Exception):
    """A refusal an owner can act on, in words they can act on."""


@dataclass
class Rendered:
    template_name: str
    template_type: str
    cls: str
    # Positional, 1-indexed at the wire. A dict keyed by number would let a gap through; a list
    # cannot have one.
    variables: list[str]


def sanitise_owner_text(value: str) -> str:
    """Clean an owner-written value, or refuse it with a reason they can fix.

    REFUSED, NOT ESCAPED. An escaped link is still a link a customer reads and retypes, and
    silently mangling the text produces a message the owner did not write and cannot explain when
    a customer asks about it.
    """
    v = (value or "").strip()
    if not v:
        raise RenderError("النص مطلوب ولا يصح أن يكون فارغاً — ميتا ترفض المتغيّر الفارغ.")
    if _CONTROL.search(v):
        raise RenderError("النص يحتوي رموزاً غير مرئية — احذفها وأعد الكتابة.")
    if "\n" in v or "\r" in v:
        raise RenderError("النص لا يقبل أسطراً جديدة — القالب سطر واحد.")
    if _URL.search(v):
        raise RenderError("لا يُسمح برابط داخل نص الرسالة. القالب معتمَد من ميتا، ورابطٌ داخله "
                          "يجعله ناقلاً لما لم يُعتمد — والمحاسبة علينا.")
    if _PHONE.search(v):
        raise RenderError("لا يُسمح برقم هاتف داخل نص الرسالة — رقم المنشأة يظهر في الملف أصلاً.")
    if len(v) > MAX_OWNER_FIELD:
        raise RenderError(f"النص أطول من {MAX_OWNER_FIELD} حرفاً — اختصره ليقرأه العميل بنظرة.")
    return v


def choose(*, template_type: str, tone: str, library: list[dict[str, Any]],
           approved: set[str] | None = None, own: str = "",
           own_row: dict[str, Any] | None = None, tone_index: int = 1) -> dict[str, Any]:
    """Pick the template for this type in this tenant's tone, preferring one Meta has approved.

    FALLS BACK TO ANY ACTIVE TONE rather than failing. A tenant whose tone was set to one we later
    retired would otherwise stop sending entirely — a configuration mismatch becoming a silent
    outage, which is the shape this codebase keeps finding.

    ────────────────────────────────────────────────────────────────────────────────────────────
    WHY APPROVAL IS CHECKED HERE AT ALL, when notification-service checks it anyway.

    Approval is per (tenant, name): the library is authored once and submitted to every
    establishment's own WhatsApp account, so the same text is approved for one shop and pending for
    another (spec §6.6.1).

    Without this, a shop whose library is still under review sends, the peer refuses at the
    delivery layer, and the schedule is deferred. That is correct — nothing is lost — but the
    attempt has already taken its slot in the daily cap, and a shop that connected this morning has
    an entire library in review. One read per tenant per tick replaces all of it.

    THIS PARAMETER EXISTED ONCE AND WAS REMOVED THE SAME DAY, because nothing could supply it:
    notification-service's template list was user-tier, and a service cannot mint a user token
    without the signing key, which lives in identity-service and must stay there. A parameter
    nobody can pass is a promise the code does not keep. It was escalated, and v0.13.5 added
    GET /internal/whatsapp/templates?tenant=&status= — token-authed, tenant as a parameter. So it
    is back, with the same rules that were right the first time.

    ────────────────────────────────────────────────────────────────────────────────────────────
    `approved=None` MEANS NOT KNOWN, AND SKIPS THE FILTER ENTIRELY.

    Deliberately not an empty set. An empty set means "nothing may be sent", so a caller that
    forgot to pass the argument would silence the entire product rather than behave as it did
    before. Not-known and none-approved are opposite facts and must not share a representation.

    THE TONE IS WHAT IS GIVEN UP, NEVER THE SEND. A shop whose chosen tone is still pending and
    whose other two are approved sends in a different voice — a message in the wrong register
    reaches the customer, and a message held for the right one does not.

    AND IT ASKS FOR `approved`, IT DOES NOT EXCLUDE `pending`. v0.13.5 split the statuses:
    pending | approved | rejected | paused | disabled. Excluding pending would let paused and
    disabled straight through, and neither is sendable — Meta pauses a template for quality and
    disables it permanently. An allowlist keeps a status added later out by default; a denylist
    lets it in.
    """
    # ── HIS OWN TEXT FIRST, IF META HAS APPROVED IT ────────────────────────────────────────
    #
    # THE WIRE THAT WAS NEVER CONNECTED. An owner could write his own message, submit it, and have
    # Meta approve it — and the send path chose from OUR library regardless. `template_name()` on
    # his choices was read by the preview screen and by nothing that sends. He saw his text on the
    # screen and his customers received ours.
    #
    # AND THE FALLBACK IS THE OTHER HALF OF THE SAME RULE. Meta rejects a text, or is still
    # reviewing it, or paused it for quality — in every one of those the shop must keep sending,
    # in our words, rather than go quiet. A shop that stops sending because one sentence it wrote
    # was refused has lost the product over an edit.
    #
    # `approved is None` MEANS NOT KNOWN, and his name is used on trust: it is the same rule the
    # library gets three lines down, and refusing his text on an unreadable status would be the
    # outage this whole function is written to avoid.
    if own and (approved is None or own in approved):
        # HIS BLANKS TRAVEL WITH HIS TEMPLATE. This branch used to return the NAME alone, and
        # `render` reads `variables`/`fills` off the template it is given — so a shop's own
        # approved text went out with ZERO parameters: every blank he wrote arrived empty, or Meta
        # refused the send outright for a parameter count that did not match. The one feature we
        # sell as «اكتبها بنفسك» could not deliver a single filled message.
        #
        # `own_row` is his stored template (core/custom_templates.py), which already holds the
        # numbering and the meaning of each blank — checked at write time, so nothing is re-derived
        # here from text we do not store.
        #
        # AND ITS ABSENCE IS NEVER "NO CUSTOMIZATION" (ح-6). `own` is only set when the shop's own
        # choices name a template it picked — so a missing `own_row` means the read failed or the
        # row was lost, not that nothing was customized. This used to fall back to `{}`, which
        # rendered `variables: []`: Meta refused the send for a parameter-count mismatch, or the
        # template's numbered slots went out with nothing in them — a blank sentence under the
        # shop's own approved name. The fallback is a refusal instead, which the send log can show
        # and the shop can act on.
        if own_row is None:
            raise RenderError(
                f"تعذّرت قراءة القالب الخاص «{own}» — لن تُرسَل رسالة بمتغيّرات فارغة.")
        return {"name": own, "type": template_type, "tone": tone, "active": True, "own": True,
                "variables": list(own_row.get("variables") or []),
                "fills": list(own_row.get("fills") or [])}

    active = [t for t in library if t.get("type") == template_type and t.get("active", True)]
    if not active:
        raise RenderError(f"لا يوجد قالب فعّال من نوع {template_type}.")

    if approved is not None:
        usable = [t for t in active if t.get("name") in approved]
        if not usable:
            # A DIFFERENT SENTENCE FROM THE ONE ABOVE, and the difference is who has to act.
            # "No approved template of this type" means Meta is still reviewing and the answer is
            # patience; "no template of this type" means the library was never seeded and the
            # answer is us. One error message for both would send a shop owner to support for a
            # thing that resolves itself in an hour.
            raise RenderError(
                f"قوالب {template_type} ما زالت قيد مراجعة واتساب — سترسل تلقائياً عند اعتمادها.")
        active = usable

    # ── THE RUNG'S VOICE (د-7) ──────────────────────────────────────────────────────────────
    #
    # `tone_index` was stamped on every ladder rung from the day the ladder was built and READ BY
    # NOBODY: this function had no such parameter. So the second rung was the first rung, word for
    # word — the same template, the same tone, the same sentence, days apart. «تنويع لا تصعيد» is
    # §5.6.1's rule, and a customer receiving one sentence twice is precisely the thing that gets
    # reported, and a reported number is a banned number.
    #
    # THE MECHANISM STILL PICKS BY INDEX INTO THE SHOP'S TONE FIRST, THEN THE REST — it is not
    # hardcoded to three tones or to any tone name. What changed is who calls it with an index
    # other than 1: `core/ladder.py` used to hop to a second tone for variety, safe when every
    # tone addressed the customer the same grammatical way (spec's old brief/warm/formal). Now the
    # library carries two tones split by grammatical gender (masculine/feminine), so `ladder.py` no
    # longer asks for anything but index 1 — see its own docstring for why. Index 1 is the shop's
    # chosen tone and everything that is not a rung, so nothing outside the ladder changes.
    ordered = [t for t in active if t.get("tone") == tone] +               [t for t in active if t.get("tone") != tone]
    if not ordered:
        return active[0]
    return ordered[(max(1, int(tone_index or 1)) - 1) % len(ordered)]


def choose_carousel(*, template_type: str, tone: str, library: list[dict[str, Any]],
                    approved: set[str] | None = None) -> dict[str, Any] | None:
    """The carousel-shaped counterpart of `choose()` — for a shop WITHOUT the appointment book
    (core/shape.py's `carousel` request, Phase 2). Returns the template row, or `None`.

    NEVER RAISES, UNLIKE `choose()`. A carousel is an upgrade over the plain text every shop already
    gets, never a reason to refuse a send — no carousel template of this type, none in this tone,
    none Meta has approved for this tenant yet: every one of those is `None`, and the caller falls
    back to the ordinary flat template exactly as it would if the request had never been made.

    `choose()` ITSELF NEVER SEES THESE ROWS. A carousel row carries `active: false` in the seed
    (operations/data/templates.seed.json) precisely so the flat send path and the `sendable` goal-
    card endpoint — both of which filter on `t.get("active", True)` — skip it entirely; this is the
    only function that reads it, by looking for `t.get("carousel")` instead of `active`. Sharing the
    campaign goal's own `type` (mkt_offer/mkt_winback/mkt_personal_occasion) with the flat rows,
    rather than inventing a separate type, keeps the carousel out of the goal picker as a selectable
    campaign type in its own right — it is a SHAPE the existing three goals may take, not a fourth
    goal.
    """
    candidates = [t for t in library if t.get("type") == template_type and t.get("carousel")]
    if not candidates:
        return None
    if approved is not None:
        candidates = [t for t in candidates if t.get("name") in approved]
        if not candidates:
            return None
    ordered = [t for t in candidates if t.get("tone") == tone]
    return ordered[0] if ordered else candidates[0]


#: The owner's own vocabulary — every name `custom_templates.check()` accepts on a `fills` list,
#: which is `reasons.slots_for()`. This module used to know none of them.
#:
#: THE DEFECT (ح-1). `check()` validated an owner's blanks against these names and stored them;
#: `render()` understood only its own six sources and dropped everything else into an `else` that
#: reads `system[NUMBER]` — the LIBRARY row's meaning for that position. So «هلا {{1}}، جاهز {{2}}
#: عندنا» with fills `[customer, service]` sent «هلا محمد، جاهز مغسلة النخيل عندنا»: slot 2 is the
#: shop name in the library's layout. And the preview fills by MEANING and was right, so the owner
#: approved one sentence and his customers received another — in his name.
OWNER_SLOTS = frozenset({
    "customer", "shop", "service", "reward", "points", "balance", "action", "digest",
    "offer_value", "ends_at", "free_text", "code", "minutes",
})


#: The two slots that carry an ADDRESS rather than a word, and the only ones this module cannot
#: fill from what it was handed. A page path is meaningless on a phone, so both are composed by
#: core/links.py from the fleet's public base — and both refuse when that base is not configured.
LINK_SLOTS = {"link": L.customer_page, "stop_link": L.stop_link}


def render(*, template: dict[str, Any], system: dict[str, str],
           catalogue: dict[str, str], owner: dict[str, str],
           by_meaning: dict[str, str] | None = None,
           public_base_url: str = "", reference: str = "",
           marketing_consent: str = "", rating_points: int = 0) -> Rendered:
    """Fill every variable the template declares, in order.

    `system`, `catalogue` and `owner` are keyed by variable NUMBER as a string ("1", "2", ...).
    Keyed by number rather than by name because Meta numbers variables and does not name them: a
    value that knows its own position cannot be put in the wrong slot by a rename.
    """
    fills = list(template.get("fills") or [])
    variables = list(template.get("variables") or [])
    if not variables:
        return Rendered(template.get("name", ""), template.get("type", ""),
                        template.get("class", "service"), [])

    # The library refuses a numbering gap at write time (operations' TemplateLibrary). Checked
    # again here because this side must not depend on the other side having been right — a gap
    # that reaches the wire is a rejection days later blaming the wording.
    if variables != list(range(1, len(variables) + 1)):
        raise RenderError(f"ترقيم متغيّرات القالب {template.get('name')} فيه فجوة: {variables}.")
    if fills and len(fills) != len(variables):
        raise RenderError(f"القالب {template.get('name')} يعلن {len(fills)} مصادر لـ"
                          f"{len(variables)} متغيّراً.")

    out: list[str] = []
    for i, number in enumerate(variables):
        key = str(number)
        source = fills[i] if i < len(fills) else "system"
        if source in LINK_SLOTS:
            # AN ADDRESS, NOT A WORD. Every other source here is text somebody typed or a number we
            # computed; this one has to be somewhere a thumb can reach. `links.py` composes it from
            # the fleet's public base and RAISES when that base is unset or the reference is not
            # one we issued — deliberately, because the alternative is a message that is delivered,
            # reported as sent, and carries a link that opens nothing.
            try:
                out.append(LINK_SLOTS[source](public_base_url, reference))
            except L.LinkError as exc:
                raise RenderError(str(exc)) from exc
        elif source == "invite":
            # THE LAST LINE OF EVERY UTILITY TEXT, AND THE ONLY DOOR CONSENT COMES THROUGH.
            #
            # A whole sentence rather than a bare address, because the two states say different
            # things: somebody who has never been asked is invited, somebody who agreed is told
            # his benefits are live and given NO link — the page one would point at is closed for
            # this release — and somebody who REFUSED is not asked again, which §8.5 calls pursuit
            # rather than marketing.
            #
            # `core/invite.py` holds both, and refuses rather than composing a dead address.
            from app.core import invite as I

            try:
                out.append(I.line(consent=marketing_consent,
                                  public_base_url=public_base_url, reference=reference))
            except L.LinkError as exc:
                raise RenderError(str(exc)) from exc
        elif source == "rating_cta":
            # A WHOLE SENTENCE, COMPUTED HERE — same discipline as `invite` just above: WhatsApp
            # refuses an empty variable, so a shop with no participation points configured gets a
            # full neutral sentence, never a blank and never a sentence naming zero points.
            from app.core import rating_cta as RC
            out.append(RC.line(rating_points))
        elif source == "amount":
            value = (system.get(key) or "").strip()
            if not _AMOUNT.fullmatch(value):
                raise RenderError(
                    f"قيمة الخصم «{value}» غير مقبولة — اكتبها نسبةً مثل 20% أو مبلغاً مثل "
                    f"50 ريال.")
            out.append(value)
        elif source == "date":
            value = (system.get(key) or "").strip()
            if not value:
                # AN OFFER WITHOUT AN END IS AN OFFER FOR EVER, and the shop honours it at the
                # till long after it meant to stop. Refusing the send is the cheaper failure.
                raise RenderError("العرض بلا تاريخ انتهاء — لا تُرسَل رسالة تعِد بخصمٍ بلا نهاية.")
            out.append(value)
        elif source in OWNER_SLOTS:
            # BY MEANING, AND REFUSED WHEN THE MEANING HAS NO VALUE. Positional lookup is what
            # produced the wrong sentence; falling back to it here would keep the defect behind a
            # nicer name. A refusal costs this one message and is visible in the send log; a guess
            # reaches a customer, in the shop's name, and nothing anywhere records that it was
            # wrong.
            value = ((by_meaning or {}).get(source) or "").strip()
            if not value and source == "customer":
                value = FALLBACK_NAME
            if not value:
                raise RenderError(
                    f"الفراغ «{source}» لا قيمة له في هذه الرسالة — لا تُرسَل بنصٍّ ناقص.")
            out.append(sanitise_owner_text(value) if source == "free_text" else value)
        elif source == "owner":
            out.append(sanitise_owner_text(owner.get(key, "")))
        elif source == "catalogue":
            value = (catalogue.get(key) or "").strip()
            if not value:
                raise RenderError(f"المتغيّر {key} يأتي من كتالوج الخدمات ولم يُحدَّد.")
            # Sanitised too. A service name is picked from a list, but the list is one the OWNER
            # types into — "picked from a catalogue" describes the UI, not the provenance.
            out.append(sanitise_owner_text(value))
        else:
            value = (system.get(key) or "").strip()
            # Variable 1 is the customer's name and the name is optional in our model. Empty is a
            # Meta rejection at send time, so it falls back rather than failing.
            if not value and key == "1":
                value = FALLBACK_NAME
            if not value:
                raise RenderError(f"المتغيّر {key} من النظام وهو فارغ — لا تُرسَل رسالة ناقصة.")
            # KEY "1" IS THE CUSTOMER'S OWN NAME — the one `system` value a customer, not the shop,
            # actually authors (self-registration or staff typing exactly what he gave them). Every
            # OTHER free-text-shaped slot in this function already runs through sanitise_owner_text;
            # this one didn't, which is the same injection channel that guard exists for, just
            # reachable by a customer instead of an owner. Every other `system` key here is a
            # computed value (a date, a count) this service produced itself, never customer-typed —
            # sanitising those would risk rejecting a legitimate value shaped unlike free text.
            out.append(sanitise_owner_text(value) if key == "1" else value)

    return Rendered(template.get("name", ""), template.get("type", ""),
                    template.get("class", "service"), out)


AR_MONTHS = ("يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
             "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر")


def arabic_date(epoch: int) -> str:
    """The last day of an offer, as a person reads it — in Riyadh, in Western digits.

    RIYADH AND NOT UTC: an offer ending at 01:00 UTC ends the previous evening for the customer
    reading it, and a message that names the wrong day is a message the shop honours for a day it
    did not intend.
    """
    if not epoch:
        return ""
    from datetime import datetime, timedelta, timezone
    d = local(epoch)
    return f"{d.day} {AR_MONTHS[d.month - 1]}"


#: `date.weekday()`'s own numbering — Monday=0..Sunday=6 — matching `bookings`' own
#: `app/core/availability.py` exactly rather than inventing a second one for this reader.
AR_WEEKDAYS = ("الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد")


def arabic_appointment(epoch: int) -> str:
    """A booking's day and hour, as its customer reads it — «الأحد 9:00 مساءً» — in Riyadh, in
    Western digits, 12-hour with the Arabic ص/م rather than a bare 24-hour number nobody reads a
    WhatsApp message in.

    RIYADH AND NOT UTC, same reasoning as `arabic_date`: a booking at 21:00 UTC is a different
    evening for the customer holding the phone, and a wrong day in a confirmation is worse than no
    confirmation at all.
    """
    if not epoch:
        return ""
    d = local(epoch)
    hour12 = d.hour % 12 or 12
    suffix = "م" if d.hour >= 12 else "ص"
    return f"{AR_WEEKDAYS[d.weekday()]} {hour12}:{d.minute:02d} {suffix}"


def campaign_slots(template: dict[str, Any], *, establishment: str, owner_text: str,
                   service_text: str = "", offer_value: str = "",
                   expires_at: int = 0) -> dict[str, str]:
    """What goes in each numbered slot of a CAMPAIGN message, decided by the slot's own source.

    THE OLD ANSWER WAS TO PUT THE SAME STRING IN EVERYTHING. The campaign path filled slots 3 and
    4 with `owner_text` in all three source dicts, so a four-variable template emitted the owner's
    one sentence twice in a row — «باقة تنظيف كامل من مغسلة النخيل: تنظيف كامل» — and slot 1 was
    passed empty, which greeted every customer «عميلنا العزيز» although we hold their names.

    So the template says who fills each slot (`fills`), and this answers slot by slot. A template
    that asks for something a campaign cannot supply gets an empty string and the renderer refuses
    the send — which is right: a discount with no value and an offer with no end are exactly the
    messages that must not go out.

    SLOT 1 IS LEFT EMPTY ON PURPOSE. The customer's name is personal data this service does not
    hold; it is filled at the very last moment, beside the phone number, in the sender.
    """
    fills = list(template.get("fills") or [])
    variables = list(template.get("variables") or [])
    out: dict[str, str] = {}
    for i, number in enumerate(variables):
        key = str(number)
        source = fills[i] if i < len(fills) else "system"
        if source == "amount":
            out[key] = offer_value
        elif source == "date":
            out[key] = arabic_date(expires_at)
        elif source == "catalogue":
            # The services the offer covers, named. Empty when it covers the whole shop — and the
            # renderer then refuses, because «خصم على » is not a sentence.
            out[key] = service_text
        elif source == "establishment":
            # AN OWNER-ONLY TEMPLATE'S OWN NAME SLOT (per_weekly_digest) — never the number==1
            # customer assumption below, which is exactly the defect the seed's own comment
            # documents: a template with no customer at all fell through to the customer-shaped
            # guess for slot 1 and showed FALLBACK_NAME («عميلنا العزيز») where the shop's own name
            # belongs. `source` decides this now, not the slot's position.
            out[key] = establishment
        elif source == "system" and number == 1:
            # THE ONE CASE LEFT POSITIONAL, AND DELIBERATELY: an ordinary customer-facing template
            # declares "system" for both its name slots, and only the position tells the two
            # apart (slot 1 the customer, filled at the very last moment beside the phone number —
            # see this function's own docstring — slot 2 the shop). A template with no customer at
            # all says so explicitly via `establishment`/`owner`/etc above, never via "system".
            out[key] = ""
        elif source == "system":
            out[key] = establishment
        else:
            out[key] = owner_text
    return out


def merged_service_text(names: list[str]) -> str:
    """Three services in one message, as one readable phrase (spec 5.8).

    Arabic joins with «و» and not with a comma-and-final-and, so this is not a translation of an
    English list formatter. Capped at three names plus a count: a reminder listing seven services
    is a receipt, and nobody reads a receipt sent as a reminder.
    """
    clean = [n.strip() for n in names if n and n.strip()]
    if not clean:
        return ""
    if len(clean) == 1:
        return clean[0]
    if len(clean) <= 3:
        return "، ".join(clean[:-1]) + " و" + clean[-1]
    return "، ".join(clean[:3]) + f" و{len(clean) - 3} غيرها"


class PlatformLibrary:
    """The 81 texts themselves, read from operations — the ONE thing the engine could not find.

    WHAT WAS WRONG, AND IT IS THE THIRD OF ITS FAMILY IN THIS SERVICE. `_library()` read a
    `tenant_cache` collection that NOTHING IN THE FLEET EVER WROTE, so it answered `[]` on every
    tick, `choose()` found no template of any type, and every single message — every reminder,
    confirmation, follow-up and campaign — failed with «لا يوجد قالب فعّال من نوع …». The engine
    had no library at all. Its two siblings were the establishment's name and the settings tree,
    both fixed the same way: read the owner of the fact rather than a cache nobody fills.

    CACHED BRIEFLY, BECAUSE IT IS PLATFORM CONTENT. The library is the same for every tenant and
    changes when WE edit it in the console — minutes of staleness cost nothing, and a read per
    tenant per tick would be one HTTP call per shop per five minutes for a constant.

    AN UNREACHABLE PEER KEEPS THE LAST ANSWER. Losing the library mid-outage would stop every
    shop's messages; the texts do not change while operations restarts.
    """

    def __init__(self, *, url: str = "", path: str = "", token: str = "",
                 timeout: int = 8, ttl: int = 300) -> None:
        self._url = (url.rstrip("/") + path) if url else ""
        self._token = token
        self._timeout = timeout
        self._ttl = ttl
        self._rows: list[dict[str, Any]] = []
        self._at = 0.0

    async def all(self) -> list[dict[str, Any]]:
        """The rows, and nothing about whether they were read.

        RIGHT FOR THE SEND PATH, WRONG FOR A SCREEN. A scheduler that cannot reach the library
        skips this tick and tries the next one; nobody is told anything, which is correct. But a
        SCREEN handed the same `[]` cannot tell an outage from an empty shelf, and the one that was
        invented a sentence about Meta reviewing templates that had never been submitted. `read()`
        below carries the answer; `ci/check_a_screen_is_never_handed_an_unread_list.py` keeps this
        one out of `api/v1`.
        """
        return (await self.read())["templates"]

    async def read(self) -> dict[str, Any]:
        """`{"ok": bool, "templates": [...]}` — the rows AND whether this call actually got them.

        `ok` is FALSE for a peer that refused or could not be reached, and TRUE for a library that
        answered with nothing in it. Those are different facts about different people: the first is
        ours to fix and the owner should be told only that; the second is a gap in what we ship.

        A CACHED ANSWER IS A READ ANSWER. Inside the TTL we return what we hold with `ok: True` —
        it came from a successful call, and calling it unread would flicker a screen between two
        sentences for no reason a person could see.
        """
        import json
        import time as _time
        import urllib.error
        from app.adapters import internal_http

        if not self._url:
            # NOT CONFIGURED IS NOT A FAILED READ. A local run with no peer holds whatever it was
            # seeded with, and that is exactly what it should serve.
            return {"ok": True, "templates": list(self._rows)}
        now = _time.time()
        if self._rows and (now - self._at) < self._ttl:
            return {"ok": True, "templates": list(self._rows)}
        try:
            out = internal_http.get_json(self._url, self._token, self._timeout)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError):
            # THE LAST GOOD ANSWER, NEVER AN EMPTY LIBRARY — and now it says so.
            return {"ok": False, "templates": list(self._rows)}
        rows = out.get("templates")
        if isinstance(rows, list) and rows:
            self._rows = rows
            self._at = now
            return {"ok": True, "templates": list(self._rows)}
        # ANSWERED, AND ANSWERED WITH NOTHING. The peer is up; the shelf is empty. Whoever asked
        # may say so plainly instead of blaming a network it cannot see.
        return {"ok": True, "templates": list(self._rows)}


class ShopCatalogue:
    """Each service's own cycle, read from the shop that owns it — the number the OWNER set.

    THE DEFECT THIS CLOSES, AND IT IS THE FOURTH OF ITS FAMILY HERE. The scheduler resolves a
    service's cycle through the settings tree, whose default is DEFAULT_INTERVAL_DAYS — 90. But an
    establishment's real cycles live in its CATALOGUE (operations), written by its owner the day
    it registered: a car wash's «غسيل خارجي» is 10 days, a workshop's oil change is 90, a barber's
    haircut is 21. Nothing ever read that. So every shop that never hand-edited a service — which
    is every new shop — had every first reminder scheduled at 90 days.

    Found on the cluster, not by a test: a real wash shop's visit scheduled its reminder 83 days
    out (90 minus a 7-day lead) for a service whose catalogue says 10. Nothing failed. The owner
    sees «10» on his own screen and no customer ever comes back.

    WHERE IT SITS IN THE ORDER: the settings tree WINS — what the owner set explicitly for a
    service, or its group, or his shop, is his decision and outranks everything. This answers only
    where the tree has nothing to say, and our platform default answers only where this cannot.

    ONE READ PER TENANT PER TICK, cached briefly. A catalogue changes when the owner edits it, and
    a minute of staleness costs a reminder scheduled a day early at worst.

    AN UNREACHABLE PEER KEEPS THE LAST ANSWER, and an empty one is treated as "unknown" rather than
    "no cycles": answering zero would push every shop back onto the 90-day default, which is the
    exact defect this exists to end.
    """

    def __init__(self, *, url: str = "", path: str = "", token: str = "",
                 timeout: int = 8, ttl: int = 300) -> None:
        self._url = (url.rstrip("/") + path) if url else ""
        self._token = token
        self._timeout = timeout
        self._ttl = ttl
        #: tenant -> (fetched_at, {service_id: {"cycle_days": float, "name": str}})
        #:
        #: THE NAME IS CACHED BESIDE THE CYCLE (أ-5), from the same answer. Operations has always
        #: sent it — `{"id", "name", "cycle_days", …}` — and this adapter kept the number and threw
        #: the word away, so every reminder in the product read «تذكير بخصوص svc_7f3a…». Fetching
        #: it separately would be a second call for a field already in the response.
        self._by_tenant: dict[str, tuple[float, dict[str, dict]]] = {}

    async def cycles(self, tenant: str) -> dict[str, float]:
        """`{service_id: cycle_days}` for one establishment. Empty when unknown.

        A service with no cycle is ABSENT: zero means «no natural rhythm» to the scheduler, and it
        must keep meaning that. `names` does not filter — a puncture repair has a name even though
        it has no cycle, and something that mentions it still needs the word.
        """
        rows = await self._rows(tenant)
        return {sid: float(r.get("cycle_days") or 0) for sid, r in rows.items()
                if float(r.get("cycle_days") or 0) > 0}

    async def names(self, tenant: str) -> dict[str, str]:
        """`{service_id: name}` — his words for his own services, from the same cached read."""
        return {sid: str(r.get("name") or "") for sid, r in (await self._rows(tenant)).items()
                if r.get("name")}

    async def _rows(self, tenant: str) -> dict[str, dict]:
        import json
        import time as _time
        import urllib.error
        from app.adapters import internal_http

        if not self._url or not tenant:
            return {}
        now = _time.time()
        hit = self._by_tenant.get(tenant)
        if hit and (now - hit[0]) < self._ttl:
            return dict(hit[1])
        body = json.dumps({"tenant": tenant}).encode()
        try:
            out = json.loads(internal_http.read(
                self._url, self._timeout, method="POST", body=body,
                content_type=internal_http.JSON, token=self._token) or b"{}")
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
            return dict(hit[1]) if hit else {}
        rows = out.get("services")
        if not isinstance(rows, list):
            return dict(hit[1]) if hit else {}
        # EVERY SERVICE IS KEPT HERE, cycle or none, because the name is wanted for all of them —
        # `cycles()` is what drops the ones with no rhythm, and it still does.
        kept = {str(r.get("id")): {"cycle_days": float(r.get("cycle_days") or 0),
                                   "name": str(r.get("name") or "")}
                for r in rows if r.get("id")}
        self._by_tenant[tenant] = (now, kept)
        return dict(kept)


class ApprovedTemplates:
    """Which template names WhatsApp has approved for one tenant.

    ONE READ PER TENANT PER TICK, not one per message. The tick already reads a library once per
    tenant and this belongs beside it: a shop with 300 due reminders would otherwise ask
    notification-service 300 times for an answer that cannot change mid-tick.

    NOT CACHED ACROSS TICKS, deliberately. A template approved five minutes ago should start being
    used on the next tick, not in an hour — and the whole reason this exists is a shop that
    connected this morning, whose statuses are changing while it runs. A stale cache would recreate
    the wasted send it was built to avoid, just later.

    UNREACHABLE ANSWERS `None`, WHICH MEANS NOT KNOWN. choose() then skips the filter and behaves
    exactly as it did before this existed: it sends, and notification-service refuses if the
    template is not ready. That is a wasted send, and it is the correct failure — an unreachable
    peer must not stop a shop's reminders, and `set()` here would silence every establishment we
    host for as long as the outage lasted.
    """

    def __init__(self, *, url: str = "", path: str = "", token: str = "",
                 timeout: int = 8) -> None:
        self._url = (url.rstrip("/") + path) if url else ""
        self._token = token
        self._timeout = timeout

    async def names(self, tenant: str) -> set[str] | None:
        if not self._url:
            return None                       # not configured — not known, never "none approved"
        import json
        import urllib.error
        import urllib.parse
        from app.adapters import internal_http

        # ASKS FOR approved, RATHER THAN EXCLUDING pending. v0.13.5 split the statuses and both
        # `paused` and `disabled` are unsendable; a denylist would let each new one through.
        query = urllib.parse.urlencode({"tenant": tenant, "status": "approved", "limit": 200})
        try:
            out = internal_http.get_json(f"{self._url}?{query}", self._token, self._timeout)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError):
            return None
        rows = out.get("templates")
        if rows is None:
            return None
        return {str(r.get("name")) for r in rows if r.get("name")}

    async def statuses(self, tenant: str) -> dict[str, str] | None:
        """Every one of this tenant's templates, by name, with Meta's OWN status word —
        pending | approved | rejected | paused | disabled. `names()` above collapses all four
        unsendable statuses into "not approved", which is exactly right for choosing what to
        send but wrong for TELLING the owner why: "قوالبك قيد المراجعة" about a template Meta
        actually REJECTED sends him to wait for something that will never resolve on its own.

        `None` means not known — unconfigured or unreachable — never "nothing registered"; a
        caller must not draw "no template exists" from a peer it could not ask.
        """
        if not self._url:
            return None
        import urllib.error
        import urllib.parse
        from app.adapters import internal_http

        # NO `status=` FILTER — every status this tenant's templates carry, in one read, so a
        # caller building a badge per template does not make one request per status to assemble
        # the same picture `names()` gets in one.
        query = urllib.parse.urlencode({"tenant": tenant, "limit": 200})
        try:
            out = internal_http.get_json(f"{self._url}?{query}", self._token, self._timeout)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError):
            return None
        rows = out.get("templates")
        if rows is None:
            return None
        return {str(r.get("name")): str(r.get("status") or "pending")
                for r in rows if r.get("name")}


#: THE ONE OWNER OF "WHAT DOES THIS SHOP-FACING ROW SAY ABOUT ITSELF" — a single status word per
#: TYPE (svc_visit_confirmation, mkt_winback, ...), not per registered NAME. A type has one row
#: per tone (see PlatformLibrary), each its own Meta registration that can be approved on its own
#: schedule — a shop must not be told "still under review" about a type whose masculine tone Meta
#: already approved just because its feminine tone has not caught up. Priority, best answer first:
#: approved (something usable exists) > pending (still with Meta, resolves on its own) > paused
#: (Meta held it for quality — ours to look at) > disabled (Meta removed it — ours to fix) >
#: rejected (Meta refused every tone) > not_registered (never submitted) > not_seeded (not even in
#: our own library — a genuine gap, not a Meta state at all).
_STATUS_PRIORITY = ("approved", "pending", "paused", "disabled", "rejected")


def type_status(template_type: str, *, library: list[dict[str, Any]],
                statuses: dict[str, str] | None) -> str:
    candidates = [r for r in library if r.get("type") == template_type]
    if not candidates:
        return "not_seeded"
    if statuses is None:
        return "unknown"
    names = {str(r.get("name")) for r in candidates if r.get("name")}
    seen = {statuses[n] for n in names if n in statuses}
    if not seen:
        return "not_registered"
    for status in _STATUS_PRIORITY:
        if status in seen:
            return status
    # A status word Meta introduced after this list was written — surfaced rather than hidden
    # behind a guess, so a new one is visible the day it first appears rather than the day
    # somebody notices a badge went quiet.
    return sorted(seen)[0]
