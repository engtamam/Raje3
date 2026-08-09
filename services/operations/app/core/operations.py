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
from dataclasses import dataclass
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


def _now() -> int:
    return int(time.time())


class Operations:
    def __init__(self, *, store, pii_salt: str) -> None:
        self._customers = CustomerStore(store)
        self._assets = AssetStore(store)
        self._services = ServiceStore(store)
        self._visits = VisitStore(store)
        self._salt = pii_salt

    # ── the write path ────────────────────────────────────────────────────────────────────────
    async def record_visit(self, *, tenant: str, phone: str, service_ids: list[str],
                           operator_id: str = "", branch_id: str = "", name: str = "",
                           plate: str = "", meter: int = 0, note: str = "",
                           idempotency_key: str = "") -> RecordedVisit:
        if not tenant:
            raise OperationError("no establishment on the request")
        phone = _normalise_phone(phone)
        if not phone:
            raise OperationError("a phone number is required")
        if not service_ids:
            raise OperationError("select at least one service")

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

        asset_id = ""
        if plate.strip():
            asset_id = await self._resolve_asset(tenant, customer.id, plate.strip())

        visit = Visit(id=new_id("vis"), tenant=tenant, customer_id=customer.id,
                      service_ids=list(service_ids), asset_id=asset_id, operator_id=operator_id,
                      branch_id=branch_id, meter=meter, note=note.strip(),
                      idempotency_key=idempotency_key, created=now)

        # The counters live on the customer so the recent-customers strip is one read. Updated
        # here rather than derived, because deriving them would put a scan on every keystroke.
        customer.last_visit = now
        customer.visit_count += 1

        await self._customers.save(customer)
        await self._visits.save(visit)
        return RecordedVisit(visit=visit, customer=customer,
                             created_customer=created_customer, duplicate=False)

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
