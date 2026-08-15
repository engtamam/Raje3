"""«ساعدوني» — one button that turns Meta's refusal into a request a human answers.

THE DECISION THIS COMPLETES, in the owner's words: «الفاحص الالي الغيه، ما راح نسوي اي فاحص، هو
يقرر ونحط ميزة ساعدوني». We removed ourselves from between him and Meta on purpose. The cost of
that decision is that a refusal arrives in English, from a reviewer he cannot reach, about a rule
he has never read — and the shape that follows is always the same: he edits a word, submits again,
is refused again, and after the third time he stops using the feature and tells us the product does
not work.

SO THE REFUSAL IS THE ENTRY POINT, not a dead end. One press attaches Meta's exact sentence, his
text, and the reason it was for, to a queue we answer. He does not have to describe the problem,
find a support channel, or quote an error — all three are things a shop owner in the middle of a
working day will simply not do.

WHAT IS STORED AND WHY EACH FIELD EARNS ITS PLACE:

  · `reason` — META'S OWN WORDS, copied from the submission. Whoever answers has to see what the
    reviewer actually said, not our paraphrase of it.
  · `body` — the text AS HE WROTE IT, frozen at the moment of asking. He will keep editing the
    draft while he waits, and answering a question about a text that has since changed is how
    support ends up arguing with a customer about what he typed.
  · `note` — his own sentence, optional. Often the most useful field: «أبغى أقول له إن الخصم
    للفرع الجديد فقط» explains an intent no rejection text carries.

ONE OPEN REQUEST PER TEMPLATE. Pressing twice must not open two tickets — he presses again because
nothing visible happened, which is the most human thing on this screen, and a queue that grows a
row each time punishes him for our silence.
"""
from __future__ import annotations

import time
from typing import Any

HELP = "template_help"

OPEN = "open"
ANSWERED = "answered"


class HelpRequestError(Exception):
    """A refusal an owner reads, in his own language."""


class HelpRequestStore:
    def __init__(self, store: Any) -> None:
        self._s = store

    @staticmethod
    def _key(tenant: str, name: str) -> str:
        # ONE PER TEMPLATE, and the key IS that rule — not a uniqueness check somewhere that a
        # concurrent second press could slip past.
        return f"{tenant}:{name}"

    async def list(self, tenant: str = "", *, status: str = "") -> list[dict[str, Any]]:
        """His own, or — for the platform queue — everybody's.

        AN EMPTY TENANT MEANS EVERY SHOP, and that is only ever reachable from a `platform.*`
        route. It is written here rather than at the caller so the two readings of "no tenant"
        cannot drift apart.
        """
        rows = await self._s.list(HELP)
        out = [r for r in rows if not tenant or r.get("tenant") == tenant]
        if status:
            out = [r for r in out if r.get("status") == status]
        return sorted(out, key=lambda r: int(r.get("asked") or 0), reverse=True)

    async def get(self, tenant: str, name: str) -> dict[str, Any] | None:
        return await self._s.get(HELP, self._key(tenant, name))

    async def ask(self, tenant: str, *, name: str, reason_id: str, body: str,
                  refusal: str, note: str = "") -> dict[str, Any]:
        """Open a request, or return the one already open for this text.

        RETURNS THE EXISTING ROW RATHER THAN REFUSING. A second press is not an error he needs to
        read about — it is a man checking whether the first one worked. He gets the same answer
        either way, and we get one ticket.
        """
        now = int(time.time())
        existing = await self.get(tenant, name)
        if existing and existing.get("status") == OPEN:
            # HIS NEWER NOTE IS KEPT, because a second press usually carries a better explanation
            # than the first — but the refusal and the body stay frozen as they were.
            if note:
                existing["note"] = note[:600]
                existing["updated"] = now
                await self._s.put(HELP, self._key(tenant, name), existing)
            return existing

        row = {
            "tenant": tenant, "name": name, "reason_id": reason_id,
            # FROZEN AT THE MOMENT OF ASKING — he keeps editing the draft while he waits.
            "body": body[:1024], "refusal": refusal[:600], "note": note[:600],
            "status": OPEN, "asked": now, "updated": now, "answer": "",
        }
        await self._s.put(HELP, self._key(tenant, name), row)
        return row

    async def answer(self, tenant: str, name: str, *, answer: str) -> dict[str, Any]:
        """Ours, from the platform panel. Closes the request and keeps what was said.

        KEPT, NOT DELETED. The next shop refused for the same rule is answered from this row, and
        a queue that empties itself teaches us nothing about which rule keeps catching people.
        """
        row = await self.get(tenant, name)
        if row is None:
            raise HelpRequestError("لا يوجد طلب مساعدة بهذا الاسم.")
        row["status"] = ANSWERED
        row["answer"] = answer[:1200]
        row["updated"] = int(time.time())
        await self._s.put(HELP, self._key(tenant, name), row)
        return row
