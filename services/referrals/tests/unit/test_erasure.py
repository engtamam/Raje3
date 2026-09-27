"""Erasure — app/core/erasure.py, Phase 1's own {phone <-> code} mapping."""
from __future__ import annotations

from app.adapters.datastore.memory import MemoryDataStore
from app.core.erasure import TemplateErasure
from app.core.referral_code import BY_CODE, BY_PHONE, code_for_phone
from tests.contracts.util import run

TENANT = "t1"
PHONE = "+966501234567"
SALT = "s" * 32


def test_erase_deletes_both_sides_of_the_mapping():
    store = MemoryDataStore()
    code = run(code_for_phone(store, PHONE))

    eraser = TemplateErasure(store=store, pii_salt=SALT)
    result = run(eraser.erase(TENANT, PHONE))

    assert run(store.get(BY_PHONE, PHONE)) is None
    assert run(store.get(BY_CODE, code)) is None
    assert result["already_absent"] is False
    assert result["erased"] == [f"{BY_PHONE}:1", f"{BY_CODE}:1"]
    assert result["retained"] == []


def test_erase_on_a_phone_with_no_rows_reports_already_absent():
    store = MemoryDataStore()
    eraser = TemplateErasure(store=store, pii_salt=SALT)
    result = run(eraser.erase(TENANT, PHONE))
    assert result["already_absent"] is True
    assert result["erased"] == []


def test_erase_is_idempotent():
    store = MemoryDataStore()
    run(code_for_phone(store, PHONE))
    eraser = TemplateErasure(store=store, pii_salt=SALT)

    first = run(eraser.erase(TENANT, PHONE))
    second = run(eraser.erase(TENANT, PHONE))

    assert first["already_absent"] is False
    assert second["already_absent"] is True, "a retried DSAR must not fail on an already-erased subject"


def test_erasing_one_phone_never_touches_another_phones_code():
    store = MemoryDataStore()
    other_phone = "+966509999999"
    other_code = run(code_for_phone(store, other_phone))
    run(code_for_phone(store, PHONE))

    eraser = TemplateErasure(store=store, pii_salt=SALT)
    run(eraser.erase(TENANT, PHONE))

    assert run(store.get(BY_PHONE, other_phone)) is not None
    assert run(store.get(BY_CODE, other_code)) is not None
