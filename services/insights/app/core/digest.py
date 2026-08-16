"""The weekly message — the only report most owners will ever read.

MOST OWNERS WILL NEVER OPEN A DASHBOARD. That is not a criticism of them; they are running a shop.
So the highest-leverage surface this service has is not the panel, it is a message that arrives
where they already are — which makes this small file more consequential than the eleven indicators
behind it.

EIGHT LINES AT MOST, ONE NUMBER EACH, AND ONE THING TO DO. Read in ten seconds on a phone, and the
discipline that makes it work is the line nobody adds.

Two of them are alternatives rather than additions: a shop that cannot send offers yet gets the
audience it already has, and a shop that can gets the relationship we found. Nobody gets both, so
the message stays the same length whatever he has bought.

THE REPORT TELLS; THE PANEL SELLS — and that line is what keeps this message PERSONAL class, not
marketing: it is the shop's own report to its own owner, with no price and no invitation to buy.

The last line states a finding about HIS shop: "we found 4 relationships between your services, the
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

# A personal-class template: the shop's own report to its own owner (spec §8.4.1). The class here
# must match the library's (operations/data/templates.seed.json, and reasons.py's own claim for
# this same template_type) — ci/check_template_fills.py compares all three.
TEMPLATE = "per_weekly_digest"

# THE CEILING THE CALLEE ENFORCES, held here too. reminders declares the same number as
# OWNER_TEXT_MAX on `CampaignSendIn.owner_text`; if the two ever disagree the disagreement is
# silent — a 422 the caller converts into «not sent» and the route counts as zero.
OWNER_TEXT_MAX = 700

# THE SEPARATOR BETWEEN LINES, DELIBERATELY NOT "\n" (ح-5). This text travels as one WhatsApp
# template parameter and Meta refuses a submission whose parameter contains a real newline —
# the reminders-side sanitiser never runs on this field (it is written for the owner's own
# hand-typed text, not for text we compose ourselves), so a "\n"-joined report failed at Meta
# with nobody watching. A middle dot reads as a list on one line rather than eight, which is a
# worse layout than a line break — but a report the owner can read beats one that never arrives.
SEP = " · "


def _line(label: str, value: Any) -> str:
    return f"{label}: {value}"


def build(*, snapshot: dict, previous: dict | None = None,
          messages_sent: int = 0, ceiling_missed: int = 0,
          points_redeemed: int = 0, consented: int = 0,
          can_campaign: bool = True, shop: str = "") -> dict[str, Any] | None:
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

    # 6 · WHAT HE SENT, not what he has left. We do not sell messages — Meta bills him directly
    #     (spec §16.7) — so a "balance" here would be a balance of nothing, and the first time he
    #     compared it to his Meta invoice he would stop trusting both numbers.
    #
    #     It is still worth a line: it is the only place he sees the volume his shop generates
    #     without opening anything, and it is what makes his own bill explicable.
    if messages_sent:
        lines.append(_line("رسائل أرسلتها", messages_sent))

    # 6b · WHAT HIS CEILING COST HIM, and it is a line rather than a message of its own.
    #
    #      A separate WhatsApp notice was designed and dropped: a notice to the owner is itself a
    #      business-initiated message, out of the SAME ceiling and onto the SAME bill, and it would
    #      be sent at exactly the moment there is none left. This report is already going out, so
    #      the line costs nothing — no extra send, no extra unit, no extra riyal.
    #
    #      AND ONLY IN A WEEK IT ACTUALLY BIT. A shop that never touched its ceiling gets no line;
    #      a limit that has cost him nothing is not news about his shop.
    if ceiling_missed:
        lines.append(_line("لم تصلهم رسائلك (حد واتساب)", ceiling_missed))

    # 7 · the loyalty programme, for shops that have one. Absent otherwise — a shop without points
    #     must not see an empty points line (spec §8.6.1).
    if points_redeemed:
        lines.append(_line("نقاط استُبدلت", points_redeemed))

    # 8 · THE AUDIENCE HE ALREADY HAS, for a shop that cannot send offers yet. Customers who
    #     explicitly agreed, sitting there while he has no way to reach them — a fact about his own
    #     business in the same column as the rest, with no price and no invitation.
    #
    #     ONLY HONEST BECAUSE CONSENT IS NOW EXPLICIT. Counted from refusals, as it would have been
    #     a week ago, this was every customer he had.
    if consented and not can_campaign:
        lines.append(_line("وافقوا على استقبال عروضك", consented))

    # 9 · A FINDING ABOUT HIS SERVICES. Reaches the owner who bought the engine and the one who did
    #     not, identically: the first opens it and reads the pairs, the second opens it and finds
    #     the card. No price, no plan, no invitation — see the module docstring.
    assoc = values.get("associations") or {}
    pairs = [p for p in (assoc.get("pairs") or []) if p.get("verdict") in ("real", "temporal")]
    if pairs:
        biggest = max(pairs, key=lambda p: int(p.get("customers") or 0))
        if int(biggest.get("customers") or 0):
            lines.append(f"وجدنا {len(pairs)} ترابطات بين خدماتك، "
                         f"أكبرها يشمل {biggest['customers']} عميلاً")

    header = f"أسبوعك في {shop}" if shop else "أسبوعك"
    # BOUNDED HERE, WHERE A LINE CAN STILL BE DROPPED WHOLE.
    #
    # reminders caps `owner_text` — the field this text is posted as — and the cap was written for a
    # campaign's one-liner. A full week runs past it, FastAPI answered 422, the caller turned that
    # into {"sent": false} and the route counted it as nothing: the shops with the MOST to report
    # were exactly the ones whose report never arrived, silently, every week.
    #
    # The cap is raised on both sides, and the text is trimmed here as well — by whole lines, from
    # the end, never mid-sentence. A report that stops in the middle of a number is worse than a
    # report missing its last line, and the lines are already written most-important-first.
    #
    # JOINED WITH SEP, NOT A REAL NEWLINE — see SEP's own comment above (ح-5).
    while lines and len(header) + 1 + len(SEP.join(lines)) > OWNER_TEXT_MAX:
        lines.pop()
    return {
        "text": header + SEP + SEP.join(lines),
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
        # THE LIBRARY, NOT A GUESS REPEATED HERE. `per_weekly_digest` is filed as `personal` in
        # the platform library (operations/data/templates.seed.json) — the module docstring above
        # argues for exactly that: a report with no price and no invitation is not a service
        # notice. This constant used to say "service" instead, which is a different regulatory
        # class with its own daily cap and its own service-message ceiling — so every digest quietly
        # spent budget meant for confirmations and receipts, on a message the library never classed
        # that way.
        "cls": "personal",
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

    async def state_for(self, tenant: str, subject: str) -> bool | None:
        """Is THIS person subscribed? `None` means «never decided», which is not «off».

        WHY IT HAS TO BE THREE STATES. The switch on «محلّي» was `useState(true)` — hardcoded on,
        because nothing could read this back. An owner who turned the weekly report off saw it ON
        again the moment he reopened the screen, and a second tap turned it… off again, or on,
        depending on what he believed. A control that does not report its own position is not a
        control; it is a button that argues with the person pressing it.

        `None` lets the screen show the DEFAULT honestly (subscribed, which is what a new owner
        gets) without claiming to have read a decision he never made.
        """
        from app.core.models import SUBSCRIPTIONS

        row = await self.store.get(SUBSCRIPTIONS, f"{tenant}|{subject}")
        return None if row is None else bool(row.get("on"))

    async def recipients(self, tenant: str) -> list[str]:
        from app.core.models import SUBSCRIPTIONS

        rows, _ = await self.store.find(SUBSCRIPTIONS, {"tenant": tenant}, limit=200,
                                        sort=("id", "asc"))
        return [r["subject"] for r in (rows or []) if r.get("on")]
