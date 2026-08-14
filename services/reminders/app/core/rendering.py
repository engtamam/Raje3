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
  code        a coupon code, one per customer, machine-made.
  date        the day an offer ends, phrased by us.

THE LAST THREE ARE TYPED, AND THAT IS THE WHOLE POINT. They used to be `owner` free text, which
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

# A blank {{1}} is a Meta rejection at send time. This is what goes in instead.
FALLBACK_NAME = "عميلنا العزيز"

MAX_OWNER_FIELD = 60

# ── the shapes the typed slots accept ────────────────────────────────────────────────────────
# WESTERN DIGITS ONLY, here as everywhere: Arabic-Indic digits render inconsistently across the
# phones our customers actually hold, and a discount nobody can read is worse than no discount.
_AMOUNT = re.compile(r"^(?:(?:[1-9][0-9]?|90)%|[0-9]{1,6}(?:\.[0-9]{1,2})? ريال)$")
# Uppercase Latin and digits, hyphen-separated. Not a free string: the code is read aloud at a
# till and typed back by somebody who is not looking at the message.
_CODE = re.compile(r"^[A-Z0-9]{2,8}(?:-[A-Z0-9]{2,8})?$")

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
           approved: set[str] | None = None) -> dict[str, Any]:
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

    for t in active:
        if t.get("tone") == tone:
            return t
    return active[0]


def render(*, template: dict[str, Any], system: dict[str, str],
           catalogue: dict[str, str], owner: dict[str, str]) -> Rendered:
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
        if source == "amount":
            value = (system.get(key) or "").strip()
            if not _AMOUNT.fullmatch(value):
                raise RenderError(
                    f"قيمة الخصم «{value}» غير مقبولة — اكتبها نسبةً مثل 20% أو مبلغاً مثل "
                    f"50 ريال.")
            out.append(value)
        elif source == "code":
            value = (system.get(key) or "").strip()
            if not _CODE.fullmatch(value):
                # NOT AN OWNER MISTAKE. We generate this one, so a bad shape is our defect and the
                # message must stop rather than carry a code the till will not recognise.
                raise RenderError(f"رمز القسيمة «{value}» غير صالح.")
            out.append(value)
        elif source == "date":
            value = (system.get(key) or "").strip()
            if not value:
                # AN OFFER WITHOUT AN END IS AN OFFER FOR EVER, and the shop honours it at the
                # till long after it meant to stop. Refusing the send is the cheaper failure.
                raise RenderError("العرض بلا تاريخ انتهاء — لا تُرسَل رسالة تعِد بخصمٍ بلا نهاية.")
            out.append(value)
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
            out.append(value)

    return Rendered(template.get("name", ""), template.get("type", ""),
                    template.get("class", "service"), out)


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
        import urllib.request

        # ASKS FOR approved, RATHER THAN EXCLUDING pending. v0.13.5 split the statuses and both
        # `paused` and `disabled` are unsendable; a denylist would let each new one through.
        query = urllib.parse.urlencode({"tenant": tenant, "status": "approved", "limit": 200})
        req = urllib.request.Request(f"{self._url}?{query}",
                                     headers={"X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                out = json.loads(resp.read() or b"{}")
        except (urllib.error.HTTPError, urllib.error.URLError, OSError):
            return None
        rows = out.get("templates")
        if rows is None:
            return None
        return {str(r.get("name")) for r in rows if r.get("name")}
