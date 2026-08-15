"""How an establishment runs its branches — the one setting everything about branches reads.

TWO SHAPES, AND A SHOP IS EXACTLY ONE OF THEM.

  central     ONE WhatsApp number for the brand. Branches are places work is recorded at: they
              have names, staff and figures, and every message goes out from the same number the
              customer already knows. This is what is built, and it is the default.

  per_branch  EACH BRANCH HAS ITS OWN NUMBER, and the customer talks to his own branch. Management
              stays central — templates, services, campaigns, apps and the customer list are set
              once and inherited — because the branch owns only two things: the number it sends
              from, and what its staff may see.

THE DEFAULT IS `central`, AND NOT MERELY BECAUSE IT IS SIMPLER. It is the only one whose whole
path exists: credentials, ceiling, templates and consent are all keyed by establishment today. A
new shop landing in a mode whose plumbing is half-built would be a shop we cannot message.

────────────────────────────────────────────────────────────────────────────────────────────────
THE TRANSITION IS ONE-WAY, AND THAT IS HONESTY RATHER THAN STRICTNESS

Going central → per_branch is a decision a growing chain makes once. Going back is not a setting:
a number that entered the Cloud API, templates approved against it, and customers who have saved
their branch's number in their phones — none of that is undone by flipping a field. A switch that
claims to reverse it would be the product lying about the world.

So the reverse is REFUSED HERE, with the sentence that says what to do instead: ask us. Undoing it
is real work (which number survives, what happens to each branch's approvals, who tells the
customers), and work that needs a human decision may not hide behind a toggle.

────────────────────────────────────────────────────────────────────────────────────────────────
AND `per_branch` IS NOT SELLABLE UNTIL ITS PLUMBING EXISTS

`available()` says whether this deployment can honour it at all. While the sending identity is
still per-establishment, the answer is no — and the screen shows the choice, explains it, and does
not offer it. A mode that can be selected and does nothing is the exact defect this codebase keeps
finding: a control with no wire behind it.
"""
from __future__ import annotations

import time
from typing import Any

MODES = "shop_modes"

CENTRAL = "central"
PER_BRANCH = "per_branch"
ALL = (CENTRAL, PER_BRANCH)


class ModeError(Exception):
    """A refusal an owner reads, in his own language."""


class ModeStore:
    """One row per establishment. Absent means `central` — the default is not written at signup.

    NOT WRITTEN AT SIGNUP, deliberately: a row that exists only because somebody registered says
    nothing, and every shop that never chose would carry a record of a decision it never made.
    Absence IS the default, and the first write is the first real choice.
    """

    def __init__(self, store: Any) -> None:
        self._s = store

    async def get(self, tenant: str) -> dict[str, Any]:
        row = await self._s.get(MODES, tenant) if tenant else None
        return {"mode": str((row or {}).get("mode") or CENTRAL),
                "chosen_at": int((row or {}).get("chosen_at") or 0)}

    async def set(self, tenant: str, mode: str, *, available: bool) -> dict[str, Any]:
        """Move this establishment to `mode`, or refuse and say why.

        EVERY REFUSAL NAMES ITS REASON, because the three are different acts for the owner: an
        unknown value is our bug, a locked mode is a wait, and the reverse direction is a phone
        call.
        """
        if mode not in ALL:
            raise ModeError("نظام الفروع غير معروف.")
        current = (await self.get(tenant))["mode"]
        if mode == current:
            return await self.get(tenant)
        if mode == CENTRAL:
            raise ModeError(
                "لا يمكن الرجوع إلى الإدارة المركزية من الشاشة — أرقام الفروع وقوالبها المعتمدة "
                "وعملاؤها لا تُلغى بضغطة. تواصل معنا ونكمل معك.")
        if not available:
            raise ModeError("إدارة الفروع المستقلة لم تُفعَّل بعد. سنبلغك حين تجهز.")
        await self._s.put(MODES, tenant,
                          {"id": tenant, "tenant": tenant, "mode": mode,
                           "chosen_at": int(time.time())})
        return await self.get(tenant)
