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

    async def duration(tenant, service_ids, quantities=None):
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


def test_create_forwards_created_by_so_an_ai_made_booking_is_attributable(env_guard):
    """whatsapp-assistant's own RealBookingProvider now sends `created_by="whatsapp-assistant"`
    on every booking it makes (booking_assignment.py) — this proves the internal route actually
    forwards it onto the real row instead of silently dropping it (the old behaviour, when
    `created_by` was left at its "" default regardless of what the caller sent)."""
    client = _make_app()
    _stub_ops(client)
    r = client.post("/internal/bookings", json={
        "tenant": "t1", "branch_id": "b1", "operator_id": "op1", "customer_id": "c1",
        "service_ids": ["svc1"], "starts_at": 1786860000, "idempotency_key": "wa-attr-k",
        "created_by": "whatsapp-assistant"}, headers=_h())
    assert r.status_code == 200, r.text
    assert r.json()["created_by"] == "whatsapp-assistant"


def test_create_without_created_by_still_defaults_to_blank_never_guessed(env_guard):
    """A caller that has not been wired to send an actor (or a genuine staff-made booking through
    a different route) must not be mislabelled as AI-made."""
    client = _make_app()
    _stub_ops(client)
    r = client.post("/internal/bookings", json={
        "tenant": "t1", "branch_id": "b1", "operator_id": "op1", "customer_id": "c1",
        "service_ids": ["svc1"], "starts_at": 1786860000, "idempotency_key": "wa-noattr-k"},
        headers=_h())
    assert r.status_code == 200, r.text
    assert r.json()["created_by"] == ""


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


def test_nearest_real_slot_with_exclude_booking_id_offers_the_bookings_own_current_time(env_guard):
    """The booking-management-via-WhatsApp reschedule check's own dependency: EXCLUDING a
    booking's own id must make its own current time available again — the booking is not a
    conflict with itself. Without `exclude_booking_id`, this same query (see the test above)
    correctly treats it as busy; this proves the exclusion actually flips that."""
    client = _make_app()
    _stub_ops(client)
    booking = client.post("/internal/bookings", json={
        "tenant": "t1", "branch_id": "b1", "operator_id": "op1", "customer_id": "c1",
        "service_ids": ["svc1"], "starts_at": 1786860000}, headers=_h()).json()
    r = client.post("/internal/bookings/nearest-real-slot", json={
        "tenant": "t1", "branch_id": "b1", "operator_id": "op1", "service_ids": ["svc1"],
        "after": 1786860000, "exclude_booking_id": booking["id"]}, headers=_h())
    assert r.status_code == 200
    assert r.json()["starts_at"] == booking["starts_at"]


# ── /internal/bookings/nearest-any-real — whatsapp-assistant's own real algorithm, phase 4 ─────

def test_nearest_any_real_refuses_without_the_internal_token(env_guard):
    client = _make_app()
    _stub_ops(client)
    r = client.post("/internal/bookings/nearest-any-real", json={
        "tenant": "t1", "branch_id": "b1", "operator_ids": ["op1"], "service_ids": ["svc1"],
        "after": 1786860000})
    assert r.status_code == 401


def test_nearest_any_real_merges_across_the_whole_eligible_pool(env_guard):
    """Two candidates, both free — the SAME merge engine the console's own nearest-any uses
    (BookingOperations.nearest_slots_any), reached from the internal tier instead of a user JWT."""
    client = _make_app()
    _stub_ops(client)
    r = client.post("/internal/bookings/nearest-any-real", json={
        "tenant": "t1", "branch_id": "b1", "operator_ids": ["op1", "op2"],
        "service_ids": ["svc1"], "after": 1786860000, "max_slots": 1}, headers=_h())
    assert r.status_code == 200, r.text
    slots = r.json()["slots"]
    assert len(slots) == 1
    assert slots[0]["operator_id"] in ("op1", "op2")
    assert slots[0]["starts_at"] == 1786860000


