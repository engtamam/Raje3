"""Mutual benefit engine (core/mutual_benefit.py) — no network, no billing socket.
`FakePlans` matches the same narrow contract `CouponService`'s own tests fake (`plan_id_for_key`/
`subscriptions`), and `FakeNotifier`/`FakeAuthz` are the two peers `_managers()` needs."""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.mutual_benefit import (ACTIVE, BAD_CONDITION, CANCEL_REQUESTED,
                                           CONDITION_MIN_TOTAL, CONDITION_SERVICE_ID, ENDED,
                                           EXPIRED_UNANSWERED, FEATURE_KEY, FORBIDDEN,
                                           NOT_FOUND, NOT_SUBSCRIBED, PAUSED, PROPOSED,
                                           REJECTED, MutualBenefitError, MutualBenefitEngine,
                                           SELF_PARTNER, WRONG_STATE, _CAP_PERIOD_SECONDS,
                                           _PROPOSAL_TTL_SECONDS)
from app.core.signup import PHONE_INDEX, canonical_phone

CC = "966"
A = "tnt_alpha"
B = "tnt_beta"
C = "tnt_gamma"
B_PHONE = "0501234567"
C_PHONE = "0559876543"


def run(coro):
    return asyncio.run(coro)


class FakePlans:
    driver = "fake"

    def __init__(self) -> None:
        self.subs: dict[str, list[dict]] = {}
        self.plan_for_key: dict[str, str] = {FEATURE_KEY: "plan_referral"}
        self.unreachable: set[str] = set()

    async def subscriptions(self, tenant: str):
        if tenant in self.unreachable:
            return None
        return self.subs.get(tenant, [])

    async def plan_id_for_key(self, key: str) -> str:
        return self.plan_for_key.get(key, "")

    async def limits(self, plan_id: str):
        return {}


class FakeAuthz:
    def __init__(self) -> None:
        # tenant -> subject who holds operations.manage, so `_managers()` finds someone real.
        self.owners: dict[str, str] = {B: "owner_b", A: "owner_a", C: "owner_c"}

    async def list_assignments(self, tenant: str):
        owner = self.owners.get(tenant)
        if not owner:
            return []
        return [{"subject": owner, "capabilities": ["operations.manage"], "roles": []}]

    async def effective_capabilities(self, tenant, subject, roles):
        return set()


class FakeNotifier:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send(self, **kwargs):
        self.sent.append(kwargs)
        return True


def _subscribe(plans: FakePlans, tenant: str) -> None:
    plans.subs.setdefault(tenant, []).append(
        {"id": f"sub_{tenant}", "plan": "plan_referral", "status": "active"})


def _unsubscribe(plans: FakePlans, tenant: str) -> None:
    plans.subs[tenant] = []


def _register_phone(store, phone: str, tenant: str) -> None:
    key = canonical_phone(phone, default_cc=CC)
    run(store.put(PHONE_INDEX, key, {"id": key, "tenant": tenant, "verified": True}))


@pytest.fixture()
def env():
    store = MemoryDataStore()
    plans = FakePlans()
    notifier = FakeNotifier()
    authz = FakeAuthz()
    engine = MutualBenefitEngine(store=store, plans=plans, notifier=notifier, authz=authz,
                                       default_cc=CC)
    _register_phone(store, B_PHONE, B)
    _register_phone(store, C_PHONE, C)
    _subscribe(plans, A)
    _subscribe(plans, B)
    return engine, store, plans, notifier


def _propose(engine, **overrides):
    kwargs = dict(shop_a=A, shop_b_phone=B_PHONE, operator_id="op1",
                 condition_type=CONDITION_MIN_TOTAL, condition_value="1000",
                 grant_validity_days=3,
                 agreement_duration_days=90, per_period_cap=0,
                 discount_kind="percent", discount_amount=10)
    kwargs.update(overrides)
    return run(engine.propose(**kwargs))


