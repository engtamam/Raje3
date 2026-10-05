"""Customer-service freelancers — the link table / authorization boundary
(core/freelancer_service.py). No HTTP, no CRM rules — just the add/deactivate/list engine and the
invariants its own module docstring promises: max 3 active per tenant, no duplicate phone within a
tenant, tenant isolation, and `tenants_for_phone()` never leaking another tenant's data.
"""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.freelancer_service import FreelancerError, FreelancerService

CC = "966"
TENANT_A = "tnt_freelancer_a"
TENANT_B = "tnt_freelancer_b"


def run(c):
    return asyncio.run(c)


@pytest.fixture()
def svc():
    store = MemoryDataStore()
    return FreelancerService(store=store, default_cc=CC), store


def test_add_links_a_freelancer(svc):
    s, _store = svc
    row = run(s.add(TENANT_A, phone="0501234567", display_name="سارة", actor="owner1"))
    assert row.active is True
    assert row.phone.startswith("+966")
    assert row.display_name == "سارة"


def test_add_refuses_an_invalid_phone(svc):
    s, _store = svc
    with pytest.raises(FreelancerError):
        run(s.add(TENANT_A, phone="not-a-phone", display_name="سارة", actor="owner1"))


def test_add_refuses_an_empty_display_name(svc):
    s, _store = svc
    with pytest.raises(FreelancerError):
        run(s.add(TENANT_A, phone="0501234567", display_name="   ", actor="owner1"))


def test_add_refuses_a_duplicate_phone_in_the_same_tenant(svc):
    s, _store = svc
    run(s.add(TENANT_A, phone="0501234567", display_name="سارة", actor="owner1"))
    with pytest.raises(FreelancerError):
        run(s.add(TENANT_A, phone="0501234567", display_name="سارة الثانية", actor="owner1"))


def test_the_same_phone_may_be_linked_in_a_different_tenant(svc):
    s, _store = svc
    run(s.add(TENANT_A, phone="0501234567", display_name="سارة", actor="owner1"))
    row = run(s.add(TENANT_B, phone="0501234567", display_name="سارة", actor="owner2"))
    assert row.tenant == TENANT_B


def test_add_refuses_past_the_cap_of_three_active_freelancers(svc):
    s, _store = svc
    run(s.add(TENANT_A, phone="0501111111", display_name="واحد", actor="owner1"))
    run(s.add(TENANT_A, phone="0502222222", display_name="اثنان", actor="owner1"))
    run(s.add(TENANT_A, phone="0503333333", display_name="ثلاثة", actor="owner1"))
    with pytest.raises(FreelancerError):
        run(s.add(TENANT_A, phone="0504444444", display_name="أربعة", actor="owner1"))


def test_deactivating_one_frees_a_slot_under_the_cap(svc):
    s, _store = svc
    one = run(s.add(TENANT_A, phone="0501111111", display_name="واحد", actor="owner1"))
    run(s.add(TENANT_A, phone="0502222222", display_name="اثنان", actor="owner1"))
    run(s.add(TENANT_A, phone="0503333333", display_name="ثلاثة", actor="owner1"))
    run(s.deactivate(TENANT_A, one.id))
    row = run(s.add(TENANT_A, phone="0504444444", display_name="أربعة", actor="owner1"))
    assert row.active is True


def test_deactivate_is_a_soft_stop_never_a_delete(svc):
    s, _store = svc
    row = run(s.add(TENANT_A, phone="0501234567", display_name="سارة", actor="owner1"))
    deactivated = run(s.deactivate(TENANT_A, row.id))
    assert deactivated.active is False
    # still listable with include_inactive, still the same id
    rows = run(s.list(TENANT_A, include_inactive=True))
    assert any(r.id == row.id and r.active is False for r in rows)


def test_deactivate_is_idempotent(svc):
    s, _store = svc
    row = run(s.add(TENANT_A, phone="0501234567", display_name="سارة", actor="owner1"))
    run(s.deactivate(TENANT_A, row.id))
    again = run(s.deactivate(TENANT_A, row.id))
    assert again.active is False


def test_deactivate_refuses_a_link_belonging_to_another_tenant(svc):
    s, _store = svc
    row = run(s.add(TENANT_A, phone="0501234567", display_name="سارة", actor="owner1"))
    with pytest.raises(FreelancerError):
        run(s.deactivate(TENANT_B, row.id))


def test_list_only_returns_the_calling_tenants_own_rows(svc):
    s, _store = svc
    run(s.add(TENANT_A, phone="0501111111", display_name="فرع أ", actor="owner1"))
    run(s.add(TENANT_B, phone="0502222222", display_name="فرع ب", actor="owner2"))
    rows_a = run(s.list(TENANT_A))
    assert len(rows_a) == 1
    assert rows_a[0].tenant == TENANT_A


def test_list_excludes_inactive_rows_by_default(svc):
    s, _store = svc
    row = run(s.add(TENANT_A, phone="0501234567", display_name="سارة", actor="owner1"))
    run(s.deactivate(TENANT_A, row.id))
    assert run(s.list(TENANT_A)) == []
    assert len(run(s.list(TENANT_A, include_inactive=True))) == 1


def test_tenants_for_phone_finds_every_tenant_a_freelancer_is_active_in(svc):
    s, _store = svc
    run(s.add(TENANT_A, phone="0501234567", display_name="سارة", actor="owner1"))
    run(s.add(TENANT_B, phone="0501234567", display_name="سارة", actor="owner2"))
    tenants = run(s.tenants_for_phone("0501234567"))
    assert tenants == sorted([TENANT_A, TENANT_B])


def test_tenants_for_phone_excludes_a_deactivated_link(svc):
    s, _store = svc
    row = run(s.add(TENANT_A, phone="0501234567", display_name="سارة", actor="owner1"))
    run(s.deactivate(TENANT_A, row.id))
    assert run(s.tenants_for_phone("0501234567")) == []


def test_tenants_for_phone_never_reveals_anything_but_the_tenant_id(svc):
    s, _store = svc
    run(s.add(TENANT_A, phone="0501234567", display_name="سارة", actor="owner1"))
    tenants = run(s.tenants_for_phone("0501234567"))
    assert tenants == [TENANT_A]
    assert all(isinstance(t, str) for t in tenants)


def test_tenants_for_phone_returns_nothing_for_an_unknown_phone(svc):
    s, _store = svc
    assert run(s.tenants_for_phone("0509999999")) == []