def test_nearest_any_real_skips_an_operator_already_booked_at_the_earliest_candidate(env_guard):
    client = _make_app()
    _stub_ops(client)
    client.post("/internal/bookings", json={
        "tenant": "t1", "branch_id": "b1", "operator_id": "op1", "customer_id": "c1",
        "service_ids": ["svc1"], "starts_at": 1786860000}, headers=_h())
    r = client.post("/internal/bookings/nearest-any-real", json={
        "tenant": "t1", "branch_id": "b1", "operator_ids": ["op1", "op2"],
        "service_ids": ["svc1"], "after": 1786860000, "max_slots": 1}, headers=_h())
    assert r.status_code == 200, r.text
    # op1 is busy at exactly this instant; op2 is free, so op2 wins the earliest slot.
    assert r.json()["slots"][0]["operator_id"] == "op2"


def test_nearest_any_real_respects_the_callers_own_eligible_pool(env_guard):
    """`_stub_ops(eligible_operator=...)` refuses every OTHER operator server-side — proves this
    route does not just trust the caller's `operator_ids` blindly."""
    client = _make_app()
    _stub_ops(client, eligible_operator="op-only-this-one")
    r = client.post("/internal/bookings/nearest-any-real", json={
        "tenant": "t1", "branch_id": "b1", "operator_ids": ["op-someone-else"],
        "service_ids": ["svc1"], "after": 1786860000}, headers=_h())
    assert r.status_code == 400


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


# ── customer self-service (booking-management-via-WhatsApp): for-customer / cancel / reschedule ──

def _book(client, **over) -> dict:
    payload = {"tenant": "t1", "branch_id": "b1", "operator_id": "op1", "customer_id": "c1",
              "service_ids": ["svc1"], "starts_at": 1786860000}
    payload.update(over)
    return client.post("/internal/bookings", json=payload, headers=_h()).json()


def test_for_customer_refuses_without_the_internal_token(env_guard):
    client = _make_app()
    _stub_ops(client)
    r = client.post("/internal/bookings/for-customer", json={"tenant": "t1", "customer_id": "c1"})
    assert r.status_code == 401


def test_for_customer_returns_only_that_customers_own_bookings(env_guard):
    client = _make_app()
    _stub_ops(client)
    mine = _book(client, customer_id="c1", idempotency_key="k-mine")
    _book(client, customer_id="c2", idempotency_key="k-other")   # a different customer entirely
    r = client.post("/internal/bookings/for-customer", json={"tenant": "t1", "customer_id": "c1"},
                    headers=_h())
    assert r.status_code == 200
    ids = [b["id"] for b in r.json()["bookings"]]
    assert ids == [mine["id"]]


# ── branch scoping (booking-management-via-WhatsApp, cross-branch fix) ───────────────────────────
#
# A per_branch shop's WhatsApp number IS a branch: a customer texting branch B's number must never
# see/cancel/reschedule a booking she made at branch A, even though both are genuinely hers.

def test_for_customer_with_no_branch_id_sees_every_branch_unchanged(env_guard):
    """No regression for a central shop (or a session with no branch fixed yet): omitting
    branch_id keeps today's behaviour exactly — every one of her bookings, any branch."""
    client = _make_app()
    _stub_ops(client)
    a = _book(client, branch_id="branch-a", idempotency_key="k-branch-a")
    b = _book(client, branch_id="branch-b", idempotency_key="k-branch-b")
    r = client.post("/internal/bookings/for-customer", json={"tenant": "t1", "customer_id": "c1"},
                    headers=_h())
    ids = {x["id"] for x in r.json()["bookings"]}
    assert ids == {a["id"], b["id"]}


def test_for_customer_with_a_branch_id_sees_only_that_branch(env_guard):
    client = _make_app()
    _stub_ops(client)
    a = _book(client, branch_id="branch-a", idempotency_key="k-branch-a-2")
    _book(client, branch_id="branch-b", idempotency_key="k-branch-b-2")
    r = client.post("/internal/bookings/for-customer",
                    json={"tenant": "t1", "customer_id": "c1", "branch_id": "branch-a"},
                    headers=_h())
    ids = [x["id"] for x in r.json()["bookings"]]
    assert ids == [a["id"]]


