"""A shop owner's own notes for the WhatsApp AI assistant — hours, policies, service details he
wants the bot to mention that nothing else on the platform already knows.

ABSENT MEANS EMPTY, same discipline as `vehicles.py`: a row exists only because an owner wrote
something, never because he registered.

WHY THIS IS NOT `sanitise_owner_text` (reminders/app/core/rendering.py). That function is built for
a WhatsApp TEMPLATE VARIABLE — one line, no URL, no phone number, because the text is substituted
into an already-approved message a customer reads verbatim. This is different: real instructions
for an AI need paragraphs, and a shop plausibly needs to write "نفتح من السبت للخميس" or mention a
service by name — a blanket phone/URL ban here would reject exactly the kind of concrete detail the
field exists for. So this module has its own, narrower policy: a length cap and a control-character
ban (never a formatting concern, only ever a payload-shape one), plus something `sanitise_owner_text`
does not need at all — mandatory PII redaction, because this text is not read by a human, it is
merged into a prompt sent to a model that may be hosted outside the Kingdom.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any

from app.core.redaction import Redacted, redact

AI_NOTES = "shop_ai_notes"

#: SAME FAMILY AS reminders/app/core/rendering.py's own `_CONTROL` — invisible control characters
#: and RTL/LTR override marks have no legitimate place in typed prose, only in an attempt to make
#: text read differently than it displays. DELIBERATELY NARROWER than that copy: `\n`/`\r` (0x0A,
#: 0x0D) are excluded on purpose — that field bans them because it fills a single-line template
#: variable; this one is paragraphs of real instructions, and rejecting a newline here would reject
#: the one thing that makes the field usable.
_CONTROL = re.compile(r"[\x00-\x09\x0b\x0c\x0e-\x1f\x7f​-‏‪-‮]")

#: The same bound is enforced twice more downstream (`whatsapp-assistant/core/conversation.py`, at
#: merge time) — this is the FIRST enforcement, at write time, so an owner who exceeds it learns
#: immediately rather than discovering his tail was silently dropped months later.
MAX_AI_NOTES = 2000


class AiNotesError(Exception):
    """A refusal the owner can act on."""


@dataclass
class SanitisedNotes:
    text: str
    hits: tuple[str, ...]


def sanitise(value: str) -> SanitisedNotes:
    """Validate then redact. CLEARING TO EMPTY IS A VALID ANSWER — unlike a template variable,
    which must never be blank, an owner emptying this field is "I have nothing to add", not an
    error."""
    v = (value or "").strip()
    if v:
        if _CONTROL.search(v):
            raise AiNotesError("النص يحتوي رموزاً غير مرئية — احذفها وأعد الكتابة.")
        if len(v) > MAX_AI_NOTES:
            raise AiNotesError(f"النص أطول من {MAX_AI_NOTES} حرفاً — اختصره.")
    cleaned: Redacted = redact(v, enabled=True, max_chars=MAX_AI_NOTES)
    return SanitisedNotes(text=cleaned.text, hits=cleaned.hits)


class AiNotesStore:
    """One row per establishment. Absent means «no notes», which is most shops."""

    def __init__(self, store: Any) -> None:
        self._s = store

    async def get(self, tenant: str) -> str:
        if not tenant:
            return ""
        try:
            row = await self._s.get(AI_NOTES, tenant)
        except Exception:                                                    # noqa: BLE001
            # UNREADABLE IS «NOTHING TO ADD», never a 500 that would stop a shop's own screen from
            # loading over a field that is, worst case, decorative — same asymmetry as
            # VehicleStore.tracks_vehicle's own fail-to-the-harmless-answer.
            return ""
        return str((row or {}).get("text") or "")

    async def set(self, tenant: str, text: str) -> dict[str, Any]:
        row = {"tenant": tenant, "text": text, "updated_at": int(time.time())}
        await self._s.put(AI_NOTES, tenant, row)
        return row