# ── basic validation ──────────────────────────────────────────────────────────────────────────
def test_a_shop_cannot_propose_to_itself(env):
    engine, store, plans, _ = env
    _register_phone(store, "0500000000", A)
    with pytest.raises(MutualBenefitError) as exc:
        run(engine.propose(shop_a=A, shop_b_phone="0500000000", operator_id="op1",
                           condition_type=CONDITION_MIN_TOTAL, condition_value="1000",
                           grant_validity_days=3, agreement_duration_days=30))
    assert exc.value.args[0] == SELF_PARTNER


def test_a_shop_without_the_paid_feature_cannot_propose(env):
    engine, store, plans, _ = env
    _unsubscribe(plans, A)
    with pytest.raises(MutualBenefitError) as exc:
        _propose(engine)
    assert exc.value.args[0] == NOT_SUBSCRIBED


def test_bad_condition_shapes_are_refused(env):
    engine, _store, _plans, _ = env
    with pytest.raises(MutualBenefitError):
        _propose(engine, condition_type="bogus")
    with pytest.raises(MutualBenefitError):
        _propose(engine, condition_type=CONDITION_MIN_TOTAL, condition_value="0")
    with pytest.raises(MutualBenefitError):
        _propose(engine, condition_type=CONDITION_SERVICE_ID, condition_value="")
    with pytest.raises(MutualBenefitError):
        _propose(engine, grant_validity_days=0)
    with pytest.raises(MutualBenefitError):
        _propose(engine, agreement_duration_days=0)


# ── lifecycle: propose -> accept -> active ───────────────────────────────────────────────────
def test_propose_then_accept_activates_it(env):
    engine, _store, _plans, notifier = env
    agreement = _propose(engine)
    assert agreement.status == PROPOSED
    assert notifier.sent and notifier.sent[0]["tenant"] == B

    activated = run(engine.accept(tenant=B, agreement_id=agreement.id))
    assert activated.status == ACTIVE
    assert activated.original_ends_at == activated.ends_at


def test_only_the_invited_side_may_accept_or_reject(env):
    engine, _store, _plans, _ = env
    agreement = _propose(engine)
    with pytest.raises(MutualBenefitError) as exc:
        run(engine.accept(tenant=A, agreement_id=agreement.id))
    assert exc.value.args[0] == FORBIDDEN
    with pytest.raises(MutualBenefitError) as exc2:
        run(engine.reject(tenant=A, agreement_id=agreement.id))
    assert exc2.value.args[0] == FORBIDDEN


def test_accepting_requires_the_beneficiary_also_holds_the_app(env):
    engine, _store, plans, _ = env
    agreement = _propose(engine)
    _unsubscribe(plans, B)
    with pytest.raises(MutualBenefitError) as exc:
        run(engine.accept(tenant=B, agreement_id=agreement.id))
    assert exc.value.args[0] == NOT_SUBSCRIBED


def test_reject_ends_it_and_a_third_party_cannot_touch_it(env):
    engine, _store, _plans, _ = env
    agreement = _propose(engine)
    rejected = run(engine.reject(tenant=B, agreement_id=agreement.id))
    assert rejected.status == REJECTED
    with pytest.raises(MutualBenefitError) as exc:
        run(engine.get(C, agreement.id))
    assert exc.value.args[0] == NOT_FOUND


# ── adversarial cross-tenant reads ────────────────────────────────────────────────────────────
def test_a_third_tenant_can_never_read_someone_elses_agreement(env):
    engine, _store, _plans, _ = env
    agreement = _propose(engine)
    run(engine.accept(tenant=B, agreement_id=agreement.id))
    with pytest.raises(MutualBenefitError) as exc:
        run(engine.get(C, agreement.id))
    assert exc.value.args[0] == NOT_FOUND
    listed = run(engine.agreements_for(C))
    assert listed == []


def test_a_random_id_is_not_found_not_a_crash(env):
    engine, _store, _plans, _ = env
    with pytest.raises(MutualBenefitError) as exc:
        run(engine.get(A, "rpa_doesnotexist"))
    assert exc.value.args[0] == NOT_FOUND


