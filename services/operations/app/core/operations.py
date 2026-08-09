"""The field operation itself — recording a visit, and everything that hangs off it.

THE FIVE-SECOND RULE IS THE DESIGN CONSTRAINT, not an aspiration (spec §17.3). An operator records
a visit with a customer standing in front of them, and the screen must be empty and ready for the
next car within that budget. Everything here is arranged around it:

  * the request path does the MINIMUM: find or create the customer, write the visit. Two indexed
    reads and two writes, no joins, no fan-out.
  * indexing into search, the analytics event, and the reminder scheduling all happen AFTER the
    operator has been answered (see api/v1/visits.py). A peer being slow must never be the screen
    being slow.
  * the audit record is the one exception and it runs BEFORE the write, deliberately. A visit the
    log cannot witness must not happen — and recording afterwards would tell an operator "saved"
    about something the record does not hold.

THE DOUBLE TAP. A thumb on a phone in a workshop hits the save button twice. The guard is a
CLIENT-generated idempotency key, one per entry on the screen: the second tap carries the same key
and gets the same visit back. This cannot be done server-side — a server sees two identical
requests and cannot tell a double tap from a customer who genuinely came back an hour later, which
in a tyre shop is an ordinary thing.

The guard is a read-before-write rather than a unique constraint, and that is a deliberate trade:
under a true race two writes can still land. The reconciliation is that the SECOND one is
detectable (same key, two rows) and a sweep can merge them, whereas a database-level lock on the
hot path would cost every save to protect against a case that needs two taps inside the same few
milliseconds.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from app.core.models import Asset, Customer, Visit
from app.core.pii import subject_ref
from app.core.stores import AssetStore, CustomerStore, ServiceStore, VisitStore, new_id


class OperationError(Exception):
    """A refusal the caller can act on. The message is shown to an operator, so it says what to do
    rather than what went wrong internally."""


@dataclass
class RecordedVisit:
    visit: Visit
    customer: Customer
    created_customer: bool
    duplicate: bool          # True when the idempotency key had already been used
    # Service ids the catalogue did not recognise, folded into the catch-all. REPORTED rather than
    # swallowed: an integration sending a service that does not exist is a bug worth seeing, even
    # though the visit was rightly kept.
    unknown_services: list[str] = field(default_factory=list)


def _now() -> int:
    return int(time.time())


# A DEFAULT: how far back a claimed visit time may be before we treat it as a broken clock rather
# than a backlog. A shop migrating a year of history legitimately needs more, and a release is the
# wrong way to give it to them. MAX_BACKDATE_SECONDS overrides it.
_DEFAULT_MAX_BACKDATE_SECONDS = 90 * 24 * 3600


class Operations:
    def __init__(self, *, store, pii_salt: str,
                 max_backdate: int = _DEFAULT_MAX_BACKDATE_SECONDS) -> None:
        self._customers = CustomerStore(store)
        self._assets = AssetStore(store)
        self._services = ServiceStore(store)
        self._visits = VisitStore(store)
        self._salt = pii_salt
        # How far back a claimed visit time may be before it is a broken clock. A shop migrating a
        # year of its own history needs more, and that must not require a release.
        self._max_backdate = int(max_backdate)

    # ── the write path ────────────────────────────────────────────────────────────────────────
    async def record_visit(self, *, tenant: str, phone: str, service_ids: list[str],
                           operator_id: str = "", branch_id: str = "", name: str = "",
                           plate: str = "", meter: int = 0, note: str = "",
                           idempotency_key: str = "", custom_service: str = "",
                           occurred_at: int = 0,
                           allow_unknown_services: bool = False) -> RecordedVisit:
        if not tenant:
            raise OperationError("no establishment on the request")
        phone = _normalise_phone(phone)
        if not phone:
            raise OperationError("a phone number is required")
        if not service_ids:
            raise OperationError("select at least one service")
        if any(not str(s).strip() for s in service_ids):
            raise OperationError("a service id is blank")

        # The double-tap guard, first, before anything is created. Cheapest possible check: one
        # indexed read. If it hits, nothing else in this method runs — including customer creation,
        # which is what stops a double tap from also producing two customers.
        if idempotency_key:
            existing = await self._visits.by_idempotency_key(tenant, idempotency_key)
            if existing is not None:
                customer = await self._customers.get(tenant, existing.customer_id)
                return RecordedVisit(visit=existing, customer=customer, created_customer=False,
                                     duplicate=True)

        now = _now()
        customer = await self._customers.by_phone(tenant, phone)
        created_customer = customer is None
        if customer is None:
            customer = Customer(
                id=new_id("cus"), tenant=tenant, phone=phone,
                subject_ref=subject_ref(self._salt, tenant, phone),
                name=name.strip(), created=now)
        elif name.strip() and not customer.name:
            # A name arriving later fills a blank, but never overwrites one already there. The
            # operator typing today does not know what the operator typed last month, and the
            # older value was entered with the customer present just as this one is.
            customer.name = name.strip()

        # UNKNOWN SERVICES ARE ABSORBED, NOT REFUSED — and only on the integration path, where
        # `allow_unknown_services` is set. A till sends a service the owner never added to our
        # catalogue: refusing it would lose the visit, and a lost visit loses the CUSTOMER from
        # the product entirely — no reminder, no points, no metric, permanently. Losing the
        # service NAME is a small cost; losing the visit costs the product its premise.
        #
        # So the unknown ids are folded into the tenant's catch-all and their labels preserved on
        # the visit, where an owner can read them and where a name that keeps appearing is exactly
        # the signal that it should become a real catalogue entry.
        #
        # Never silent: the caller is told which ids were unknown, so an integration bug is
        # visible rather than absorbed into a shrug.
        unknown: list[str] = []
        if allow_unknown_services:
            known = {s.id for s in await self._services.list(tenant, active_only=False)}
            unknown = [sid for sid in service_ids if sid not in known]
            if unknown:
                catch = await self._services.catchall(tenant)
                if catch is None:
                    # A tenant provisioned before the catch-all existed. A clean refusal that names
                    # the fix, rather than a crash or a silently dropped service.
                    raise OperationError(
                        "this establishment has no 'خدمة أخرى' entry, so an unrecognised service "
                        "cannot be recorded — re-seed its catalogue")
                service_ids = [sid for sid in service_ids if sid in known] or []
                if catch.id not in service_ids:
                    service_ids = service_ids + [catch.id]
                if not custom_service:
                    custom_service = ", ".join(unknown)[:200]

        asset_id = ""
        if plate.strip():
            asset_id = await self._resolve_asset(tenant, customer.id, plate.strip())

        visit = Visit(id=new_id("vis"), tenant=tenant, customer_id=customer.id,
                      service_ids=list(service_ids), asset_id=asset_id, operator_id=operator_id,
                      branch_id=branch_id, meter=meter, note=note.strip(),
                      custom_service=custom_service.strip()[:200],
                      idempotency_key=idempotency_key, created=now,
                      occurred_at=_sane_occurred_at(occurred_at, now,
                                                                    self._max_backdate))

        # last_visit follows the EVENT time, not the receive time: a batch drained two days late
        # describes a customer who was here two days ago, and the reminder must be scheduled from
        # when they were actually here.
        #
        # It only moves FORWARD. A replayed old visit arriving after a newer one must not drag the
        # customer's last-visit date backwards, which would schedule a reminder that has already
        # passed and mark a returning customer as absent.
        # The counters live on the customer so the recent-customers strip is one read. Updated
        # here rather than derived, because deriving them would put a scan on every keystroke.
        customer.last_visit = max(customer.last_visit, visit.occurred_at)
        customer.visit_count += 1

        await self._customers.save(customer)
        await self._visits.save(visit)
        return RecordedVisit(visit=visit, customer=customer,
                             created_customer=created_customer, duplicate=False,
                             unknown_services=unknown)

    async def _resolve_asset(self, tenant: str, customer_id: str, plate: str) -> str:
        """Find this customer's vehicle by plate, or create it.

        Matched WITHIN the customer, not across the tenant. Two customers may present the same
        plate — a sold car, a company vehicle, a transcription error — and attaching a visit to the
        wrong person's car is worse than holding the plate twice.
        """
        for a in await self._assets.for_customer(tenant, customer_id):
            if a.plate == plate:
                return a.id
        asset = Asset(id=new_id("ast"), tenant=tenant, customer_id=customer_id, plate=plate,
                      created=_now())
        await self._assets.save(asset)
        return asset.id

    # ── the read path ─────────────────────────────────────────────────────────────────────────
    async def recent_customers(self, tenant: str, limit: int = 10) -> list[Customer]:
        return await self._customers.recent(tenant, limit=limit)

    async def customer_by_phone(self, tenant: str, phone: str) -> Customer | None:
        return await self._customers.by_phone(tenant, _normalise_phone(phone))

    async def customer_record(self, tenant: str, customer_id: str) -> dict[str, Any] | None:
        """A customer with their vehicles and recent visits — the screen an operator opens when a
        customer asks "when was I last here?"."""
        customer = await self._customers.get(tenant, customer_id)
        if customer is None:
            return None
        return {
            "customer": customer.public(),
            "assets": [a.public() for a in await self._assets.for_customer(tenant, customer_id)],
            "visits": [v.public() for v in await self._visits.for_customer(tenant, customer_id)],
        }

    async def catalogue(self, tenant: str) -> list[dict[str, Any]]:
        return [s.public() for s in await self._services.list(tenant)]


# A device clock may be wrong by days, and occasionally by years — a tablet that lost its battery
# comes back at the epoch, and one set by hand can land in the future. Both are clamped rather than
# trusted, because either would corrupt a reminder schedule silently.


def _sane_occurred_at(claimed: int, now: int,
                      max_backdate: int = _DEFAULT_MAX_BACKDATE_SECONDS) -> int:
    """Trust the device's clock only within a window we can defend.

    Not validation for its own sake: `occurred_at` is what reminders schedule from. A device set to
    next month would schedule a reminder into next month; one at the epoch would mark every
    customer permanently absent and trigger a win-back to somebody who was here this morning.
    """
    if claimed <= 0:
        return now
    if claimed > now:
        # A future timestamp is always wrong — we received it, so it has happened.
        return now
    if now - claimed > max_backdate:
        return now
    return claimed


def _normalise_phone(phone: str) -> str:
    """One stored form, so the same person is one customer however they were typed.

    A Saudi number arrives as 0501234567, 501234567, +966501234567 or 966501234567 depending on who
    is typing and what their keyboard did. Stored differently, they become four customers with one
    visit each instead of one customer with four — and the whole product is built on recognising
    the returning customer.

    Kept deliberately small and country-shaped rather than a general library: this is a Saudi
    product, and a general phone parser would accept forms that are certainly typos here.
    """
    digits = "".join(c for c in phone if c.isdigit())
    if not digits:
        return ""
    if digits.startswith("00966"):
        digits = digits[5:]
    elif digits.startswith("966"):
        digits = digits[3:]
    digits = digits.lstrip("0")
    # A Saudi mobile is 5XXXXXXXX — nine digits starting with 5. Anything else is stored as typed
    # rather than refused: a landline, a foreign number, a genuine oddity. Refusing it would stop a
    # real visit being recorded to enforce a format nobody promised.
    return f"966{digits}" if len(digits) == 9 and digits.startswith("5") else digits