def test_cancel_from_a_different_branch_is_refused_identically_to_not_found(env_guard):
    """SAME enumeration-oracle discipline as the cross-customer refusal: 'exists, wrong branch'
    must read exactly like 'does not exist', never distinguished."""
    client = _make_app()
    _stub_ops(client)
    booking = _book(client, branch_id="branch-a", idempotency_key="k-cancel-branch")
    r = client.post(f"/internal/bookings/{booking['id']}/cancel",
                    json={"tenant": "t1", "customer_id": "c1", "branch_id": "branch-b"},
                    headers=_h())
    assert r.status_code == 404
    ghost = client.post("/internal/bookings/does-not-exist/cancel",
                        json={"tenant": "t1", "customer_id": "c1", "branch_id": "branch-b"},
                        headers=_h())
    assert ghost.status_code == 404
    assert r.json()["error"] == ghost.json()["error"]
    # AND THE REAL BOOKING IS UNTOUCHED — the refused cross-branch attempt must not have cancelled
    # it underneath the 404.
    mine = client.post("/internal/bookings/for-customer", json={"tenant": "t1", "customer_id": "c1"},
                       headers=_h()).json()["bookings"][0]
    assert mine["status"] == "booked"


def test_cancel_from_the_same_branch_still_succeeds(env_guard):
    client = _make_app()
    _stub_ops(client)
    booking = _book(client, branch_id="branch-a", idempotency_key="k-cancel-branch-ok")
    r = client.post(f"/internal/bookings/{booking['id']}/cancel",
                    json={"tenant": "t1", "customer_id": "c1", "branch_id": "branch-a"},
                    headers=_h())
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "cancelled"


def test_reschedule_from_a_different_branch_is_refused_and_leaves_the_booking_untouched(env_guard):
    client = _make_app()
    _stub_ops(client)
    booking = _book(client, branch_id="branch-a", idempotency_key="k-resch-branch")
    r = client.post(f"/internal/bookings/{booking['id']}/reschedule",
                    json={"tenant": "t1", "customer_id": "c1", "starts_at": 1786870000,
                         "branch_id": "branch-b"},
                    headers=_h())
    assert r.status_code == 404
    mine = client.post("/internal/bookings/for-customer", json={"tenant": "t1", "customer_id": "c1"},
                       headers=_h()).json()["bookings"][0]
    assert mine["starts_at"] == 1786860000


# ── for-subject: the same read, keyed by the pseudonym (the case-timeline tool's own entry) ──────

def test_for_subject_refuses_without_the_internal_token(env_guard):
    client = _make_app()
    _stub_ops(client)
    r = client.post("/internal/bookings/for-subject", json={"tenant": "t1", "subject_ref": "sub_c1"})
    assert r.status_code == 401


def test_for_subject_returns_only_that_subjects_own_bookings(env_guard):
    """_stub_ops's own subject_ref resolver is `subject_ref(tenant, customer_id) -> "sub_" +
    customer_id` — so a booking made for customer_id="c1" carries subject_ref="sub_c1"."""
    client = _make_app()
    _stub_ops(client)
    mine = _book(client, customer_id="c1", idempotency_key="k-mine-subj")
    _book(client, customer_id="c2", idempotency_key="k-other-subj")   # a different customer
    r = client.post("/internal/bookings/for-subject",
                    json={"tenant": "t1", "subject_ref": "sub_c1"}, headers=_h())
    assert r.status_code == 200
    ids = [b["id"] for b in r.json()["bookings"]]
    assert ids == [mine["id"]]


def test_for_subject_and_for_customer_agree_on_the_same_bookings_own_history(env_guard):
    """Both routes must describe the SAME real history for the same real customer — proving the
    subject_ref path is not a second, looser source of truth."""
    client = _make_app()
    _stub_ops(client)
    _book(client, customer_id="c1", idempotency_key="k-agree-1")
    _book(client, customer_id="c1", starts_at=1786870000, idempotency_key="k-agree-2")
    by_customer = client.post("/internal/bookings/for-customer",
                              json={"tenant": "t1", "customer_id": "c1"}, headers=_h()).json()
    by_subject = client.post("/internal/bookings/for-subject",
                             json={"tenant": "t1", "subject_ref": "sub_c1"}, headers=_h()).json()
    assert {b["id"] for b in by_customer["bookings"]} == {b["id"] for b in by_subject["bookings"]}


