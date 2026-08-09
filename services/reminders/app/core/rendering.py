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
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# A blank {{1}} is a Meta rejection at send time. This is what goes in instead.
FALLBACK_NAME = "عميلنا العزيز"

MAX_OWNER_FIELD = 60

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


def choose(*, template_type: str, tone: str, library: list[dict[str, Any]]) -> dict[str, Any]:
    """Pick the template for this type in this tenant's tone.

    FALLS BACK TO ANY ACTIVE TONE rather than failing. A tenant whose tone was set to one we later
    retired would otherwise stop sending entirely — a configuration mismatch becoming a silent
    outage, which is the shape this codebase keeps finding.
    """
    active = [t for t in library if t.get("type") == template_type and t.get("active", True)]
    if not active:
        raise RenderError(f"لا يوجد قالب فعّال من نوع {template_type}.")
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
        if source == "owner":
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