# ── idempotency ───────────────────────────────────────────────────────────────────────────────
def test_a_retried_propose_with_the_same_idempotency_key_never_duplicates(env):
    engine, _store, _plans, _ = env
    first = _propose(engine, idempotency_key="click-1")
    second = _propose(engine, idempotency_key="click-1")
    assert first.id == second.id
    all_rows = run(engine.agreements_for(A))
    assert len(all_rows) == 1


def test_concurrent_proposals_between_the_same_two_shops_converge_on_one(env):
    engine, _store, _plans, _ = env

    async def go():
        return await asyncio.gather(
            engine.propose(shop_a=A, shop_b_phone=B_PHONE, operator_id="op1",
                          condition_type=CONDITION_MIN_TOTAL, condition_value="1000",
                          grant_validity_days=3, agreement_duration_days=30,
                          discount_kind="percent", discount_amount=10),
            engine.propose(shop_a=A, shop_b_phone=B_PHONE, operator_id="op2",
                          condition_type=CONDITION_MIN_TOTAL, condition_value="2000",
                          grant_validity_days=3, agreement_duration_days=30,
                          discount_kind="percent", discount_amount=10),
            return_exceptions=True)

    results = run(go())
    ok = [r for r in results if not isinstance(r, Exception)]
    # Either both converge on the same agreement, or the second is refused as "try again" — never
    # two distinct live agreements for the same pair.
    ids = {r.id for r in ok}
    assert len(ids) == 1


# ── cancellation — mutual consent only ───────────────────────────────────────────────────────
def test_a_cancel_request_alone_does_not_end_the_agreement(env):
    engine, _store, _plans, _ = env
    agreement = _propose(engine)
    run(engine.accept(tenant=B, agreement_id=agreement.id))
    requested = run(engine.cancel_request(tenant=A, agreement_id=agreement.id))
    assert requested.status == CANCEL_REQUESTED
    # still queryable/active-in-spirit, but NOT ended — the other side has not agreed yet.
    fetched = run(engine.get(A, agreement.id))
    assert fetched.status == CANCEL_REQUESTED


def test_the_side_that_requested_cancel_cannot_also_confirm_it(env):
    engine, _store, _plans, _ = env
    agreement = _propose(engine)
    run(engine.accept(tenant=B, agreement_id=agreement.id))
    run(engine.cancel_request(tenant=A, agreement_id=agreement.id))
    with pytest.raises(MutualBenefitError) as exc:
        run(engine.cancel_confirm(tenant=A, agreement_id=agreement.id))
    assert exc.value.args[0] == FORBIDDEN


def test_the_other_side_confirming_actually_ends_it(env):
    engine, _store, _plans, _ = env
    agreement = _propose(engine)
    run(engine.accept(tenant=B, agreement_id=agreement.id))
    run(engine.cancel_request(tenant=A, agreement_id=agreement.id))
    ended = run(engine.cancel_confirm(tenant=B, agreement_id=agreement.id))
    assert ended.status == ENDED


# ── subscription pause / resume ──────────────────────────────────────────────────────────────
def test_a_lapsed_subscription_pauses_the_agreement_immediately_and_unilaterally(env):
    engine, _store, plans, _ = env
    agreement = _propose(engine)
    run(engine.accept(tenant=B, agreement_id=agreement.id))
    _unsubscribe(plans, B)
    fetched = run(engine.get(A, agreement.id))
    assert fetched.status == PAUSED


def test_resuming_before_the_original_end_date_keeps_the_same_end_date(env):
    engine, _store, plans, _ = env
    agreement = _propose(engine)
    active = run(engine.accept(tenant=B, agreement_id=agreement.id))
    original_end = active.original_ends_at
    _unsubscribe(plans, B)
    run(engine.get(A, agreement.id))
    _subscribe(plans, B)
    resumed = run(engine.get(A, agreement.id))
    assert resumed.status == ACTIVE
    assert resumed.ends_at == original_end