def test_for_subject_refuses_a_malformed_body_rather_than_500ing(env_guard):
    client = _make_app()
    _stub_ops(client)
    r = client.post("/internal/bookings/for-subject", json={"tenant": "t1"}, headers=_h())
    assert r.status_code == 422   # subject_ref missing — a validation error, never a 500


def test_for_subject_is_isolated_per_tenant(env_guard):
    client = _make_app()
    _stub_ops(client)
    _book(client, tenant="tnt_subj_a", customer_id="same-id", idempotency_key="k-subj-a")
    _book(client, tenant="tnt_subj_b", customer_id="same-id", idempotency_key="k-subj-b")
    r = client.post("/internal/bookings/for-subject",
                    json={"tenant": "tnt_subj_a", "subject_ref": "sub_same-id"}, headers=_h())
    assert len(r.json()["bookings"]) == 1


def test_for_subject_returns_empty_never_an_error_for_an_unknown_subject(env_guard):
    client = _make_app()
    _stub_ops(client)
    r = client.post("/internal/bookings/for-subject",
                    json={"tenant": "t1", "subject_ref": "sub_never-existed"}, headers=_h())
    assert r.status_code == 200
    assert r.json()["bookings"] == []


def test_cancel_by_the_owning_customer_succeeds(env_guard):
    client = _make_app()
    _stub_ops(client)
    booking = _book(client, idempotency_key="k-cancel-own")
    r = client.post(f"/internal/bookings/{booking['id']}/cancel",
                    json={"tenant": "t1", "customer_id": "c1", "reason": "غيّرت رأيي"},
                    headers=_h())
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "cancelled"


def test_cancel_by_a_different_customer_is_refused_with_the_generic_not_found_reason(env_guard):
    """SECURITY: a customer must never be able to cancel another customer's booking — and the
    refusal for "belongs to someone else" must read IDENTICALLY to "does not exist", never
    distinguishing the two (an enumeration oracle otherwise)."""
    client = _make_app()
    _stub_ops(client)
    booking = _book(client, customer_id="c1", idempotency_key="k-cancel-cross")
    r = client.post(f"/internal/bookings/{booking['id']}/cancel",
                    json={"tenant": "t1", "customer_id": "c2-not-the-owner", "reason": ""},
                    headers=_h())
    assert r.status_code == 404
    ghost = client.post("/internal/bookings/does-not-exist/cancel",
                        json={"tenant": "t1", "customer_id": "c2-not-the-owner", "reason": ""},
                        headers=_h())
    assert ghost.status_code == 404
    # Same shape and reason text — `request_id` legitimately differs per call, not a distinguisher.
    assert r.json()["error"] == ghost.json()["error"], \
        "existing-but-not-mine and never-existed must read identically"
    # SECURITY, THE PART THAT ACTUALLY MATTERS: the refused attempt must not have touched the
    # booking — a 404 that came back AFTER the write already went through underneath would be
    # far worse than no check at all. Proven by re-reading the booking as its REAL owner.
    mine = client.post("/internal/bookings/for-customer", json={"tenant": "t1", "customer_id": "c1"},
                       headers=_h()).json()["bookings"][0]
    assert mine["status"] == "booked"


def test_cancel_is_idempotent_an_already_cancelled_booking_is_a_no_op_success(env_guard):
    client = _make_app()
    _stub_ops(client)
    booking = _book(client, idempotency_key="k-cancel-twice")
    first = client.post(f"/internal/bookings/{booking['id']}/cancel",
                        json={"tenant": "t1", "customer_id": "c1"}, headers=_h())
    second = client.post(f"/internal/bookings/{booking['id']}/cancel",
                         json={"tenant": "t1", "customer_id": "c1"}, headers=_h())
    assert first.status_code == 200 and second.status_code == 200
    assert second.json()["status"] == "cancelled"


def test_reschedule_by_the_owning_customer_succeeds(env_guard):
    client = _make_app()
    _stub_ops(client)
    booking = _book(client, idempotency_key="k-resch-own")
    r = client.post(f"/internal/bookings/{booking['id']}/reschedule",
                    json={"tenant": "t1", "customer_id": "c1", "starts_at": 1786870000},
                    headers=_h())
    assert r.status_code == 200, r.text
    assert r.json()["starts_at"] == 1786870000


