"""What THIS shop decided about each trigger: does it run, and in whose words.

TWO DECISIONS AND NO MORE. Whether a trigger sends at all, and which text answers it — ours or one
of his own that Meta approved. Everything else about a trigger (when it fires, what class it is,
which blanks it can fill) is the product's and is not a per-shop setting.

PRESENCE DECIDES, NOT TRUTH — the same rule the settings tree runs on, and for the same reason it
was written down there: `{"on": False}` read with `or` becomes the default, and the owner who
switched something off watches it keep sending. So an absent key means "he never chose" and takes
the registry's default; a present key is his answer, whatever it says.

ONE ROW PER TENANT. Thirteen small answers read together on every tick — three collections and a
join would be three reads per pass for a dictionary that fits in a log line.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from app.core import triggers as T

CHOICES = "trigger_choices"


@dataclass
class Choices:
    """One establishment's answers, and the registry behind them."""

    tenant: str
    rows: dict[str, dict[str, Any]] = field(default_factory=dict)

    def enabled(self, trigger_id: str) -> bool:
        """Does this trigger send for this shop?

        A TRIGGER HE MAY NOT SWITCH IS ALWAYS ON, whatever is stored. The privacy code answers a
        statutory clock; a row written by a future bug must not be able to silence it.
        """
        t = T.get(trigger_id)
        if t is None:
            # UNKNOWN MEANS ON. A trigger removed from the registry while rows for it are still in
            # the datastore is our mistake, and silently dropping the messages would hide it.
            return True
        if not t.owner_can_switch:
            return True
        row = self.rows.get(trigger_id) or {}
        if "on" in row:
            return bool(row["on"])
        return t.default_on

    def template_name(self, trigger_id: str) -> str:
        """His own approved template for this trigger, or empty for ours.

        A NAME, NOT A BODY. The text lives in his WhatsApp account, approved under this name; a
        copy here would be the version that drifts.
        """
        t = T.get(trigger_id)
        if t is None or not t.owner_can_retext:
            return ""
        return str((self.rows.get(trigger_id) or {}).get("template") or "")

    def public(self) -> list[dict[str, Any]]:
        """The whole registry with his answers folded in — what one screen call returns.

        THE CATALOGUE AND THE ANSWERS TOGETHER, never the answers alone: a screen that had to
        merge them would be a second place the defaults live, and the two would disagree the first
        time a default changed.
        """
        out = []
        for t in T.TRIGGERS:
            row = T.public(t)
            row["on"] = self.enabled(t.id)
            row["template"] = self.template_name(t.id)
            out.append(row)
        return out


class ChoiceStore:
    def __init__(self, store: Any) -> None:
        self._s = store

    async def load(self, tenant: str) -> Choices:
        row = await self._s.get(CHOICES, f"{tenant}|triggers") or {}
        return Choices(tenant=tenant, rows=dict(row.get("triggers") or {}))

    async def set(self, tenant: str, trigger_id: str, *,
                  on: bool | None = None, template: str | None = None) -> Choices:
        """Change one trigger. Everything not named is left exactly as it was.

        REFUSES WHAT THE REGISTRY FORBIDS rather than storing it and ignoring it later. A stored
        setting that does nothing is the shape of every "I turned it off and it kept sending"
        support call this product will ever get.
        """
        t = T.get(trigger_id)
        if t is None:
            raise ValueError(f"لا يوجد محفّز باسم {trigger_id}.")
        if on is not None and not t.owner_can_switch:
            raise ValueError(f"«{t.label}» لا يمكن إيقافه — هو حقٌّ لعميلك لا إعدادٌ لك.")
        if template is not None and not t.owner_can_retext:
            raise ValueError(f"«{t.label}» يُرسَل بصياغتنا — نصّه مرتبط بحقٍّ نظامي.")

        choices = await self.load(tenant)
        row = dict(choices.rows.get(trigger_id) or {})
        if on is not None:
            row["on"] = bool(on)
        if template is not None:
            # EMPTY MEANS "BACK TO OURS", and it is a deletion rather than a stored empty string:
            # an empty value that means "follow" is the copy-versus-inherit mistake the settings
            # tree exists to avoid.
            if template.strip():
                row["template"] = template.strip()
            else:
                row.pop("template", None)
        if row:
            choices.rows[trigger_id] = row
        else:
            choices.rows.pop(trigger_id, None)
        await self._s.put(CHOICES, f"{tenant}|triggers", {
            "id": f"{tenant}|triggers", "tenant": tenant,
            "triggers": choices.rows, "updated": int(time.time())})
        return choices
