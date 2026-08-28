"""whatsapp-assistant's two internal doors into real bookings: a real-store-backed slot search
for one operator, and real booking creation — both over the internal token, never a user one."""
from __future__ import annotations

import os

import pytest

INTERNAL_TOKEN = "t" * 40


def _make_app(**env_over):
    from app.config import get_settings

    env = {
        "ENV": "test",
        "INTERNAL_SERVICE_TOKEN": INTERNAL_TOKEN,
        "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": "h" * 40,
        "TOKEN_ISSUER": "iss",
        "TOKEN_AUDIENCE": "aud",
        "RATELIMIT_MAX": "1000",
        "PII_SALT": "s" * 32,
    }
    env.update(env_over)
    os.environ.update(env)
    get_settings.cache_clear()
    from app.main import create_app
    from fastapi.testclient import TestClient

    return TestClient(create_app(), raise_server_exceptions=False)


def _stub_ops(client, *, eligible_operator: str = "") -> None:
    """Same helper as test_bookings_api.py's own — a fixed duration + visit gateway + subject_ref,
    optionally refusing every operator but `eligible_operator` (empty string = never refuse)."""
    from app.core.operations import BookingEvents, BookingOperations, DurationLookup, SubjectRefLookup, VisitGateway
    from app.core.stores import BookingStore, WorkingHoursStore
    from app.core.licence import NullLicence

    c = client.app.state.container

    async def duration(tenant, service_ids):
        return 30

    async def visit(**kw):
        return {"visit_id": "vis_1"}

    async def subject_ref(tenant, customer_id):
        return "sub_" + customer_id

    c.bookings = BookingStore(c.datastore)
    c.working_hours = WorkingHoursStore(c.datastore)
    kwargs = dict(
        datastore=c.datastore, bookings=c.bookings,
        durations=DurationLookup(lookup=duration), licence=NullLicence(),
        visits=VisitGateway(create=visit), subject_refs=SubjectRefLookup(lookup=subject_ref),
        events=BookingEvents(publish=None), working_hours=c.working_hours)
    if eligible_operator:
        from app.core.operations import StaffEligibilityLookup

        async def eligible(tenant, service_ids):
            return {sid: [eligible_operator] for sid in service_ids}

        kwargs["staff_eligibility"] = StaffEligibilityLookup(lookup=eligible)
    c.booking_ops = BookingOperations(**kwargs)
    c.branch_scope = None


@pytest.fixture(scope="module")
def env_guard():
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
    from app.config import get_settings
    get_settings.cache_clear()


def _h() -> dict:
    return {"X-Internal-Token": INTERNAL_TOKEN}


def test_create_refuses_without_the_internal_token(env_guard):
    client = _make_app()
    _stub_ops(client)
    r = client.post("/internal/bookings", json={
        "tenant": "t1", "branch_id": "b1", "operator_id": "op1", "customer_id": "c1",
        "service_ids": ["svc1"], "starts_at": 1786860000})
    assert r.status_code == 401


def test_create_a_real_booking_over_the_internal_token(env_guard):
    client = _make_app()
    _stub_ops(client)
    r = client.post("/internal/bookings", json={
        "tenant": "t1", "branch_id": "b1", "operator_id": "op1", "customer_id": "c1",
        "service_ids": ["svc1"], "starts_at": 1786860000, "idempotency_key": "wa-k1"},
        headers=_h())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "booked"
    assert body["operator_id"] == "op1" and body["customer_id"] == "c1"


def test_create_stamps_an_intended_reward_id_as_intent_only(env_guard):
    """The WhatsApp-side of «use my reward with this booking» — never an immediate spend, see
    InternalCreateBookingIn.intended_reward_id's own docstring."""
    client = _make_app()
    _stub_ops(client)
    r = client.post("/internal/bookings", json={
        "tenant": "t1", "branch_id": "b1", "operator_id": "op1", "customer_id": "c1",
        "service_ids": ["svc1"], "starts_at": 1786860000, "idempotency_key": "wa-reward-k",
        "intended_reward_id": "rwd_free_coffee"}, headers=_h())
    assert r.status_code == 200, r.text
    assert r.json()["intended_reward_id"] == "rwd_free_coffee"
    assert r.json()["status"] == "booked", "stamping intent must never itself spend anything"


def test_create_is_idempotent_a_retried_call_returns_the_same_booking(env_guard):
    client = _make_app()
    _stub_ops(client)
    payload = {"tenant": "t1", "branch_id": "b1", "operator_id": "op1", "customer_id": "c1",
              "service_ids": ["svc1"], "starts_at": 1786860000, "idempotency_key": "wa-retry-k"}
    first = client.post("/internal/bookings", json=payload, headers=_h()).json()
    second = client.post("/internal/bookings", json=payload, headers=_h()).json()
    assert first["id"] == second["id"]


