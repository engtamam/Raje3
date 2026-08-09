"""The weekly message — the only report most owners will ever read.

MOST OWNERS WILL NEVER OPEN A DASHBOARD. That is not a criticism of them; they are running a shop.
So the highest-leverage surface this service has is not the panel, it is a message that arrives
where they already are — which makes this small file more consequential than the eleven indicators
behind it.

THREE OR FOUR NUMBERS AND ONE THING TO DO. Not eleven. An owner who receives a wall of figures
stops opening the message, and then the one week it actually matters he does not see it either. The
discipline that makes this work is refusing to add the fifth number.

IT GOES THROUGH REMINDERS' GATE like everything else. No second send path, no exception — the same
rule that governs campaigns and loyalty, for the same reason: a second path is a second set of
rules and the second one is always missing a check.

AND IT IS A SERVICE MESSAGE, NOT MARKETING. It is the shop's own operational report about its own
business, sent to its own owner. Classing it as marketing would put a business report behind a
consent the owner never thought to give himself, and he would conclude the feature is broken.

IT MUST DEGRADE TO SILENCE. A week with no snapshot sends NOTHING rather than a message full of
zeros — "0 visits, 0 customers" reads as "your shop is dead", and it is our failure being reported
as his.
"""
from __future__ import annotations

from typing import Any

# A service-class template: the shop's own report to its own owner (spec §8.4.1).
TEMPLATE = "per_weekly_digest"


def build(*, snapshot: dict, previous: dict | None = None) -> dict[str, Any] | None:
    """The message, or None when there is nothing honest to send.

    None is returned — never an empty message and never a zeroed one. See the module docstring:
    silence is the correct output for a week we could not compute.
    """
    if not snapshot:
        return None
    values = snapshot.get("values") or {}
    visits = int(snapshot.get("visits") or 0)
    if not visits:
        return None

    prev_visits = int((previous or {}).get("visits") or 0)
    at_risk = list(values.get("at_risk") or [])

    lines = [f"زياراتك هذا الأسبوع: {visits}"]
    if prev_visits:
        delta = visits - prev_visits
        # The SIGN is the point, and the direction is spelled out rather than left to a symbol —
        # a bare minus in a message read on a phone at speed is easy to miss.
        word = "أكثر من" if delta > 0 else "أقل من"
        if delta:
            lines.append(f"{abs(delta)} {word} الأسبوع الماضي")
    if at_risk:
        lines.append(f"{len(at_risk)} عميلاً تأخّروا عن موعدهم")

    return {
        "text": "\n".join(lines),
        "visits": visits,
        "at_risk": len(at_risk),
        # ONE action, and it links into campaigns rather than into a dashboard. A report that ends
        # in "open the panel to see more" ends in nothing.
        "action": ("send_winback" if at_risk else ""),
        "action_label": (f"أرسل لهم" if at_risk else ""),
        "template_type": TEMPLATE,
        "cls": "service",
    }


class Subscriptions:
    """Who receives it — PER PERSON, not per establishment.

    A manager may want the weekly report and the owner may not, and one flag on the establishment
    forces them to agree. Per person also means unsubscribing is a personal act rather than one
    that silently switches the feature off for a colleague.
    """

    def __init__(self, store: Any) -> None:
        self.store = store

    async def set(self, tenant: str, subject: str, *, on: bool) -> dict:
        from app.core.models import SUBSCRIPTIONS

        key = f"{tenant}|{subject}"
        row = {"id": key, "key": key, "tenant": tenant, "subject": subject, "on": bool(on)}
        await self.store.put(SUBSCRIPTIONS, key, row)
        return row

    async def recipients(self, tenant: str) -> list[str]:
        from app.core.models import SUBSCRIPTIONS

        rows, _ = await self.store.find(SUBSCRIPTIONS, {"tenant": tenant}, limit=200,
                                        sort=("id", "asc"))
        return [r["subject"] for r in (rows or []) if r.get("on")]
