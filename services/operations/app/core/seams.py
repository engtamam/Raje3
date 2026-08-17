"""What happens after a visit is recorded — and why none of it is on the request path.

Recording a visit costs two reads and two writes. Everything else a visit implies — indexing the
customer so the keypad can find them, counting it so the owner's dashboard is right, scheduling the
reminder that is the entire point of the product — is work the OPERATOR IS NOT WAITING FOR.

Put any of it in front of the response and a slow peer becomes a slow screen. The five-second
budget (spec §17.3) belongs to the person with a customer standing in front of them, not to our
fan-out.

FAILURE HERE MUST NOT LOSE THE VISIT. The visit is already durable before any of this runs. So
every seam below fails soft, records that it failed, and lets the sweep or the next visit repair
it. The alternative — surfacing a search-service hiccup to an operator whose visit was saved
correctly — teaches them to distrust a screen that was right.

WHAT IS NOT HERE, DELIBERATELY: the audit record. It runs BEFORE the write, in the route, because
a visit the log cannot witness must not happen at all. Moving it here would mean telling an
operator "saved" about something the record does not hold.
"""
from __future__ import annotations

from typing import Any


class Seams:
    """Post-response work. Constructed once and handed the peers it talks to."""

    def __init__(self, *, search=None, events=None, telemetry=None,
                 index_name: str = "customers", visits=None, clock=None) -> None:
        self._search = search
        self._events = events
        self._telemetry = telemetry
        self._index = index_name
        # THE STORE THIS MARKS WHEN IT IS DONE (ز-7). Optional so a caller that only wants the
        # index write — the backfill — needs no store; when it is absent nothing is stamped, and
        # the sweep will simply come back, which is the harmless direction.
        self._visits = visits
        self._clock = clock or (lambda: int(__import__("time").time()))

    async def after_visit(self, result) -> None:
        # One try/except per seam, not one around all three. A failure in the first must not
        # silently skip the other two — that would make one broken peer look like three.
        await self._index_customer(result)
        await self._emit_visit(result)
        await self._mark_seamed(result)

    async def _mark_seamed(self, result) -> None:
        """Write down that this visit's after-work finished (ز-7).

        THE DOCSTRING ABOVE PROMISED THIS BEFORE ANYTHING DID IT: «lets the sweep or the next visit
        repair it». There was no sweep, and the next visit repaired nothing — it indexed the
        customer again and emitted its own event, which does nothing for the reminder the lost
        visit never scheduled. A reason given for a decision has to be a mechanism.
        """
        visit = getattr(result, "visit", None)
        if self._visits is None or visit is None:
            return
        try:
            visit.seamed_at = self._clock()
            await self._visits.save(visit)
        except Exception as exc:                                            # noqa: BLE001
            # UNMARKED IS THE SAFE SIDE. The seams themselves already ran; failing to record that
            # costs one repeated pass later, and a repeated pass is harmless — the index write is
            # idempotent by document id and the event carries the visit id.
            self._note("seam_mark_failed", error=str(exc)[:200],
                       visit=getattr(visit, "id", ""))

    async def _index_customer(self, result) -> None:
        """Make the customer findable by the keypad.

        Indexed on EVERY visit rather than only on creation: the name may have arrived later, and
        an index that is only written once drifts from the record it points at. The write is small
        and idempotent by document id.
        """
        c = result.customer
        await self.index_customer_row(
            tenant=c.tenant, customer_id=c.id, phone=c.phone, name=c.name,
            plates=list(getattr(result, "plates", []) or []),
            branch_id=getattr(c, "last_branch_id", "") or "")

    async def index_customer_row(self, *, tenant: str, customer_id: str, phone: str,
                                 name: str, plates: list[str], branch_id: str = "") -> None:
        """The ONE place a customer's search document is composed.

        TWO CALLERS, ONE SHAPE. The visit path writes it as it happens, and the backfill rewrites
        it for customers who came before a field existed — and if those two ever disagreed, half a
        shop would be searchable by a field the other half is not, which is worse than the field
        not existing at all.
        """
        if self._search is None:
            return
        try:
            await self._search.index(
                index=self._index, doc_id=customer_id, tenant=tenant,
                fields={
                    # STORED E.164, and the operator types 05. Both forms are indexed because the
                    # search matches PREFIXES: «05…» against a stored «966…» matched nothing, ever,
                    # on the one screen built around finding a customer fast. Measured on the live
                    # index — «96» returned ten numbers, «05» returned none.
                    "phone": phone,
                    "local": ("0" + phone[3:]) if phone.startswith("966") else phone,
                    # Empty is fine and expected: the name is optional. The analyzer folds Arabic
                    # forms, which is why a customer saved as "محمّد" is found by someone typing
                    # "محمد" — proven, and the reason this is a search service and not a LIKE.
                    "name": name,
                    # HIS PLATES, and ALL of them: «ممكن عندي سيارتين برقمي». In a shop that works on cars
                    # the operator reads the plate off the bumper and knows nothing else yet.
                    "plate": " ".join([p for p in plates if p]),
                    # WHERE THIS CUSTOMER WAS LAST SERVED (ط-3), and the document had no such
                    # field at all — so nothing downstream could narrow a prefix suggestion to the
                    # branch asking. A manager in Jeddah typing four digits was answered with
                    # Riyadh's customers by name, number and plate, and the entire branch scope
                    # `field.py` builds for `recent` and `resolve` was walked around by the keypad,
                    # which calls search rather than either of them.
                    #
                    # A FIELD THAT IS ONLY SOMETIMES THERE IS WORSE THAN ABSENT: a filter would
                    # then hide every customer indexed before this line existed. So it is written
                    # on EVERY index — the visit path and the backfill both — and the backfill is
                    # what makes the older half of a shop answerable to the same question.
                    #
                    # Empty is a real and common value: a till records no branch, and a shop that
                    # never opened a second one has none. Empty means «visible to everyone», the
                    # same rule `SCOPE.visible` already applies everywhere else.
                    "branch_id": branch_id or "",
                })
        except Exception as exc:                                            # noqa: BLE001
            self._note("search_index_failed", error=str(exc)[:200], customer=customer_id)

    async def _emit_visit(self, result) -> None:
        """Publish the fact, for whoever cares.

        `reminders` will schedule from this, `insights` will count it. Publishing rather than
        calling them keeps this service ignorant of who consumes a visit — a service that knows
        its consumers has to be changed every time one is added.

        The payload carries the SUBJECT_REF, never the phone number. No peer needs the raw number,
        and one that never receives it cannot leak it.
        """
        if self._events is None:
            return
        v, c = result.visit, result.customer
        try:
            # An Event, not a bare dict. The port takes a typed envelope — reading the method NAME
            # and guessing its argument is how a seam fails silently in production while every
            # test that mocked it passed.
            from app.ports.event_bus import Event
            await self._events.publish("operations.visit.recorded", Event(
                type="operations.visit.recorded",
                payload={
                "tenant": v.tenant,
                "visit_id": v.id,
                "customer_id": c.id,
                "subject_ref": c.subject_ref,
                "service_ids": list(v.service_ids),
                # HOW MANY OF EACH (أ-8). `/since` carries this and says the two shapes are the
                # same — «loyalty's catch-up reads this row when the bus drops one» — and the event
                # did not, so the promise held only until somebody believed it. A consumer that
                # subscribes here reads a basket with no quantities and cannot tell one oil change
                # from four, which is exactly what the group-basket test exists to catch.
                "quantities": dict(v.quantities or {}),
                "asset_id": v.asset_id,
                "operator_id": v.operator_id,
                "branch_id": v.branch_id,
                "visit_count": c.visit_count,
                # THE NAME loyalty READS, and it read a key nobody emitted (أ-1). `earn.py` asks
                # for `amount_halalas` and multiplies `(amount // 100) * points_per_riyal`; with
                # the key absent that is `(0 // 100) * n`, so an integrated shop earned zero points
                # on every invoice and the recorded reason said «no points configured».
                "amount_halalas": v.total_minor,
                # BOUGHT WITH POINTS (ب-6). The earner reads this and awards nothing: a reward
                # that pays the customer for redeeming it gives the same thing away twice.
                "free": bool(v.free),
                "occurred_at": v.occurred_at or v.created,
                "created": v.created,
            }))
        except Exception as exc:                                            # noqa: BLE001
            self._note("visit_event_failed", error=str(exc)[:200], visit=v.id)

    def _note(self, event: str, **fields: Any) -> None:
        """A failed seam is recorded, never swallowed.

        Silent is the one thing it must not be: the visit is safe, so nobody is paged, and the
        symptom — a customer the keypad cannot find, a reminder that never arrives — surfaces days
        later somewhere that looks unrelated.
        """
        if self._telemetry is not None:
            self._telemetry.event(event, **fields)
            self._telemetry.counter(f"operations_seam_failed_{event}")
