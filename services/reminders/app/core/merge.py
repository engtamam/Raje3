"""Two messages for one person, days apart — folded into one (spec §5.8.1).

WHAT ALREADY WORKS, AND WHERE IT STOPS. `scheduling.py` merges the services of ONE visit into one
reminder: three services, one message naming three. It cannot do more than that, because at
scheduling time a visit is all there is to see.

SO THE GAP IS THE SECOND VISIT. He changes his oil on Sunday — a reminder is booked for the 12th.
He comes back Tuesday for tyres — a reminder is booked for the 14th. Both correct, both
independent, and nothing in the system knows they belong to one man until the day the first one
goes out. The per-customer limits then hold the second back, which is right and reads as a system
that dribbles messages at you.

────────────────────────────────────────────────────────────────────────────────────────────────
IT PULLS FORWARD. IT NEVER DEFERS.

The whole rule is the direction. A reminder two days early is still true — the need it names has
not arrived yet, and arriving before it is what a reminder IS. A reminder two days late may be
addressed to somebody who already went somewhere else.

So a message due within the window AFTER the one going out is pulled to it and merged. The reverse
— holding today's message to wait for next week's — is never done, at any distance.

────────────────────────────────────────────────────────────────────────────────────────────────
THREE THINGS NEVER MERGE, AND EACH FOR ITS OWN REASON

    service with marketing   Meta types them apart, bills them apart, and the consent each needs
                             is different (§8.5). One message carrying both delivers advertising
                             to somebody who never agreed to receive it.

    a reminder with a        The first is an invitation and the second is a question. A message
    follow-up                that invites and asks in one breath is answered about neither.

    what he started with     A support reply is an answer to HIS question. Folding a commercial
    what we started          reminder into it turns something he asked for into something he did
                             not.

THE PRIORITY LADDER IS §5.8's, UNCHANGED: appointment ← reminder ← follow-up ← marketing.

────────────────────────────────────────────────────────────────────────────────────────────────
PURE ON PURPOSE

Nothing here reads a store or a clock. The caller passes the rows and the time, so the whole
decision space — every combination of class, type, distance and count — is testable without a
datastore, and the same function serves the tick and any preview that ever needs it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

DAY = 86400

# HOW FAR AHEAD WE REACH. Three days: near enough that the two messages are still about the same
# stretch of the customer's life, far enough to catch the common case of two visits in one week.
# Beyond it they are not the same conversation — a service reminded a week early reads as pushy,
# and the saving is not worth teaching him that we nag.
WINDOW_DAYS = 3

# AT MOST THREE SERVICES NAMED — enforced by the RENDERER (`merged_service_text`), which already
# caps at three and turns the rest into «و3 غيرها». It is stated here only so a reader of this
# file knows the cap exists and where; duplicating it would be a second place to change one rule.
MAX_NAMED = 3

# Classes that may be folded together AT ALL. Everything absent from a group is unmergeable with
# everything — including with itself — which is the safe direction for a class nobody has thought
# about yet.
_MERGEABLE = ({"service"},)


@dataclass
class Plan:
    """What to send, and what to close behind it."""

    # The row that goes out, with its service ids widened to cover the folded ones.
    lead: dict[str, Any]
    service_ids: list[str] = field(default_factory=list)
    # The rows folded in. They are CLOSED as `merged`, never deleted — an owner reading «رسائلي»
    # must be able to see one message where he expected two, and understand why. A row that simply
    # vanishes reads as the daily cap eating his messages.
    folded: list[dict[str, Any]] = field(default_factory=list)

    @property
    def merged(self) -> bool:
        return bool(self.folded)


def _ids(row: dict[str, Any]) -> list[str]:
    """Every service this row already speaks for.

    THE ROW'S OWN SHAPE, not one of ours: `service_id` is the one it was scheduled for, and
    `also_services` is what the intra-visit merge already folded in (scheduling.py). Reading only
    the first would drop the visit's other services out of the sentence the moment a second
    message merged into it — a bug that would look like the merge deleting data.
    """
    out = [str(row.get("service_id") or "")] if row.get("service_id") else []
    for extra in (row.get("also_services") or []):
        if extra and str(extra) not in out:
            out.append(str(extra))
    return out


def may_merge(lead: dict[str, Any], other: dict[str, Any]) -> bool:
    """Are these two the same conversation?

    Everything here is a REFUSAL. The default is no, and each yes is argued in the module note —
    a pair nobody has considered must not merge by falling through.
    """
    if lead is other:
        return False
    # The same person, obviously — but stated, because a merge across customers would put one
    # man's services in another man's message, and that is the worst bug this file could have.
    if lead.get("subject_ref") != other.get("subject_ref"):
        return False
    if other.get("state") != "pending":
        return False

    a, b = lead.get("cls", "service"), other.get("cls", "service")
    if a != b:
        return False
    if not any({a} <= group for group in _MERGEABLE):
        return False

    # THE TEMPLATE TYPE IS THE REAL TEST, not the class. A reminder and a follow-up are both
    # `service` class, and they are the pair the module note refuses by name: an invitation and a
    # question do not belong in one message.
    if lead.get("template_type") != other.get("template_type"):
        return False

    return True


def plan(lead: dict[str, Any], pending: list[dict[str, Any]], *, now: int,
         window_days: int = WINDOW_DAYS, max_named: int = MAX_NAMED) -> Plan:
    """Fold everything due within the window into the message going out now.

    `pending` is this customer's other pending rows. `lead` is the one the tick has reached.
    """
    horizon = now + window_days * DAY
    out = Plan(lead=lead, service_ids=list(_ids(lead)))

    for row in sorted(pending, key=lambda r: int(r.get("due_at", 0))):
        if not may_merge(lead, row):
            continue
        # FORWARD ONLY. A row already overdue is not pulled forward — it is behind us, and the tick
        # will reach it on its own turn with its own priority. Reaching backwards here would let a
        # low-priority straggler ride out on a high-priority message's back.
        due = int(row.get("due_at", 0))
        if due <= now or due > horizon:
            continue

        fresh = [s for s in _ids(row) if s not in out.service_ids]
        if not fresh:
            # Same service, a second row — nothing to add to the sentence, but it must still be
            # closed or it goes out tomorrow saying exactly what today's said.
            out.folded.append(row)
            continue
        # THE CAP IS ON WHAT IS NAMED, NOT ON WHAT IS FOLDED. A fourth service is still merged —
        # its row still closes, and the customer still gets one message instead of two. It is only
        # the sentence that stops listing, and `extra` is what the render turns into «وخدمتان
        # أخريان». Stopping the FOLD at three would leave a row to go out tomorrow alone, which is
        # the outcome this whole file exists to prevent.
        out.service_ids.extend(fresh)
        out.folded.append(row)

    out.lead = dict(lead)
    # WRITTEN BACK IN THE ROW'S OWN SHAPE, so the renderer needs no knowledge of this file: it
    # already builds its sentence from `service_id` + `also_services`, and merged_service_text
    # already caps the list at three and counts the rest. Inventing a second field here would mean
    # two ways to say "the services in this message", and the renderer would keep reading the old
    # one — a merge that quietly changed nothing on screen.
    out.lead["also_services"] = out.service_ids[1:]
    return out
