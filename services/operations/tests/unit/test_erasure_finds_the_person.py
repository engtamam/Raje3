"""د-2 · the erasure that found nobody and reported success.

`compliance` fans a PDPL erasure out to every service by the PSEUDONYM — the only identifier the
others hold. This service holds the phone number as well, and hashed whatever it was handed. So the
pseudonym was hashed a second time, the ref of a ref matched no row, the scan answered
`already_absent: true` with HTTP 200, the dispatcher read that as ACKED, and `derive_completion`
closed the request COMPLETED.

The name, the number, the plate and the notes stayed exactly where they were — in the one service
that holds the real identifier — and the customer was told his data had been erased, on a legal
deadline, with nothing wrong in any log.

The guard for this was written in `pii.py` on the first day (`is_subject_ref` — «so we never
double-wrap one») and had no production caller at all.
"""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.erasure import OperationsErasure
from app.core.models import Customer, Visit
from app.core.pii import subject_ref
from app.core.stores import CustomerStore, VisitStore

SALT = "s" * 32
TENANT = "t1"
PHONE = "966500000111"


def run(c):
    return asyncio.run(c)


def _shop():
    store = MemoryDataStore()
    ref = subject_ref(SALT, TENANT, PHONE)
    cust = Customer(id="cus_1", tenant=TENANT, phone=PHONE, subject_ref=ref, name="أحمد")
    run(CustomerStore(store).save(cust))
    run(VisitStore(store).save(Visit(id="vis_1", tenant=TENANT, customer_id="cus_1",
                                     service_ids=["svc_wash"], note="ملاحظة على السيارة")))
    return store, ref


def test_an_erasure_by_pseudonym_actually_erases():
    """THE PATH COMPLIANCE USES. It has never once worked."""
    store, ref = _shop()
    eraser = OperationsErasure(store=store, pii_salt=SALT)

    out = run(eraser.erase(TENANT, ref))

    assert out.get("already_absent") is not True, (
        "«nothing to erase» about a customer who is still there is the whole defect")
    # `erased` carries «collection:count» — the count is what proves rows were touched rather
    # than a collection merely being visited.
    assert "customers:1" in (out.get("erased") or []), out
    # REDACTED, NOT DELETED — the row survives with nothing on it that identifies anybody, which
    # is what «الاسم والرقم واللوحة والملاحظات» meant: those are the fields that must be gone.
    left = run(CustomerStore(store).get(TENANT, "cus_1"))
    assert left is not None and left.phone == "" and left.name == "", left


def test_an_erasure_by_phone_still_works():
    """OUR OWN PATH, unchanged: this service identifies a person by the number, and the owner's
    button starts from the customer row."""
    store, _ = _shop()
    eraser = OperationsErasure(store=store, pii_salt=SALT)

    out = run(eraser.erase(TENANT, PHONE))

    assert "customers:1" in (out.get("erased") or []), out
    left = run(CustomerStore(store).get(TENANT, "cus_1"))
    assert left.phone == "" and left.name == ""


def test_hashing_a_pseudonym_is_refused_at_the_source():
    """THE SHAPE IS REMOVED, NOT ONLY THE INSTANCE. A caller that hands `subject_ref` something
    that is already a pseudonym now fails loudly — there is no second site to remember, and no
    list of exceptions to keep."""
    ref = subject_ref(SALT, TENANT, PHONE)

    with pytest.raises(ValueError) as caught:
        subject_ref(SALT, TENANT, ref)

    assert "already a pseudonym" in str(caught.value)


def test_an_ordinary_identifier_is_still_hashed():
    """The guard must not eat the real case: a phone number, an email, a platform subject id —
    none of them look like our pseudonym, and all of them must still hash."""
    for value in (PHONE, "user@example.com", "op1", "sub_short", "sub_" + "z" * 31):
        assert subject_ref(SALT, TENANT, value).startswith("sub_")
