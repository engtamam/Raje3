"""§6.5's own defect family, closed: erasure by PSEUDONYM (what `compliance`'s DSAR fan-out
actually sends) must find a subject's bookings, not just erasure by the raw phone number this
service never even holds.
"""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.erasure import TemplateErasure
from app.core.models import Booking
from app.core.pii import subject_ref
from app.core.stores import BookingStore

SALT = "s" * 32
TENANT = "t1"
PHONE = "966500000111"


def run(c):
    return asyncio.run(c)


def _shop():
    store = MemoryDataStore()
    ref = subject_ref(SALT, TENANT, PHONE)
    run(BookingStore(store).save(Booking(
        id="bkg_1", tenant=TENANT, branch_id="b1", operator_id="op1", customer_id="cus_1",
        subject_ref=ref, service_ids=("svc1",), starts_at=1786860000, duration_minutes=30,
        note="ملاحظة عن العميلة", created=1786860000, updated=1786860000)))
    return store, ref


def test_an_erasure_by_pseudonym_finds_the_booking():
    """THE PATH COMPLIANCE ACTUALLY USES — same defect family operations' own erasure had before
    subject_ref existed here to be found by."""
    store, ref = _shop()
    eraser = TemplateErasure(store=store, pii_salt=SALT)

    out = run(eraser.erase(TENANT, ref))

    assert out["already_absent"] is False
    assert "bookings:1" in out["erased"]

    row = run(BookingStore(store).get(TENANT, "bkg_1"))
    assert row.note == "[محذوف]"
    # THE APPOINTMENT ITSELF SURVIVES — not deleted, not cancelled. Only the free text is gone.
    assert row.status == "booked"
    assert row.starts_at == 1786860000


def test_erasure_by_the_raw_phone_also_works_for_our_own_future_paths():
    store, ref = _shop()
    eraser = TemplateErasure(store=store, pii_salt=SALT)

    out = run(eraser.erase(TENANT, PHONE))

    assert out["already_absent"] is False
    assert out["subject_ref"] == ref


def test_a_subject_with_no_bookings_is_reported_absent_not_hidden():
    store = MemoryDataStore()
    eraser = TemplateErasure(store=store, pii_salt=SALT)

    out = run(eraser.erase(TENANT, "966500000999"))

    assert out["already_absent"] is True
    assert out["erased"] == []


def test_erasure_is_idempotent():
    """A DSAR retries. The second pass must not fail and must not un-redact anything — same
    shape as `operations`' own note redaction, which this mirrors exactly."""
    store, ref = _shop()
    eraser = TemplateErasure(store=store, pii_salt=SALT)

    first = run(eraser.erase(TENANT, ref))
    second = run(eraser.erase(TENANT, ref))

    assert "bookings:1" in first["erased"]
    assert second["already_absent"] is False   # the booking itself is still there
    row = run(BookingStore(store).get(TENANT, "bkg_1"))
    assert row.note == "[محذوف]", "a retried erasure must not un-redact or corrupt the row"