def test_reschedule_by_a_different_customer_is_refused(env_guard):
    client = _make_app()
    _stub_ops(client)
    booking = _book(client, customer_id="c1", idempotency_key="k-resch-cross")
    r = client.post(f"/internal/bookings/{booking['id']}/reschedule",
                    json={"tenant": "t1", "customer_id": "c2-not-the-owner",
                         "starts_at": 1786870000}, headers=_h())
    assert r.status_code == 404
    # SECURITY: the booking must be UNCHANGED — a refused reschedule attempt from someone who
    # does not own it must never move the real appointment even by side effect.
    mine = client.post("/internal/bookings/for-customer", json={"tenant": "t1", "customer_id": "c1"},
                       headers=_h()).json()["bookings"][0]
    assert mine["starts_at"] == 1786860000


def test_reschedule_refuses_a_double_booked_slot_the_write_itself_refuses(env_guard):
    client = _make_app()
    _stub_ops(client)
    _book(client, customer_id="c1", operator_id="op1", starts_at=1786870000,
         idempotency_key="k-resch-conflict-a")
    booking = _book(client, customer_id="c1", operator_id="op1", starts_at=1786860000,
                    idempotency_key="k-resch-conflict-b")
    r = client.post(f"/internal/bookings/{booking['id']}/reschedule",
                    json={"tenant": "t1", "customer_id": "c1", "starts_at": 1786870000},
                    headers=_h())
    assert r.status_code == 409


def test_reschedule_refuses_an_already_cancelled_booking(env_guard):
    client = _make_app()
    _stub_ops(client)
    booking = _book(client, idempotency_key="k-resch-on-cancelled")
    client.post(f"/internal/bookings/{booking['id']}/cancel",
               json={"tenant": "t1", "customer_id": "c1"}, headers=_h())
    r = client.post(f"/internal/bookings/{booking['id']}/reschedule",
                    json={"tenant": "t1", "customer_id": "c1", "starts_at": 1786870000},
                    headers=_h())
    assert r.status_code == 400


def test_cancel_refuses_an_attended_booking(env_guard):
    client = _make_app()
    _stub_ops(client)
    booking = _book(client, idempotency_key="k-cancel-attended")
    attended = client.app.state.container
    import asyncio
    asyncio.run(attended.booking_ops.attend("t1", booking["id"], 0))
    r = client.post(f"/internal/bookings/{booking['id']}/cancel",
                    json={"tenant": "t1", "customer_id": "c1"}, headers=_h())
    assert r.status_code == 400


def test_reschedule_to_the_exact_same_time_is_a_harmless_no_op_success(env_guard):
    """A customer confirming a reschedule proposal whose target happens to equal the booking's
    current time (e.g. a redelivered webhook replaying the same confirm) must not be treated as a
    conflict against itself."""
    client = _make_app()
    _stub_ops(client)
    booking = _book(client, idempotency_key="k-resch-same-time")
    r = client.post(f"/internal/bookings/{booking['id']}/reschedule",
                    json={"tenant": "t1", "customer_id": "c1", "starts_at": booking["starts_at"]},
                    headers=_h())
    assert r.status_code == 200, r.text
    assert r.json()["starts_at"] == booking["starts_at"]


def test_cancel_with_no_reason_supplied_succeeds(env_guard):
    client = _make_app()
    _stub_ops(client)
    booking = _book(client, idempotency_key="k-cancel-no-reason")
    r = client.post(f"/internal/bookings/{booking['id']}/cancel",
                    json={"tenant": "t1", "customer_id": "c1"}, headers=_h())
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"


def test_for_customer_refuses_a_malformed_body_rather_than_500ing(env_guard):
    client = _make_app()
    _stub_ops(client)
    r = client.post("/internal/bookings/for-customer", json={"tenant": "t1"}, headers=_h())
    assert r.status_code == 422   # customer_id missing — a validation error, never a 500


