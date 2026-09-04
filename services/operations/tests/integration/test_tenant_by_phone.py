"""`/internal/operations/tenant-by-phone` — an owner's phone, resolved to the tenant he signed
up as owner of. The one direction `SignupService.tenant_of_phone` already answered internally
with no route of its own — investigation tooling (a dispute report) knows an owner's phone, not
his tenant id.
"""
from __future__ import annotations

import asyncio

INTERNAL = {"X-Internal-Token": "t" * 40}
PATH = "/internal/operations/tenant-by-phone"


def _seed_phone_index(client, *, phone: str, tenant: str):
    from app.core.signup import PHONE_INDEX, canonical_phone

    canonical = canonical_phone(phone, default_cc="966")
    asyncio.run(client.app.state.container.datastore.put(
        PHONE_INDEX, canonical, {"tenant": tenant}))


def test_a_known_owner_phone_resolves_to_his_tenant(client):
    _seed_phone_index(client, phone="0501234567", tenant="tnt_owner_a")
    r = client.post(PATH, json={"phone": "0501234567"}, headers=INTERNAL)
    assert r.status_code == 200, r.text
    assert r.json() == {"found": True, "tenant": "tnt_owner_a"}


def test_the_same_number_in_a_different_written_form_still_resolves(client):
    """+966, 966 and a leading-0 local form are ONE human (canonical_phone's own docstring) —
    the report tool will be handed whatever form a person reads off a phone."""
    _seed_phone_index(client, phone="0509876543", tenant="tnt_owner_b")
    r = client.post(PATH, json={"phone": "+966509876543"}, headers=INTERNAL)
    assert r.status_code == 200, r.text
    assert r.json() == {"found": True, "tenant": "tnt_owner_b"}


def test_an_unknown_phone_returns_found_false_not_404_or_a_guess(client):
    r = client.post(PATH, json={"phone": "0511111111"}, headers=INTERNAL)
    assert r.status_code == 200
    assert r.json() == {"found": False, "tenant": ""}


def test_no_internal_token_is_refused(client):
    r = client.post(PATH, json={"phone": "0501234567"})
    assert r.status_code == 401
