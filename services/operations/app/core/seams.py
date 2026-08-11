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
                 index_name: str = "customers") -> None:
        self._search = search
        self._events = events
        self._telemetry = telemetry
        self._index = index_name

    async def after_visit(self, result) -> None:
        # One try/except per seam, not one around all three. A failure in the first must not
        # silently skip the other two — that would make one broken peer look like three.
        await self._index_customer(result)
        await self._emit_visit(result)

    async def _index_customer(self, result) -> None:
        """Make the customer findable by the keypad.

        Indexed on EVERY visit rather than only on creation: the name may have arrived later, and
        an index that is only written once drifts from the record it points at. The write is small
        and idempotent by document id.
        """
        c = result.customer
        await self.index_customer_row(
            tenant=c.tenant, customer_id=c.id, phone=c.phone, name=c.name,
            plates=list(getattr(result, "plates", []) or []))

    async def index_customer_row(self, *, tenant: str, customer_id: str, phone: str,
                                 name: str, plates: list[str]) -> None:
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
                    # HIS PLATES, and ALL of them: «ممكن عندي سيارتين برقمي». In a vehicle sector
                    # the operator reads the plate off the bumper and knows nothing else yet.
                    "plate": " ".join([p for p in plates if p]),
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
                "asset_id": v.asset_id,
                "operator_id": v.operator_id,
                "branch_id": v.branch_id,
                "visit_count": c.visit_count,
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
