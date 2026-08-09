"""The weekly message — the only report most owners will ever read.

MOST OWNERS WILL NEVER OPEN A DASHBOARD. That is not a criticism of them; they are running a shop.
So the highest-leverage surface this service has is not the panel, it is a message that arrives
where they already are — which makes this small file more consequential than the eleven indicators
behind it.

EIGHT LINES, ONE NUMBER EACH, AND ONE THING TO DO. Read in ten seconds on a phone. The discipline
that makes it work is the ninth line nobody adds.

THE REPORT TELLS; THE PANEL SELLS — and that line is what keeps this message SERVICE class.

Line eight states a finding about HIS shop: "we found 4 relationships between your services, the
largest covers 340 customers". It carries no price, no plan name, and no invitation to buy. He
opens it because he is curious about his own business, not because we offered him something.

The moment that line says "upgrade" or names a plan, the whole template becomes promotional — and
then a shop's own operational report sits behind quiet hours, message caps and a consent its owner
never thought to give himself. THE LINE IS IN THE TEXT, NOT IN THE INTENTION. If anyone adds the
word "package" here, this template must be reclassified.

IT GOES THROUGH REMINDERS' GATE like everything else. No second send path, no exception.

IT MUST DEGRADE TO SILENCE. A week with no snapshot sends NOTHING rather than a message of zeros —
"0 visits, 0 customers" reads as "your shop is dead", and it is our failure wearing his numbers.

AND A ZERO LINE IS DROPPED, NOT PRINTED. "New customers: 0" is not information, it is a verdict on
his week — and a message of eight zeros is one he closes and never opens again.
"""
from __future__ import annotations

from typing import Any

# A service-class template: the shop's own report to its own owner (spec §8.4.1).
TEMPLATE = "per_weekly_digest"


def _line(label: str, value: Any) -> str:
    return f"{label}: {value}"


def build(*, snapshot: dict, previous: dict | None = None,
          messages_used: int = 0, messages_limit: int = 0,
          points_redeemed: int = 0, shop: str = "") -> dict[str, Any] | None:
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

    lines: list[str] = []

    # 1 · the pulse, WITH the difference — the difference is what makes it a number rather than a
    #     counter. An owner reads "120" and learns nothing he did not already feel.
    prev_visits = int((previous or {}).get("visits") or 0)
    delta = visits - prev_visits if prev_visits else 0
    if delta:
        sign = "+" if delta > 0 else "−"
        lines.append(_line("الزيارات", f"{visits} ({sign}{abs(delta)})"))
    else:
        lines.append(_line("الزيارات", visits))

    # 2 and 3 · NEW AND RETURNING AS TWO LINES, not one total. A shop growing on new customers
    #     alone is a shop bleeding, and no combined figure shows that.
    nvr = values.get("new_vs_returning") or {}
    if int(nvr.get("new") or 0):
        lines.append(_line("عملاء جدد", nvr["new"]))
    if int(nvr.get("returning") or 0):
        lines.append(_line("عادوا", nvr["returning"]))

    # 4 · THE ONLY LINE THAT ENDS IN AN ACTION, and the reason the message exists.
    at_risk = list(values.get("at_risk") or [])
    if at_risk:
        lines.append(_line("تأخّروا عن موعدهم", len(at_risk)))

    # 5 · what is selling. He knows it by instinct and reads it to be sure — and notices the week
    #     it changes, which is the point.
    pop = list(values.get("service_popularity") or [])
    names = values.get("service_names") or {}
    if pop:
        top = pop[0]
        label = names.get(top.get("service_id"), top.get("service_id", ""))
        if label:
            lines.append(_line("أكثر خدمة", f"{label} ({top.get('count', 0)})"))

    # 6 · THE QUIETEST OUTAGE THIS PRODUCT HAS. Messages run out mid-month, the return engine
    #     stops, and nothing tells him until a customer mentions they stopped hearing from him.
    if messages_limit:
        lines.append(_line("رصيد رسائلك", f"{messages_used} من {messages_limit}"))

    # 7 · the loyalty programme, for shops that have one. Absent otherwise — a shop without points
    #     must not see an empty points line (spec §8.6.1).
    if points_redeemed:
        lines.append(_line("نقاط استُبدلت", points_redeemed))

    # 8 · A FINDING ABOUT HIS SHOP. No price, no plan, no invitation — see the module docstring.
    #     It reaches the owner who has bought the engine and the one who has not, identically: the
    #     first opens it and reads the pairs, the second opens it and finds the card.
    assoc = values.get("associations") or {}
    pairs = [p for p in (assoc.get("pairs") or []) if p.get("verdict") in ("real", "temporal")]
    if pairs:
        biggest = max(pairs, key=lambda p: int(p.get("customers") or 0))
        if int(biggest.get("customers") or 0):
            lines.append(f"وجدنا {len(pairs)} ترابطات بين خدماتك، "
                         f"أكبرها يشمل {biggest['customers']} عميلاً")

    header = f"أسبوعك في {shop}" if shop else "أسبوعك"
    return {
        "text": header + "\n" + "\n".join(lines),
        "lines": len(lines),
        "visits": visits,
        "at_risk": len(at_risk),
        # ONE action, linking into campaigns rather than into a dashboard. A report that ends in
        # "open the panel to see more" ends in nothing.
        #
        # AND THE LINK CARRIES NO CREDENTIAL. The customer's page is reached by a token in a URL
        # because its blast radius is one person's own appointments; an owner's panel holds every
        # customer he has, so a forwarded message must never open it. He signs in — and with a
        # 31-day refresh window that is a few times a year, not weekly.
        "action": "send_winback" if at_risk else "",
        "action_label": "أرسل للمتأخرين" if at_risk else "",
        "action_path": "/campaigns/new?goal=win_back" if at_risk else "",
        "template_type": TEMPLATE,
        "cls": "service",
    }


class Subscriptions:
    """Who receives it — PER PERSON, not per establishment.

    A manager may want the weekly report and the owner may not, and one flag on the establishment
    forces them to agree. Per person also means unsubscribing is a personal act rather than one
    that silently switches the feature off for a colleague.

    THIS IS AN OPTIONAL NOTIFICATION, and the distinction matters. The establishment's MANDATORY
    notices — the WhatsApp connection dropped, the message quota is nearly gone, the subscription
    failed to renew — are not preferences and have no switch: silencing them is silencing an
    outage that stops his shop, which is the same argument that stops a customer silencing his
    service messages (spec §8.4.2).
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
