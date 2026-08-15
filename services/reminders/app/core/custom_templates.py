"""The shop's own texts — written by him, approved by Meta, never edited by us.

THE DECISION BEHIND THIS FILE, in the owner's words: «هو يقرر ونحط ميزة ساعدوني». There is no
review of ours between him and Meta. He classifies his own message, submits it on his own number,
and Meta is the judge; when it refuses, one button turns the refusal into a request for help
instead of ten more attempts.

WHAT WE STILL OWE HIM, and it is the whole of this file:

  · a NAME he never sees and never has to invent — Meta freezes it at approval, so it is generated
    and never reused;
  · a check that the blanks he used are ones his reason can actually fill, because a template
    asking for a coupon code inside a visit confirmation renders nothing and fails at send, once,
    silently, weeks later;
  · a version chain, so editing an approved text is a NEW submission while the old one keeps
    sending — «ما نحذف معتمَداً أبداً، ولا نوقف الإرسال أثناء المراجعة».

WHAT WE DO NOT KEEP. The approved body lives in his WhatsApp account under its name; what is
stored here is the draft, its status and its history. The send path reads the name.

AND THE PLAN COUNTER IS SPENT AT SUBMISSION, not at draft. A draft costs nobody anything and a
shop should be able to write, read it back on a phone-shaped preview, and throw it away. What is
metered is what we hand to Meta.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any

from app.core import reasons as T

CUSTOM = "custom_templates"

# The states, and they are Meta's rather than ours — except `draft`, which is his alone.
DRAFT = "draft"
PENDING = "pending"        # handed to Meta, waiting on a human there
APPROVED = "approved"
REJECTED = "rejected"
RETIRED = "retired"        # replaced by a newer version of the same text; never deleted

MAX_BODY = 1024            # Meta's own body limit
_VAR = re.compile(r"\{\{(\d+)\}\}")
# Refused for the same reason the owner's free-text field is (rendering.sanitise_owner_text): a
# link inside a template Meta approved is a carrier for something nobody approved, and it goes out
# under the shop's name against our quality rating.
_URL = re.compile(r"(https?://|www\.|\b[a-z0-9-]+\.(com|net|org|sa|io|co)\b)", re.I)
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


class CustomTemplateError(Exception):
    """A refusal in words the owner can act on."""


@dataclass
class CustomTemplate:
    tenant: str
    reason_id: str
    body: str
    # HIS ANSWER, NOT OUR ANALYSIS. We ask one question — «متى تُرسَل؟» — and store what he says.
    # The class decides consent, the window and the monthly cap, and Meta re-categorises whatever
    # we get wrong.
    cls: str = "service"
    name: str = ""
    version: int = 1
    status: str = DRAFT
    reason: str = ""           # Meta's own words when it refuses — carried, never re-worded
    variables: list[int] = field(default_factory=list)
    # What each blank MEANS, in position order — the send fills by this, never by the number.
    fills: list[str] = field(default_factory=list)
    created: int = 0
    updated: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.name, "tenant": self.tenant, "name": self.name,
                "reason_id": self.reason_id, "body": self.body, "cls": self.cls,
                "version": self.version, "status": self.status, "reason": self.reason,
                "variables": list(self.variables), "fills": list(self.fills),
                "created": self.created, "updated": self.updated}

    def public(self) -> dict[str, Any]:
        """What his screen reads. The name is included because «رسائلي» must be able to point a
        reason at it — it is an identifier, not vocabulary he has to understand."""
        return {"name": self.name, "reason_id": self.reason_id, "body": self.body,
                "fills": list(self.fills),
                "status": self.status, "reason": self.reason, "version": self.version,
                "updated": self.updated}


def slugify(tenant: str) -> str:
    """A Meta-legal name fragment: lowercase, digits and underscores, and nothing else.

    Meta refuses a name outside that alphabet, and the refusal arrives hours later against a name
    that then cannot be reused — so it is enforced here rather than discovered there.
    """
    out = re.sub(r"[^a-z0-9]+", "_", tenant.lower()).strip("_")
    return out[:24] or "shop"


def check(body: str, reason_id: str, fills: list[str]) -> list[int]:
    """Refuse now what Meta would refuse tomorrow, and what our own renderer would refuse today.

    `fills` IS WHAT EACH BLANK MEANS, in position order — «اسم العميل» then «الخدمة», say. It is
    not derived from the text and cannot be: Meta numbers blanks and names nothing, so `{{2}}` is
    the customer's name in one template and the service in another. The editor knows, because he
    inserted a chip; the number is ours to generate and the meaning is what travels.

    Returns the numbers used, so the caller stores what was validated rather than re-deriving it
    somewhere else and getting a different answer.
    """
    text = (body or "").strip()
    if not text:
        raise CustomTemplateError("النص فارغ.")
    if len(text) > MAX_BODY:
        raise CustomTemplateError(f"النص أطول من {MAX_BODY} حرفاً.")
    if _URL.search(text):
        raise CustomTemplateError(
            "لا يمكن وضع رابط داخل الرسالة — واتساب يرفضه، ويُحسب على تقييم رقمك.")
    if _CONTROL.search(text):
        raise CustomTemplateError("النص يحتوي رموزاً غير مقروءة.")

    numbers = sorted({int(n) for n in _VAR.findall(text)})
    if numbers and numbers != list(range(1, len(numbers) + 1)):
        # Meta refuses a gap at submission and blames the wording, hours later. The editor numbers
        # the chips itself, so a gap here means something rewrote the body by hand.
        raise CustomTemplateError("ترقيم الفراغات فيه فجوة — ابدأ من الأول بلا تخطٍّ.")

    reason = T.get(reason_id)
    if reason is None:
        raise CustomTemplateError("لا يوجد داعٍ للإرسال بهذا الاسم.")
    if not reason.owner_can_retext:
        raise CustomTemplateError(f"«{reason.label}» يُرسَل بصياغتنا — نصّه مرتبط بحقٍّ نظامي.")

    if len(fills) != len(numbers):
        raise CustomTemplateError(
            f"النص فيه {len(numbers)} فراغاً و{len(fills)} معنى — لكل فراغ معناه.")

    # THE FAILURE THIS WHOLE CHECK EXISTS FOR. A blank this reason cannot fill renders nothing,
    # and the send fails once, for one shop, weeks later — after Meta approved the text.
    allowed = set(T.slots_for(reason_id))
    unknown = [f for f in fills if f not in allowed]
    if unknown:
        raise CustomTemplateError(
            f"«{reason.label}» لا يعرف «{unknown[0]}» — اختر من الفراغات المتاحة له.")
    return numbers


class CustomTemplateStore:
    def __init__(self, store: Any) -> None:
        self._s = store

    async def list(self, tenant: str, *, reason_id: str = "") -> list[dict[str, Any]]:
        where: dict[str, Any] = {"tenant": tenant}
        if reason_id:
            where["reason_id"] = reason_id
        rows, _ = await self._s.find(CUSTOM, where, limit=200, sort=("updated", "desc"))
        return rows

    async def get(self, tenant: str, name: str) -> dict[str, Any] | None:
        row = await self._s.get(CUSTOM, name)
        # TENANT-CHECKED ON READ, not only on write. The name is global at Meta and guessable by
        # shape (`nakheel_service_due_2`), so a row is only ever returned to the shop that owns it.
        if not row or row.get("tenant") != tenant:
            return None
        return row

    async def draft(self, tenant: str, *, reason_id: str, body: str, fills: list[str],
                    cls: str = "service", replaces: str = "") -> CustomTemplate:
        """Write a new text, or a new VERSION of one Meta already approved.

        A NEW NAME EVERY TIME, and this is not caution — Meta freezes a name at approval and
        editing it sends it back for review. Reusing it would take the shop's messages off the air
        for a day over one word. So the old text keeps sending until the new one is approved.
        """
        numbers = check(body, reason_id, list(fills))
        now = int(time.time())
        version = 1
        if replaces:
            previous = await self.get(tenant, replaces)
            if previous is None:
                raise CustomTemplateError("لا يوجد نصّ سابق بهذا الاسم.")
            version = int(previous.get("version") or 1) + 1

        name = f"{slugify(tenant)}_{reason_id}_{version}"
        row = CustomTemplate(
            tenant=tenant, reason_id=reason_id, body=body.strip(), cls=cls,
            name=name, version=version, status=DRAFT, variables=numbers,
            fills=list(fills), created=now, updated=now)
        await self._s.put(CUSTOM, name, row.to_dict())
        return row

    async def mark(self, tenant: str, name: str, *, status: str, reason: str = "") -> dict:
        """Record what happened to it — submitted, approved, refused.

        THE REASON IS META'S OWN WORDS. Re-wording a rejection would send the owner looking for a
        problem we invented; «ساعدوني» carries the original into a request we answer.
        """
        row = await self.get(tenant, name)
        if row is None:
            raise CustomTemplateError("لا يوجد نصّ بهذا الاسم.")
        row["status"] = status
        row["reason"] = reason[:300]
        row["updated"] = int(time.time())
        await self._s.put(CUSTOM, name, row)
        # A NEW APPROVAL RETIRES THE VERSION IT REPLACES — never deletes it. The send log points at
        # a template name, and a receipt must not restate itself when the wording changes.
        if status == APPROVED:
            for other in await self.list(tenant, reason_id=row.get("reason_id", "")):
                if other.get("name") != name and other.get("status") == APPROVED:
                    other["status"] = RETIRED
                    other["updated"] = int(time.time())
                    await self._s.put(CUSTOM, other["name"], other)
        return row