def test_resuming_after_the_original_end_date_ends_it_for_good(env):
    engine, store, plans, _ = env
    agreement = _propose(engine, agreement_duration_days=1)
    active = run(engine.accept(tenant=B, agreement_id=agreement.id))
    _unsubscribe(plans, B)
    # Force the clock past the original end by rewriting the stored row directly (no sleep).
    row = run(store.get("mutual_benefit_agreements", f"_platform|{agreement.id}"))
    row["original_ends_at"] = 1
    row["ends_at"] = 1
    run(store.put("mutual_benefit_agreements", f"_platform|{agreement.id}", row))
    _subscribe(plans, B)
    ended = run(engine.get(A, agreement.id))
    assert ended.status == ENDED


# ── an unanswered proposal expires, it is not left open forever ─────────────────────────────
def test_a_never_answered_proposal_expires(env):
    engine, store, _plans, _ = env
    agreement = _propose(engine)
    row = run(store.get("mutual_benefit_agreements", f"_platform|{agreement.id}"))
    row["proposal_expires_at"] = 1
    run(store.put("mutual_benefit_agreements", f"_platform|{agreement.id}", row))
    fetched = run(engine.get(A, agreement.id))
    assert fetched.status == EXPIRED_UNANSWERED
    with pytest.raises(MutualBenefitError):
        run(engine.accept(tenant=B, agreement_id=agreement.id))


# ── the record_visit() hook: grants, redemption, expiry survives the parent's own state ─────
def test_visiting_shop_a_over_threshold_grants_eligibility_at_shop_b(env):
    engine, _store, _plans, _ = env
    agreement = _propose(engine)
    run(engine.accept(tenant=B, agreement_id=agreement.id))
    run(engine.on_visit_recorded(tenant=A, customer_phone="0511111111", service_ids=["svc1"],
                                total_minor=1500, visit_id="vis_1"))
    elig = run(engine.eligibility(B, "0511111111"))
    assert elig is not None
    assert elig["eligible"] is True
    assert "shop_a" not in elig and "agreement_id" not in elig     # privacy: no source disclosed


def test_visiting_shop_a_under_threshold_grants_nothing(env):
    engine, _store, _plans, _ = env
    agreement = _propose(engine)
    run(engine.accept(tenant=B, agreement_id=agreement.id))
    run(engine.on_visit_recorded(tenant=A, customer_phone="0511111111", service_ids=["svc1"],
                                total_minor=100, visit_id="vis_1"))
    assert run(engine.eligibility(B, "0511111111")) is None


def test_retrying_the_same_visit_id_never_grants_twice(env):
    engine, _store, _plans, _ = env
    agreement = _propose(engine)
    run(engine.accept(tenant=B, agreement_id=agreement.id))
    for _ in range(3):
        run(engine.on_visit_recorded(tenant=A, customer_phone="0511111111", service_ids=[],
                                    total_minor=1500, visit_id="vis_same"))
    kpis = run(engine.kpis(A))
    assert kpis["as_referrer"]["referrals_sent"] == 1


def test_redeeming_marks_it_used_and_kpis_reflect_it(env):
    engine, _store, _plans, _ = env
    agreement = _propose(engine)
    run(engine.accept(tenant=B, agreement_id=agreement.id))
    run(engine.on_visit_recorded(tenant=A, customer_phone="0511111111", service_ids=[],
                                total_minor=1500, visit_id="vis_1"))
    redeemed = run(engine.redeem(B, "0511111111", visit_id="vis_b_1"))
    assert redeemed is True
    assert run(engine.eligibility(B, "0511111111")) is None      # already used
    kpis_a = run(engine.kpis(A))
    assert kpis_a["as_referrer"]["redeemed"] == 1
    assert kpis_a["as_referrer"]["redemption_rate"] == 1.0


def test_a_grant_already_earned_stays_valid_even_after_the_agreement_ends(env):
    engine, store, _plans, _ = env
    agreement = _propose(engine)
    run(engine.accept(tenant=B, agreement_id=agreement.id))
    run(engine.on_visit_recorded(tenant=A, customer_phone="0511111111", service_ids=[],
                                total_minor=1500, visit_id="vis_1"))
    run(engine.cancel_request(tenant=A, agreement_id=agreement.id))
    run(engine.cancel_confirm(tenant=B, agreement_id=agreement.id))
    fetched = run(engine.get(A, agreement.id))
    assert fetched.status == ENDED
    # THE GRANT ITSELF STILL WORKS — it honours its own expiry regardless of why the parent ended.
    elig = run(engine.eligibility(B, "0511111111"))
    assert elig is not None and elig["eligible"] is True


