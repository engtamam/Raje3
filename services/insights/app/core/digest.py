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


def build(*, snapshot: dict, messages_sent: int = 0, ceiling_missed: int = 0,
          points_redeemed: int = 0, consented: int = 0,
          ratings_count: int = 0, ratings_average: float = 0.0, ratings_unhandled: int = 0,
          can_campaign: bool = True, shop: str = "") -> dict[str, Any] | None:
    """The message, or None when there is nothing honest to send.

    None is returned — never an empty message and never a zeroed one. See the module docstring:
    silence is the correct output for a week we could not compute.
    """
    if not snapshot:
        return None
    values = snapshot.get("values") or {}
    # THE SNAPSHOT'S OWN COUNT IS THE DENOMINATOR BEHIND EVERY INDICATOR — the whole feed — and it
    # is used here for exactly one thing: deciding whether the shop has any history at all. It is
    # not printed. See the visits line below.
    if not int(snapshot.get("visits") or 0):
        return None

    lines: list[str] = []
    # THE SAME FACTS, SHAPED FOR THE REPORT FLOW (rating-app-feature.md phase 6b) — one
    # `show_X`/`X_text` pair per section, filled alongside the matching text line below rather
    # than recomputed separately, so the two can never drift apart. Keys match
    # deploy/seed/report-flow.json's own `data` schema exactly; every key is always present
    # (`show_X=False`/`X_text=""` for a section this week has nothing to say about) because a
    # Flow's `flow_action_data` supplies every placeholder the published screen declares, not
    # only the ones with something to show — the `visible` binding is what hides them, not their
    # absence from this dict.
    flow: dict[str, Any] = {}

    # 1 · THE WEEK, AND ONLY THE WEEK (ي-2). This line used to print `snapshot.visits` — the count
    #     over the shop's ENTIRE history — under the heading «أسبوعك» and directly above two lines
    #     computed over 30 days. Three periods, one heading, and the largest number was the one
    #     describing a span nobody chose.
    #
    #     The difference beside it is what makes it a number rather than a counter — an owner reads
    #     "120" and learns nothing he did not already feel. It used to come from a `previous`
    #     snapshot that NO caller ever passed, so «(+15)» never once printed. Both figures now come
    #     from one indicator over one list against one clock.
    #
    #     AND A WEEK WE CANNOT COMPARE PRINTS NO COMPARISON. `previous` is None when the shop's
    #     history does not reach past the earlier window; calling that zero would turn the day he
    #     signed up into growth we take credit for.
    week = values.get("visits_week") or {}
    visits = int(week.get("visits") or 0)
    prev_visits = week.get("previous")
    flow["show_visits"] = bool(visits)
    if visits:
        delta = visits - int(prev_visits) if prev_visits is not None else 0
        if delta:
            sign = "+" if delta > 0 else "−"
            visits_text = f"{visits} ({sign}{abs(delta)})"
        else:
            visits_text = str(visits)
        lines.append(_line("زيارات الأسبوع", visits_text))
        flow["visits_text"] = visits_text
    else:
        flow["visits_text"] = ""

    # 2 and 3 · NEW AND RETURNING AS TWO LINES, not one total. A shop growing on new customers
    #     alone is a shop bleeding, and no combined figure shows that.
    nvr = values.get("new_vs_returning") or {}
    flow["show_new"] = bool(int(nvr.get("new") or 0))
    flow["new_text"] = str(nvr["new"]) if flow["show_new"] else ""
    if flow["show_new"]:
        lines.append(_line("عملاء جدد", nvr["new"]))
    flow["show_returning"] = bool(int(nvr.get("returning") or 0))
    flow["returning_text"] = str(nvr["returning"]) if flow["show_returning"] else ""
    if flow["show_returning"]:
        lines.append(_line("عادوا", nvr["returning"]))

    # 4 · THE ONLY LINE THAT ENDS IN AN ACTION, and the reason the message exists.
    at_risk = list(values.get("at_risk") or [])
    flow["show_at_risk"] = bool(at_risk)
    flow["at_risk_text"] = str(len(at_risk)) if at_risk else ""
    if at_risk:
        lines.append(_line("تأخّروا عن موعدهم", len(at_risk)))

    # 5 · what is selling. He knows it by instinct and reads it to be sure — and notices the week
    #     it changes, which is the point.
    pop = list(values.get("service_popularity") or [])
    names = values.get("service_names") or {}
    flow["show_top_service"] = False
    flow["top_service_text"] = ""
    if pop:
        top = pop[0]
        label = names.get(top.get("service_id"), top.get("service_id", ""))
        if label:
            top_service_text = f"{label} ({top.get('count', 0)})"
            lines.append(_line("أكثر خدمة", top_service_text))
            flow["show_top_service"] = True
            flow["top_service_text"] = top_service_text

    # 6 · WHAT HE SENT, not what he has left. We do not sell messages — Meta bills him directly
    #     (spec §16.7) — so a "balance" here would be a balance of nothing, and the first time he
    #     compared it to his Meta invoice he would stop trusting both numbers.
    #
    #     It is still worth a line: it is the only place he sees the volume his shop generates
    #     without opening anything, and it is what makes his own bill explicable.
    flow["show_messages"] = bool(messages_sent)
    flow["messages_text"] = str(messages_sent) if messages_sent else ""
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
    flow["show_ceiling"] = bool(ceiling_missed)
    flow["ceiling_text"] = str(ceiling_missed) if ceiling_missed else ""
    if ceiling_missed:
        lines.append(_line("لم تصلهم رسائلك (حد واتساب)", ceiling_missed))

    # 7 · the loyalty programme, for shops that have one. Absent otherwise — a shop without points
    #     must not see an empty points line (spec §8.6.1).
    flow["show_points"] = bool(points_redeemed)
    flow["points_text"] = str(points_redeemed) if points_redeemed else ""
    if points_redeemed:
        lines.append(_line("نقاط استُبدلت", points_redeemed))

    # 7b · THE RATING APP'S OWN WEEK, for shops that have it (rating-app-feature.md phase 6).
    #      Absent otherwise — a shop that never bought the rating app must not see an empty
    #      "0/5 (0)" line, same discipline as points above. Two lines, not one: the average tells
    #      him HOW he did, the unhandled count tells him what he still owes a reply — and the
    #      second is dropped on its own when it is zero, because zero unhandled is not news, it is
    #      the state every shop wants and printing it every week is the "eight zeros" defect the
    #      module docstring already warns about.
    flow["show_ratings"] = bool(ratings_count)
    flow["ratings_text"] = f"{ratings_average}/5 ({ratings_count})" if ratings_count else ""
    flow["show_unhandled"] = bool(ratings_count and ratings_unhandled)
    flow["unhandled_text"] = str(ratings_unhandled) if flow["show_unhandled"] else ""
    if ratings_count:
        lines.append(_line("تقييمات الأسبوع", f"{ratings_average}/5 ({ratings_count})"))
        if ratings_unhandled:
            lines.append(_line("بانتظار المعالجة", ratings_unhandled))

    # 8 · THE AUDIENCE HE ALREADY HAS, for a shop that cannot send offers yet. Customers who
    #     explicitly agreed, sitting there while he has no way to reach them — a fact about his own
    #     business in the same column as the rest, with no price and no invitation.
    #
    #     ONLY HONEST BECAUSE CONSENT IS NOW EXPLICIT. Counted from refusals, as it would have been
    #     a week ago, this was every customer he had.
    flow["show_consented"] = bool(consented and not can_campaign)
    flow["consented_text"] = str(consented) if flow["show_consented"] else ""
    if consented and not can_campaign:
        lines.append(_line("وافقوا على استقبال عروضك", consented))

    # 9 · A FINDING ABOUT HIS SERVICES. Reaches the owner who bought the engine and the one who did
    #     not, identically: the first opens it and reads the pairs, the second opens it and finds
    #     the card. No price, no plan, no invitation — see the module docstring.
    assoc = values.get("associations") or {}
    pairs = [p for p in (assoc.get("pairs") or []) if p.get("verdict") in ("real", "temporal")]
    flow["show_associations"] = False
    flow["associations_text"] = ""
    if pairs:
        biggest = max(pairs, key=lambda p: int(p.get("customers") or 0))
        if int(biggest.get("customers") or 0):
            associations_text = (f"وجدنا {len(pairs)} ترابطات بين خدماتك، "
                                 f"أكبرها يشمل {biggest['customers']} عميلاً")
            lines.append(associations_text)
            flow["show_associations"] = True
            flow["associations_text"] = associations_text

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
    # A HEADING WITH NOTHING UNDER IT IS NOT A REPORT. Every line here drops itself when its number
    # is zero, and since the visits line became weekly a quiet week can drop all of them — «أسبوعك
    # في مغسلة النخيل» and nothing else is a message that says only that we sent one.
    if not lines:
        return None
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
        # THE REPORT FLOW'S OWN DATA (rating-app-feature.md phase 6b) — same facts as `lines`
        # above, shaped for `deploy/seed/report-flow.json`'s `${data.*}` placeholders. Trimming
        # (the `while` loop above) only shortens the PLAIN-TEXT teaser; the Flow screen still
        # shows every section that has something to say, regardless of what the text version had
        # to drop for length — the two are sent together on one template (button + body) and are
        # allowed to say slightly different amounts for exactly that reason.
        "flow_action_data": {"header_text": header, **flow},
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
        """Every subscribed subject for this tenant — PAGED to the store's own end, fixed
        2026-09-12 (a real gap a QA audit found): a single `limit=200` page with the cursor
        discarded meant an establishment with more than 200 distinct subscribed subjects (a chain
        with many branch managers, or simply one that accumulated subscribers over time) silently
        and permanently never sent the digest to anyone sorted past the 200th by id — no error,
        no log line, just a normal-looking short list every week. Same paging shape as every other
        "every row, not a screenful" reader in this codebase (e.g. payouts.py's own `_all_commissions`
        in the sibling affiliate-service)."""
        from app.core.models import SUBSCRIPTIONS

        out: list[str] = []
        after: str | None = None
        while True:
            rows, after = await self.store.find(SUBSCRIPTIONS, {"tenant": tenant}, limit=200,
                                                after=after, sort=("id", "asc"))
            out.extend(r["subject"] for r in (rows or []) if r.get("on"))
            if not after:
                return out