def test_create_refuses_an_ineligible_operator_the_write_itself_refuses(env_guard):
    client = _make_app()
    _stub_ops(client, eligible_operator="op-only-this-one")
    r = client.post("/internal/bookings", json={
        "tenant": "t1", "branch_id": "b1", "operator_id": "op-someone-else", "customer_id": "c1",
        "service_ids": ["svc1"], "starts_at": 1786860000}, headers=_h())
    assert r.status_code == 400


def test_nearest_real_slot_refuses_without_the_internal_token(env_guard):
    client = _make_app()
    _stub_ops(client)
    r = client.post("/internal/bookings/nearest-real-slot", json={
        "tenant": "t1", "branch_id": "b1", "operator_id": "op1", "service_ids": ["svc1"],
        "after": 1786860000})
    assert r.status_code == 401


def test_nearest_real_slot_finds_the_first_open_time_for_a_free_operator(env_guard):
    client = _make_app()
    _stub_ops(client)
    r = client.post("/internal/bookings/nearest-real-slot", json={
        "tenant": "t1", "branch_id": "b1", "operator_id": "op1", "service_ids": ["svc1"],
        "after": 1786860000}, headers=_h())
    assert r.status_code == 200
    assert r.json()["starts_at"] is not None


def test_nearest_real_slot_reflects_a_real_existing_booking(env_guard):
    """An operator who already has a booking at the earliest candidate must not be offered it
    again — proves this route reads THIS SERVICE's own store, not a caller-supplied busy list."""
    client = _make_app()
    _stub_ops(client)
    first = client.post("/internal/bookings", json={
        "tenant": "t1", "branch_id": "b1", "operator_id": "op1", "customer_id": "c1",
        "service_ids": ["svc1"], "starts_at": 1786860000}, headers=_h()).json()
    r = client.post("/internal/bookings/nearest-real-slot", json={
        "tenant": "t1", "branch_id": "b1", "operator_id": "op1", "service_ids": ["svc1"],
        "after": 1786860000}, headers=_h())
    assert r.status_code == 200
    assert r.json()["starts_at"] != first["starts_at"]


def test_create_is_isolated_per_tenant_the_same_idempotency_key_never_collides_across_tenants(
        env_guard):
    """The double-tap guard (`by_idempotency_key`) is looked up WITHOUT a tenant filter unless
    the store itself scopes it — two shops that both happen to send `idempotency_key="k1"` (a
    UUID a shop's own POS system minted, with no coordination with any other shop) must each get
    their OWN booking, never tenant B's write silently returned to tenant A as "already done"."""
    client = _make_app()
    _stub_ops(client)
    same_key = {"branch_id": "b1", "operator_id": "op1", "customer_id": "c1",
               "service_ids": ["svc1"], "starts_at": 1786860000, "idempotency_key": "shared-k1"}
    a = client.post("/internal/bookings", json={"tenant": "tnt_iso_a", **same_key},
                    headers=_h()).json()
    b = client.post("/internal/bookings", json={"tenant": "tnt_iso_b", **same_key},
                    headers=_h()).json()
    assert a["id"] != b["id"]
    # A RETRY under tenant A, same key, must still return A's OWN booking — never B's, which the
    # idempotency lookup could have returned instead if it were not scoped by tenant.
    retried_a = client.post("/internal/bookings", json={"tenant": "tnt_iso_a", **same_key},
                            headers=_h()).json()
    assert retried_a["id"] == a["id"]


def test_nearest_real_slot_is_isolated_per_tenant_one_tenants_booking_never_busies_another(
        env_guard):
    """The SAME operator_id string, in two different tenants, is two different operators — a
    booking filed for tnt_a's "op1" must never make tnt_b's own "op1" look busy."""
    client = _make_app()
    _stub_ops(client)
    client.post("/internal/bookings", json={
        "tenant": "tnt_busy_a", "branch_id": "b1", "operator_id": "op1", "customer_id": "c1",
        "service_ids": ["svc1"], "starts_at": 1786860000}, headers=_h())

    r = client.post("/internal/bookings/nearest-real-slot", json={
        "tenant": "tnt_busy_b", "branch_id": "b1", "operator_id": "op1", "service_ids": ["svc1"],
        "after": 1786860000}, headers=_h())
    assert r.status_code == 200
    # tnt_b's operator has NO bookings — the earliest candidate is the very slot tnt_a just took.
    assert r.json()["starts_at"] == 1786860000