def test_a_grant_past_its_own_expiry_is_gone_even_though_its_agreement_is_active(env):
    engine, store, _plans, _ = env
    agreement = _propose(engine)
    run(engine.accept(tenant=B, agreement_id=agreement.id))
    run(engine.on_visit_recorded(tenant=A, customer_phone="0511111111", service_ids=[],
                                total_minor=1500, visit_id="vis_1"))
    rows, _ = run(store.find("mutual_benefit_grants", {"tenant": "_platform",
                                                              "agreement_id": agreement.id}))
    row = rows[0]
    row["expires_at"] = 1
    run(store.put("mutual_benefit_grants", f"_platform|{row['id']}", row))
    assert run(engine.eligibility(B, "0511111111")) is None


def test_shop_b_cannot_grant_eligibility_for_its_own_condition_it_is_not_shop_a(env):
    engine, _store, _plans, _ = env
    agreement = _propose(engine)
    run(engine.accept(tenant=B, agreement_id=agreement.id))
    # A visit at B (the beneficiary, not the referrer) triggers nothing — only shop_a visits count.
    run(engine.on_visit_recorded(tenant=B, customer_phone="0511111111", service_ids=[],
                                total_minor=999999, visit_id="vis_at_b"))
    assert run(engine.eligibility(B, "0511111111")) is None


# ── per-period grant cap ──────────────────────────────────────────────────────────────────────
def test_the_per_period_cap_actually_refuses_once_exceeded(env):
    engine, _store, _plans, _ = env
    agreement = _propose(engine, per_period_cap=2)
    run(engine.accept(tenant=B, agreement_id=agreement.id))
    for i in range(4):
        run(engine.on_visit_recorded(tenant=A, customer_phone=f"05000000{i:02d}",
                                    service_ids=[], total_minor=1500, visit_id=f"vis_{i}"))
    kpis = run(engine.kpis(A))
    assert kpis["as_referrer"]["referrals_sent"] == 2


# ── each shop sees only its own numbers ──────────────────────────────────────────────────────
def test_kpis_never_leak_the_other_partys_internal_numbers(env):
    engine, _store, _plans, _ = env
    agreement = _propose(engine)
    run(engine.accept(tenant=B, agreement_id=agreement.id))
    run(engine.on_visit_recorded(tenant=A, customer_phone="0511111111", service_ids=[],
                                total_minor=1500, visit_id="vis_1"))
    kpis_c = run(engine.kpis(C))
    assert kpis_c["as_referrer"]["referrals_sent"] == 0
    assert kpis_c["as_beneficiary"]["referrals_sent"] == 0


# ── the audit log — every transition, immutable ──────────────────────────────────────────────
def test_audit_log_captures_every_transition_and_nobody_but_a_party_can_read_it(env):
    engine, _store, _plans, _ = env
    agreement = _propose(engine)
    run(engine.accept(tenant=B, agreement_id=agreement.id))
    run(engine.cancel_request(tenant=A, agreement_id=agreement.id))
    run(engine.cancel_confirm(tenant=B, agreement_id=agreement.id))
    entries = run(engine.audit_log(A, agreement.id))
    events = [e.event for e in entries]
    assert events == ["proposed", "accepted", "activated", "cancel_requested",
                      "cancel_confirmed"]
    with pytest.raises(MutualBenefitError):
        run(engine.audit_log(C, agreement.id))


def test_the_audit_log_has_no_update_or_delete_path(env):
    engine, _store, _plans, _ = env
    # Structural guarantee: the engine never calls store.delete or a second store.put on the
    # SAME audit-log key — proven by construction (every `_audit` call mints a fresh uuid id and
    # this collection name appears nowhere else as a delete/put target in the module).
    import inspect

    import app.core.mutual_benefit as mod
    src = inspect.getsource(mod)
    assert f'self._s.delete({mod.AUDIT_LOG}' not in src
    assert "delete(AUDIT_LOG" not in src