def test_reschedule_refuses_a_nonpositive_starts_at(env_guard):
    client = _make_app()
    _stub_ops(client)
    booking = _book(client, idempotency_key="k-resch-bad-time")
    r = client.post(f"/internal/bookings/{booking['id']}/reschedule",
                    json={"tenant": "t1", "customer_id": "c1", "starts_at": 0}, headers=_h())
    assert r.status_code == 422


def test_for_customer_is_isolated_per_tenant(env_guard):
    client = _make_app()
    _stub_ops(client)
    _book(client, tenant="tnt_fc_a", customer_id="same-id", idempotency_key="k-fc-a")
    _book(client, tenant="tnt_fc_b", customer_id="same-id", idempotency_key="k-fc-b")
    r = client.post("/internal/bookings/for-customer",
                    json={"tenant": "tnt_fc_a", "customer_id": "same-id"}, headers=_h())
    assert len(r.json()["bookings"]) == 1


# ── by-actor: bookings-service's answer to upsell_report.py's own documented follow-up ──────────

def test_by_actor_refuses_without_the_internal_token(env_guard):
    client = _make_app()
    _stub_ops(client)
    r = client.post("/internal/bookings/by-actor",
                    json={"tenant": "t1", "created_by": "whatsapp-assistant"})
    assert r.status_code == 401


def test_by_actor_requires_created_by_never_a_wildcard(env_guard):
    client = _make_app()
    _stub_ops(client)
    r = client.post("/internal/bookings/by-actor", json={"tenant": "t1"}, headers=_h())
    assert r.status_code == 422


def test_by_actor_returns_only_that_actors_own_bookings(env_guard):
    client = _make_app()
    _stub_ops(client)
    ai = _book(client, customer_id="c1", idempotency_key="k-actor-ai", created_by="whatsapp-assistant")
    _book(client, customer_id="c2", idempotency_key="k-actor-staff")   # created_by="" (staff)
    r = client.post("/internal/bookings/by-actor",
                    json={"tenant": "t1", "created_by": "whatsapp-assistant"}, headers=_h())
    assert r.status_code == 200
    ids = [b["id"] for b in r.json()["bookings"]]
    assert ids == [ai["id"]]
    assert r.json()["truncated"] is False


def test_by_actor_projection_never_leaks_customer_id_or_note(env_guard):
    """A cross-service revenue report has no business seeing who the customer is or what note was
    left — proves this route serves `_actor_public`'s narrower shape, not `Booking.public()`."""
    client = _make_app()
    _stub_ops(client)
    _book(client, customer_id="c1", idempotency_key="k-actor-proj", created_by="whatsapp-assistant",
         note="ملاحظة خاصة")
    r = client.post("/internal/bookings/by-actor",
                    json={"tenant": "t1", "created_by": "whatsapp-assistant"}, headers=_h())
    row = r.json()["bookings"][0]
    assert "customer_id" not in row and "note" not in row and "idempotency_key" not in row
    assert row["status"] == "booked" and row["created_by"] == "whatsapp-assistant"


def test_by_actor_filters_by_branch_id(env_guard):
    client = _make_app()
    _stub_ops(client)
    a = _book(client, branch_id="branch-a", idempotency_key="k-actor-branch-a",
             created_by="whatsapp-assistant")
    _book(client, branch_id="branch-b", idempotency_key="k-actor-branch-b",
         created_by="whatsapp-assistant")
    r = client.post("/internal/bookings/by-actor",
                    json={"tenant": "t1", "created_by": "whatsapp-assistant",
                         "branch_id": "branch-a"}, headers=_h())
    ids = [b["id"] for b in r.json()["bookings"]]
    assert ids == [a["id"]]


def test_by_actor_is_isolated_per_tenant(env_guard):
    client = _make_app()
    _stub_ops(client)
    _book(client, tenant="tnt_actor_a", customer_id="c1", idempotency_key="k-actor-tnt-a",
         created_by="whatsapp-assistant")
    _book(client, tenant="tnt_actor_b", customer_id="c1", idempotency_key="k-actor-tnt-b",
         created_by="whatsapp-assistant")
    r = client.post("/internal/bookings/by-actor",
                    json={"tenant": "tnt_actor_a", "created_by": "whatsapp-assistant"},
                    headers=_h())
    assert len(r.json()["bookings"]) == 1


def test_by_actor_returns_empty_never_an_error_for_an_actor_with_no_bookings(env_guard):
    client = _make_app()
    _stub_ops(client)
    r = client.post("/internal/bookings/by-actor",
                    json={"tenant": "t1", "created_by": "never-booked-anything"}, headers=_h())
    assert r.status_code == 200
    assert r.json() == {"bookings": [], "truncated": False}


# ── attend (the till-integration gap both 2026-09-13/14 audits named as the largest hole) ───────

def test_attend_refuses_without_the_internal_token(env_guard):
    client = _make_app()
    _stub_ops(client)
    r = client.post("/internal/bookings/some-id/attend",
                    json={"tenant": "t1", "customer_id": "c1"})
    assert r.status_code == 401


def test_attend_turns_a_booking_into_a_real_visit(env_guard):
    client = _make_app()
    _stub_ops(client)
    booking = _book(client, idempotency_key="k-attend-1")
    r = client.post(f"/internal/bookings/{booking['id']}/attend",
                    json={"tenant": "t1", "customer_id": "c1"}, headers=_h())
    assert r.status_code == 200
    assert r.json()["status"] == "attended"


def test_attend_is_idempotent_a_retried_tap_returns_the_same_booking(env_guard):
    """The till's own retry-on-timeout must not double-fire the visit or double-spend a reward —
    attend() itself is idempotent (core/operations.py's own note), and this route must not add a
    second check on top that would break that."""
    client = _make_app()
    _stub_ops(client)
    booking = _book(client, idempotency_key="k-attend-2")
    first = client.post(f"/internal/bookings/{booking['id']}/attend",
                        json={"tenant": "t1", "customer_id": "c1"}, headers=_h())
    second = client.post(f"/internal/bookings/{booking['id']}/attend",
                         json={"tenant": "t1", "customer_id": "c1"}, headers=_h())
    assert first.status_code == second.status_code == 200
    assert first.json()["status"] == second.json()["status"] == "attended"


def test_attend_from_a_different_branch_is_refused_identically_to_not_found(env_guard):
    """SAME enumeration-oracle discipline as cancel/reschedule — 'exists, wrong branch' must read
    exactly like 'does not exist'."""
    client = _make_app()
    _stub_ops(client)
    booking = _book(client, branch_id="branch-a", idempotency_key="k-attend-branch")
    r = client.post(f"/internal/bookings/{booking['id']}/attend",
                    json={"tenant": "t1", "customer_id": "c1", "branch_id": "branch-b"},
                    headers=_h())
    assert r.status_code == 404
    ghost = client.post("/internal/bookings/does-not-exist/attend",
                        json={"tenant": "t1", "customer_id": "c1", "branch_id": "branch-b"},
                        headers=_h())
    assert ghost.status_code == 404
    assert r.json()["error"] == ghost.json()["error"]
    # AND THE REAL BOOKING IS UNTOUCHED by the refused cross-branch attempt.
    mine = client.post("/internal/bookings/for-customer", json={"tenant": "t1", "customer_id": "c1"},
                       headers=_h()).json()["bookings"][0]
    assert mine["status"] == "booked"


def test_attend_refuses_a_different_customers_booking(env_guard):
    client = _make_app()
    _stub_ops(client)
    booking = _book(client, customer_id="c1", idempotency_key="k-attend-other-cust")
    r = client.post(f"/internal/bookings/{booking['id']}/attend",
                    json={"tenant": "t1", "customer_id": "c2"}, headers=_h())
    assert r.status_code == 404


def test_attend_on_an_already_cancelled_booking_is_refused(env_guard):
    client = _make_app()
    _stub_ops(client)
    booking = _book(client, idempotency_key="k-attend-cancelled")
    client.post(f"/internal/bookings/{booking['id']}/cancel",
               json={"tenant": "t1", "customer_id": "c1"}, headers=_h())
    r = client.post(f"/internal/bookings/{booking['id']}/attend",
                    json={"tenant": "t1", "customer_id": "c1"}, headers=_h())
    assert r.status_code == 400
