"""Every core rule reached THROUGH ITS ROUTE, with the real request model in the way.

THIS FILE EXISTS BECAUSE OF §4.20. `fills` was enforced in operations' core and silently dropped by
its pydantic model, so the endpoint returned 200 having done nothing. Both layers read correctly in
isolation. The only thing that finds it is a test that goes through the door.
"""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

TOKEN_SECRET = "k" * 40
ISS, AUD, TENANT = "iss", "aud", "shop"
S = "ref_abcdef123456"


def _make_app() -> TestClient:
    from app.config import get_settings

    os.environ.update({
        "ENV": "test", "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256", "TOKEN_HS256_SECRET": TOKEN_SECRET,
        "TOKEN_ISSUER": ISS, "TOKEN_AUDIENCE": AUD, "RATELIMIT_MAX": "5000",
        "SECRETS_KEK": "K" * 44, "PII_SALT": "s" * 32,
    })
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


def _auth(*caps: str, tenant: str = TENANT) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "emp-7", "iss": ISS, "aud": AUD, "caps": list(caps),
                      "tenant": tenant, "exp": now + dt.timedelta(minutes=5), "iat": now},
                     TOKEN_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def env_guard():
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
    from app.config import get_settings
    get_settings.cache_clear()


@pytest.fixture(scope="module")
def client(env_guard) -> TestClient:
    return _make_app()


@pytest.fixture
def owner() -> dict:
    return _auth("loyalty.read", "loyalty.manage", "loyalty.redeem")


@pytest.fixture
def operator() -> dict:
    """Exactly what the field employee holds: read and redeem, never manage."""
    return _auth("loyalty.read", "loyalty.redeem")


INTERNAL = {"X-Internal-Token": "t" * 40}


def push_headers(body: bytes) -> dict[str, str]:
    """A genuine job-service push signature over `body`, verifiable against
    INTERNAL_SERVICE_TOKEN (the default `require_push_signature` falls back to) — needed on top
    of X-Internal-Token for /internal/loyalty/tick, recover and replay-free-visits since
    2026-09-16's push-dispatch migration."""
    import hashlib
    import hmac
    import time

    from app.core.push_verify import SIGNATURE_HEADER, TIMESTAMP_HEADER

    ts = int(time.time())
    signed = f"{ts}.".encode("utf-8") + body
    sig = hmac.new(("t" * 40).encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return {SIGNATURE_HEADER: sig, TIMESTAMP_HEADER: str(ts)}


def _reward(client, owner, name="قهوة", cost=50, type="item", **kw) -> str:
    r = client.post("/api/v1/loyalty/rewards",
                    json={"name": name, "cost": cost, "type": type, **kw}, headers=owner)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _earn(client, points=500, visit="v1", subject=S):
    client.put("/api/v1/loyalty/settings/general", json={"points": points},
               headers=_auth("loyalty.manage"))
    r = client.post("/internal/loyalty/earn",
                    json={"tenant": TENANT, "visit_id": visit, "subject_ref": subject,
                          "service_ids": ["wash"]}, headers=INTERNAL)
    assert r.status_code == 200, r.text
    return r.json()


# ── does this shop run a programme at all (هـ-1) ───────────────────────────────────────────────
def test_the_customer_page_read_says_whether_the_shop_runs_a_programme(client):
    """PORTAL CANNOT INFER IT, so this route has to state it.

    Every key in this answer has a value for a shop that runs nothing — zero points, no rewards —
    so the dictionary is never empty and portal's «if we got points back,
    show the card» could not be false. A customer of a shop with no loyalty read «0 نقطة» on his
    own page: a balance nobody can spend, under a heading for a programme that does not exist."""
    r = client.get("/internal/loyalty/portal/balance",
                   params={"tenant": "shop-with-no-rewards", "subject_ref": "ref_noprogram001"},
                   headers=INTERNAL)
    assert r.status_code == 200, r.text
    assert r.json()["has_programme"] is False
    # The rest of the answer is a full row of zeros, which is exactly why the flag is needed.
    assert r.json()["points"] == 0 and r.json()["rewards"] == []


# ── the field screen ───────────────────────────────────────────────────────────────────────────
def test_a_customer_with_nothing_reads_as_zero_rather_than_404(client, operator):
    r = client.get("/api/v1/loyalty/balance/ref_nobody00000", headers=operator)
    assert r.status_code == 200
    assert r.json()["points"] == 0 and r.json()["rewards"] == []


def test_the_balance_shows_only_affordable_rewards(client, owner, operator):
    _reward(client, owner, name="قهوة", cost=50)
    _reward(client, owner, name="غسلة كاملة", cost=5000)
    _earn(client, points=100, visit="v-afford")
    got = client.get(f"/api/v1/loyalty/balance/{S}", headers=operator).json()
    assert [r["name"] for r in got["rewards"]] == ["قهوة"]
    assert got["to_next_reward"] == 4900


def test_the_operator_can_redeem_and_the_manager_is_not_required(client, owner, operator):
    rid = _reward(client, owner, name="معطر", cost=30)
    _earn(client, points=100, visit="v-op")
    r = client.post("/api/v1/loyalty/redeem",
                    json={"subject_ref": S, "reward_id": rid, "idempotency_key": "k-op"},
                    headers=operator)
    assert r.status_code == 200, r.text
    assert r.json()["redemption"]["actor"] == "emp-7"


def test_the_same_key_twice_spends_once_through_the_route(client, owner, operator):
    rid = _reward(client, owner, name="شاي", cost=20)
    _earn(client, points=100, visit="v-idem")
    first = client.post("/api/v1/loyalty/redeem",
                        json={"subject_ref": S, "reward_id": rid, "idempotency_key": "k-twice"},
                        headers=operator).json()
    second = client.post("/api/v1/loyalty/redeem",
                         json={"subject_ref": S, "reward_id": rid, "idempotency_key": "k-twice"},
                         headers=operator).json()
    assert second["duplicate"] is True
    assert first["balance"] == second["balance"]


def test_an_overdraft_is_a_409_with_a_reason_the_operator_can_read(client, owner, operator):
    rid = _reward(client, owner, name="باقة", cost=9999)
    r = client.post("/api/v1/loyalty/redeem",
                    json={"subject_ref": "ref_broke00000000", "reward_id": rid,
                          "idempotency_key": "k-over"}, headers=operator)
    assert r.status_code == 409
    assert "9999" in r.text


def test_the_idempotency_key_is_required_by_the_model(client, operator):
    """Optional would mean the careful clients are safe and the hurried one is not."""
    r = client.post("/api/v1/loyalty/redeem",
                    json={"subject_ref": S, "reward_id": "rwd_x"}, headers=operator)
    assert r.status_code == 422


def test_an_operator_cannot_reprice_the_rewards_he_spends_against(client, operator):
    r = client.post("/api/v1/loyalty/rewards",
                    json={"name": "مجاني", "cost": 1, "type": "item"}, headers=operator)
    assert r.status_code == 403


# ── the rewards catalogue, through the door ────────────────────────────────────────────────────
def test_a_name_too_long_is_refused_by_the_model_before_the_core(client, owner):
    r = client.post("/api/v1/loyalty/rewards",
                    json={"name": "غ" * 60, "cost": 10, "type": "item"}, headers=owner)
    assert r.status_code == 422


def test_a_name_with_a_newline_is_refused_by_the_core_through_the_route(client, owner):
    """Length is the model's job; CONTENT is the core's — and the core must be reachable."""
    r = client.post("/api/v1/loyalty/rewards",
                    json={"name": "قهوة\nمجانية", "cost": 10, "type": "item"}, headers=owner)
    assert r.status_code == 400
    assert "واتساب" in r.text or "سطر" in r.text


def test_a_service_reward_without_its_service_is_refused_through_the_route(client, owner):
    r = client.post("/api/v1/loyalty/rewards",
                    json={"name": "غسلة", "cost": 200, "type": "service"}, headers=owner)
    assert r.status_code == 400


# ── the settings tree, through the door ────────────────────────────────────────────────────────
def test_the_tree_reports_where_every_number_came_from(client, owner):
    client.put("/api/v1/loyalty/settings/general", json={"points": 7}, headers=owner)
    client.put("/api/v1/loyalty/settings/service/oil", json={"points": 40}, headers=owner)
    got = client.get("/api/v1/loyalty/settings", headers=owner).json()
    assert got["general"]["points"] == 7
    assert got["services"]["oil"]["points"] == 40


def test_following_again_through_the_route_deletes_the_override(client, owner):
    client.put("/api/v1/loyalty/settings/general", json={"points": 7}, headers=owner)
    client.put("/api/v1/loyalty/settings/service/wax", json={"points": 40}, headers=owner)
    client.delete("/api/v1/loyalty/settings/service/wax", headers=owner)
    client.put("/api/v1/loyalty/settings/general", json={"points": 11}, headers=owner)
    got = client.get("/api/v1/loyalty/settings", headers=owner).json()
    assert "wax" not in got["services"]


def test_a_packages_own_points_through_the_route(client, owner):
    r = client.put("/api/v1/loyalty/settings/package/pkg1", json={"points": 60}, headers=owner)
    assert r.status_code == 200, r.text
    got = client.get("/api/v1/loyalty/settings", headers=owner).json()
    assert got["packages"]["pkg1"]["points"] == 60


def test_a_negative_package_points_value_is_refused_through_the_route(client, owner):
    r = client.put("/api/v1/loyalty/settings/package/pkg1", json={"points": -1}, headers=owner)
    assert r.status_code == 422


# ── the hypothetical read whatsapp-assistant's own growth tool builds on ───────────────────────
def test_earn_preview_is_a_real_read_never_a_spend(client, owner):
    client.put("/api/v1/loyalty/settings/general", json={"points": 5}, headers=owner)
    r = client.post("/internal/loyalty/earn-preview",
                    json={"tenant": TENANT, "service_ids": ["oil", "wax"]},
                    headers=INTERNAL)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["points_for_services"] > 0
    # A HYPOTHETICAL — the balance route must read exactly zero afterward, proving nothing spent.
    bal = client.get("/internal/loyalty/portal/balance",
                     params={"tenant": TENANT, "subject_ref": "ref_preview"},
                     headers=INTERNAL).json()
    assert bal["points"] == 0


def test_earn_preview_uses_the_packages_own_explicit_value_never_derived_from_price(client, owner):
    """The whole reason this route exists rather than a `points_per_riyal × price` guess —
    EarnTree.packages carries no such relationship on purpose (see that field's own docstring)."""
    client.put("/api/v1/loyalty/settings/package/pkg_deluxe", json={"points": 500}, headers=owner)
    r = client.post("/internal/loyalty/earn-preview",
                    json={"tenant": TENANT, "package_ids": ["pkg_deluxe", "pkg_unset"]},
                    headers=INTERNAL)
    assert r.status_code == 200, r.text
    assert r.json()["points_by_package"] == {"pkg_deluxe": 500, "pkg_unset": 0}


def test_earn_preview_needs_the_internal_token(client):
    r = client.post("/internal/loyalty/earn-preview",
                    json={"tenant": TENANT, "service_ids": ["oil"]})
    assert r.status_code in (401, 403)


def test_earn_preview_with_no_ids_at_all_answers_zeros_not_a_crash(client):
    r = client.post("/internal/loyalty/earn-preview", json={"tenant": TENANT}, headers=INTERNAL)
    assert r.status_code == 200
    assert r.json() == {"points_for_services": 0, "points_by_package": {}}


def test_earn_preview_is_isolated_per_tenant_never_reads_another_shops_earn_settings(client):
    """The SAME package id can exist at two different shops with two different owner-set point
    values — `tenant` is a plain body field here (this internal tier has no verified token to
    check it against, same as every other route in this file), and reading the wrong shop's
    `EarnTree` would hand whatsapp-assistant a real-looking number that belongs to somebody else's
    establishment entirely."""
    client.put("/api/v1/loyalty/settings/package/pkg_shared",
              json={"points": 111}, headers=_auth("loyalty.manage", tenant="tnt_earn_preview_a"))
    client.put("/api/v1/loyalty/settings/package/pkg_shared",
              json={"points": 222}, headers=_auth("loyalty.manage", tenant="tnt_earn_preview_b"))

    a = client.post("/internal/loyalty/earn-preview",
                    json={"tenant": "tnt_earn_preview_a", "package_ids": ["pkg_shared"]},
                    headers=INTERNAL).json()
    b = client.post("/internal/loyalty/earn-preview",
                    json={"tenant": "tnt_earn_preview_b", "package_ids": ["pkg_shared"]},
                    headers=INTERNAL).json()
    assert a["points_by_package"]["pkg_shared"] == 111
    assert b["points_by_package"]["pkg_shared"] == 222


def test_invoice_mode_is_allowed_by_default_no_till_needed(client, owner):
    """The default (null) peer answers `services_priced=True` — permissive, same posture every
    other Null* peer takes with nothing real wired. Retired 2026-09-08: this used to be refused
    for a shop with no till; operations now computes the invoice amount from priced services
    itself, so a till is no longer the requirement at all."""
    r = client.put("/api/v1/loyalty/settings/mode",
                   json={"mode": "invoice", "points_per_riyal": 1}, headers=owner)
    assert r.status_code == 200, r.text
    assert r.json()["config"]["mode"] == "invoice"


def test_invoice_mode_is_refused_when_a_service_is_not_priced(client, owner):
    class _Unpriced:
        async def __call__(self, tenant):
            return False

    client.app.state.container.services_pricing = _Unpriced()
    r = client.put("/api/v1/loyalty/settings/mode",
                   json={"mode": "invoice", "points_per_riyal": 1}, headers=owner)
    assert r.status_code == 400
    # ARABIC, and the reason NAMED — this reaches the owner's screen, and the platform is
    # Arabic-only today. An English sentence here is the same bug as no sentence.
    assert "مسعّرة" in r.json()["reason"]


def test_switching_back_to_services_mode_never_asks_operations(client, owner):
    """The pricing check costs a network call; a switch that does not need the answer must not
    pay for it."""
    class _Explodes:
        async def __call__(self, tenant):
            raise AssertionError("services_pricing must not be asked for a non-invoice switch")

    client.app.state.container.services_pricing = _Explodes()
    r = client.put("/api/v1/loyalty/settings/mode",
                   json={"mode": "services", "points_per_riyal": 1}, headers=owner)
    assert r.status_code == 200, r.text


# ── the till and the tick ──────────────────────────────────────────────────────────────────────
def test_the_till_redeems_and_returns_what_the_receipt_must_carry(client, owner):
    rid = _reward(client, owner, name="خصم", cost=40, type="discount", discount_halalas=5000)
    _earn(client, points=200, visit="v-till", subject="ref_tillcust0001")
    r = client.post("/internal/loyalty/redeem",
                    json={"tenant": TENANT, "subject_ref": "ref_tillcust0001",
                          "reward_id": rid, "idempotency_key": "inv-991",
                          "actor": "cashier-3"}, headers=INTERNAL)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["discount_halalas"] == 5000
    assert body["transaction_ref"].startswith("rdm_")
    # THE CONTRACT operations' visit-points and delivery-order callers read: without
    # `redemption.reward_type` they refused every discount after the points were already spent.
    assert body["redemption"]["reward_type"] == "discount"
    assert body["redemption"]["discount_halalas"] == 5000
    assert body["redemption"]["id"] == body["transaction_ref"]


def test_a_service_reward_redeemed_at_the_till_is_recorded_as_a_visit(client, owner):
    """THE DEFECT. The till route had copied the receipt out of `_after_redeem` and left the second
    seam behind: a `service` reward is also recorded as a VISIT, which is what restarts the reminder
    cycle. Without it the customer took his free wash at the counter and was reminded days later to
    come in for the wash he had just had — on the one counter where nobody from the shop is looking
    at our screen to catch it."""
    recorded = []

    class _Visits:
        async def record(self, **kw):
            recorded.append(kw)

    client.app.state.container.visits = _Visits()
    rid = _reward(client, owner, name="غسلة مجانية", cost=10, type="service",
                  service_id="svc_wash")
    _earn(client, points=200, visit="v-till-svc", subject="ref_tillsvc00001")
    r = client.post("/internal/loyalty/redeem",
                    json={"tenant": TENANT, "subject_ref": "ref_tillsvc00001",
                          "reward_id": rid, "idempotency_key": "inv-svc-1",
                          "actor": "cashier-9"}, headers=INTERNAL)
    assert r.status_code == 200, r.text
    assert len(recorded) == 1, recorded
    assert recorded[0]["service_id"] == "svc_wash"
    assert recorded[0]["subject_ref"] == "ref_tillsvc00001"
    assert recorded[0]["actor"] == "cashier-9"


def test_the_till_needs_the_internal_token(client):
    r = client.post("/internal/loyalty/redeem",
                    json={"tenant": TENANT, "subject_ref": S, "reward_id": "x",
                          "idempotency_key": "k"})
    assert r.status_code in (401, 403)


def test_the_tick_runs_and_reports_what_it_did(client):
    body = f'{{"tenant": "{TENANT}"}}'.encode()
    r = client.post("/internal/loyalty/tick", data=body,
                    headers={**INTERNAL, **push_headers(body), "Content-Type": "application/json"})
    assert r.status_code == 200, r.text
    assert set(r.json()) >= {"expired", "warned_sent", "seen", "more"}


def test_the_tick_refuses_without_a_push_signature_even_with_a_valid_internal_token(client):
    r = client.post("/internal/loyalty/tick", json={"tenant": TENANT}, headers=INTERNAL)
    assert r.status_code == 401


def test_reconcile_repairs_through_the_route(client, owner, operator):
    _earn(client, points=60, visit="v-recon", subject="ref_driftcust001")
    r = client.post("/internal/loyalty/reconcile",
                    json={"tenant": TENANT, "subject_ref": "ref_driftcust001",
                          # REQUIRED NOW (§8.3): a repair with no written reason is not performed.
                          "reason": "تحقّق من بلاغ «نقاطي اختفت»"},
                    headers=INTERNAL)
    assert r.status_code == 200
    assert r.json()["ledger"] == 60 and r.json()["repaired"] is False


# ── erasure ────────────────────────────────────────────────────────────────────────────────────
def test_erasure_removes_the_balance_and_is_idempotent(client, owner, operator):
    _earn(client, points=80, visit="v-erase", subject="ref_erasecust001")
    first = client.post("/internal/privacy/erase",
                        json={"tenant": TENANT, "subject": "ref_erasecust001"},
                        headers=INTERNAL)
    assert first.status_code == 200, first.text
    assert first.json()["erased"]
    assert client.get("/api/v1/loyalty/balance/ref_erasecust001",
                      headers=operator).json()["points"] == 0
    # A DSAR retries. Failing the second time would stall a fan-out designed to repeat.
    second = client.post("/internal/privacy/erase",
                         json={"tenant": TENANT, "subject": "ref_erasecust001"},
                         headers=INTERNAL)
    assert second.status_code == 200 and second.json()["already_absent"] is True


def test_erasure_keeps_the_redemption_receipt_pseudonymous_not_deleted(client, owner, operator):
    # A redemption is a receipt (reward, cost, branch, when) — deleting it on
    # an erasure request leaves the shop with no defence if the customer later disputes what he
    # was given, and breaks /report's own aggregate, which reads these rows directly.
    rid = _reward(client, owner, name="غسلة مجانية", cost=20)
    _earn(client, points=100, visit="v-receipt", subject="ref_erasereceipt001")
    client.post("/api/v1/loyalty/redeem",
               json={"subject_ref": "ref_erasereceipt001", "reward_id": rid,
                     "idempotency_key": "k-receipt"}, headers=operator)

    # THE SHARED TENANT ("shop") CARRIES OTHER TESTS' OWN REDEMPTIONS TOO — this asserts the
    # DELTA this one redemption made, not an absolute count.
    before = client.get("/api/v1/loyalty/report", headers=owner).json()
    before_count = before["redemptions"]
    before_reward = dict(before["top_rewards"]).get("غسلة مجانية", 0)

    r = client.post("/internal/privacy/erase",
                    json={"tenant": TENANT, "subject": "ref_erasereceipt001"}, headers=INTERNAL)
    assert r.status_code == 200, r.text
    assert any("redemptions" in x["what"] for x in r.json()["retained"])

    # THE RECEIPT SURVIVES — /report's aggregate is unchanged by the erasure, proving the row is
    # still there (not just claimed as "retained" in the ack while actually gone).
    after = client.get("/api/v1/loyalty/report", headers=owner).json()
    assert after["redemptions"] == before_count
    assert dict(after["top_rewards"]).get("غسلة مجانية", 0) == before_reward

    # AND THE CUSTOMER IS UNREACHABLE — his balance answers empty, the pseudonym no longer
    # resolves to him.
    assert client.get("/api/v1/loyalty/balance/ref_erasereceipt001",
                      headers=operator).json()["points"] == 0


# ── isolation ──────────────────────────────────────────────────────────────────────────────────
def test_another_establishment_sees_none_of_this(client, owner):
    _reward(client, owner, name="سرّي", cost=10)
    other = _auth("loyalty.read", "loyalty.manage", tenant="other-shop")
    assert client.get("/api/v1/loyalty/rewards", headers=other).json()["rewards"] == []


def test_earn_is_isolated_per_tenant_the_same_subject_ref_never_shares_a_balance(client):
    """`/internal/loyalty/earn` trusts `tenant` as a plain body field (see any internal.py's own
    header note — this tier has no verified token to check it against), and the SAME `subject_ref`
    can legitimately arrive for two different shops the same customer visits. His balance at one
    must never be nudged by an earn posted for the other."""
    client.put("/api/v1/loyalty/settings/general", json={"points": 20},
              headers=_auth("loyalty.manage", tenant="tnt_earn_iso_a"))
    client.put("/api/v1/loyalty/settings/general", json={"points": 20},
              headers=_auth("loyalty.manage", tenant="tnt_earn_iso_b"))
    same_ref = "ref_iso_shared01"
    client.post("/internal/loyalty/earn",
               json={"tenant": "tnt_earn_iso_a", "visit_id": "v-iso-a",
                     "subject_ref": same_ref, "service_ids": ["wash"]}, headers=INTERNAL)
    r = client.get(f"/api/v1/loyalty/balance/{same_ref}",
                   headers=_auth("loyalty.read", tenant="tnt_earn_iso_b"))
    assert r.status_code == 200
    assert r.json()["points"] == 0, "tenant A's earn must not appear on tenant B's balance"


def test_a_token_with_no_establishment_is_refused(client):
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "x", "iss": ISS, "aud": AUD, "caps": ["loyalty.read"],
                      "exp": now + dt.timedelta(minutes=5), "iat": now},
                     TOKEN_SECRET, algorithm="HS256")
    r = client.get(f"/api/v1/loyalty/balance/{S}",
                   headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 403


# ── which branch (spec §12.2: one balance, and still a place it happened) ──────────────────────
class _Scope:
    """Stands in for operations, the only service that knows who works where."""

    def __init__(self, answer: str) -> None:
        self.answer = answer

    async def scope(self, tenant: str, subject: str) -> str:
        return self.answer


def test_a_redemption_records_the_branch_the_PERSON_works_at(client, owner, operator, monkeypatch):
    """و-5 و و-9 معاً. The branch used to arrive in the body — and the field screen never sent one,
    so every redemption in a branched shop was filed under «غير محدَّد» while the till's were filed
    correctly. loyalty holds no staff list either, so whatever a caller DID send was written
    unchecked. It is now resolved from his own operator row, and a body value is ignored."""
    monkeypatch.setattr(client.app.state.container, "branch_scope",
                        _Scope("riyadh-north"), raising=False)
    rid = _reward(client, owner, name="بسكويت", cost=15)
    _earn(client, points=100, visit="v-branch", subject="ref_branchcust01")
    r = client.post("/api/v1/loyalty/redeem",
                    json={"subject_ref": "ref_branchcust01", "reward_id": rid,
                          "idempotency_key": "k-branch", "branch_id": "jeddah-FAKE"},
                    headers=operator)
    assert r.status_code == 200, r.text
    assert r.json()["redemption"]["branch_id"] == "riyadh-north", (
        "his row decides, not the body — which nothing here can check")
    # ON THE MOVEMENT TOO, because the ledger is the truth. A branch report built from receipts
    # alone would silently omit every earn and every expiry — neither of which has a receipt.
    hist = client.get("/api/v1/loyalty/history/ref_branchcust01", headers=operator).json()
    spend = next(e for e in hist["entries"] if e["reason"] == "redeem")
    assert spend["branch_id"] == "riyadh-north"


def test_a_supervisor_over_several_branches_redeems_without_crashing(
        client, owner, operator, monkeypatch):
    """loyalty-001/002 (QA audit, 2026-09-12): `BranchScope.scope()` returns a `frozenset` for a
    supervisor over more than one branch — the route used to pass that straight through into
    `Redemption.branch_id`, crashing on JSON serialization AFTER the ledger had already deducted
    the points, with no receipt ever written. Files as unscoped ("") instead — a real answer, not
    a crash — and, critically, the points are actually spent exactly once."""
    monkeypatch.setattr(client.app.state.container, "branch_scope",
                        _Scope(frozenset({"riyadh-north", "jeddah-south"})), raising=False)
    rid = _reward(client, owner, name="عصير", cost=10)
    _earn(client, points=100, visit="v-multibranch", subject="ref_multibranch01")
    r = client.post("/api/v1/loyalty/redeem",
                    json={"subject_ref": "ref_multibranch01", "reward_id": rid,
                          "idempotency_key": "k-multibranch"},
                    headers=operator)
    assert r.status_code == 200, r.text
    assert r.json()["redemption"]["branch_id"] == ""
    balance = client.get("/api/v1/loyalty/balance/ref_multibranch01", headers=operator).json()
    assert balance["points"] == 90


def test_an_unreadable_branch_refuses_the_spend_rather_than_filing_it_nowhere(
        client, owner, operator, monkeypatch):
    """«تعذّر أن نسأل» ليست «بلا فرع». A spend filed under «غير محدَّد» is invisible to the
    comparison an owner closes a place on."""
    from app.adapters.branch_scope import UNREADABLE

    monkeypatch.setattr(client.app.state.container, "branch_scope",
                        _Scope(UNREADABLE), raising=False)
    rid = _reward(client, owner, name="شاي", cost=5)
    _earn(client, points=50, visit="v-unread", subject="ref_unreadcust01")
    r = client.post("/api/v1/loyalty/redeem",
                    json={"subject_ref": "ref_unreadcust01", "reward_id": rid,
                          "idempotency_key": "k-unread"},
                    headers=operator)
    assert r.status_code == 503, r.text


def test_a_stopped_employee_cannot_spend_a_customers_points(client, owner, operator, monkeypatch):
    """His shop stopped him. That is a different fact from «we could not ask», and it refuses too."""
    from app.adapters.branch_scope import REVOKED

    monkeypatch.setattr(client.app.state.container, "branch_scope",
                        _Scope(REVOKED), raising=False)
    rid = _reward(client, owner, name="قهوة", cost=5)
    _earn(client, points=50, visit="v-revoked", subject="ref_revokedcus1")
    r = client.post("/api/v1/loyalty/redeem",
                    json={"subject_ref": "ref_revokedcus1", "reward_id": rid,
                          "idempotency_key": "k-revoked"},
                    headers=operator)
    assert r.status_code == 503, r.text


def test_adjust_is_refused_while_a_redemption_holds_the_same_subjects_lock(client, owner):
    """loyalty-005 (QA audit, 2026-09-12): adjust used to call Ledger.post with no lock at all,
    so it could race a redeem/earn's own locked read-modify-write for the same subject and
    silently lose one of the two writes. Proved by holding the SAME lane redeem()/earn() use,
    directly, and confirming adjust() is refused rather than allowed to interleave."""
    import asyncio

    from app.core.spend_lock import SpendLock

    subject = "ref_adjustlock01"
    _earn(client, points=50, visit="v-adjustlock", subject=subject)

    async def go():
        cache = client.app.state.container.cache
        async with SpendLock(cache, TENANT, subject):
            return client.post("/api/v1/loyalty/adjust",
                               json={"subject_ref": subject, "delta": 10,
                                     "note": "تعديل أثناء عملية أخرى",
                                     "idempotency_key": "adj-lock-race"},
                               headers=owner)

    r = asyncio.run(go())
    assert r.status_code == 409, r.text
    # AND THE BALANCE IS UNCHANGED — the refusal must not have partially applied anyway.
    balance = client.get(f"/api/v1/loyalty/balance/{subject}", headers=owner).json()
    assert balance["points"] == 50


def test_a_till_that_sends_no_branch_still_records_the_redemption(client, owner):
    """Optional, like everything else the till says about itself — never a reason to lose a sale."""
    rid = _reward(client, owner, name="علكة", cost=5)
    _earn(client, points=50, visit="v-nobranch", subject="ref_nobranchcus1")
    r = client.post("/internal/loyalty/redeem",
                    json={"tenant": TENANT, "subject_ref": "ref_nobranchcus1",
                          "reward_id": rid, "idempotency_key": "inv-nobranch"},
                    headers=INTERNAL)
    assert r.status_code == 200, r.text


def test_the_branch_a_visit_was_recorded_at_rides_onto_the_earn(client, owner):
    client.put("/api/v1/loyalty/settings/general", json={"points": 12},
               headers=_auth("loyalty.manage"))
    r = client.post("/internal/loyalty/earn",
                    json={"tenant": TENANT, "visit_id": "v-earnbranch",
                          "subject_ref": "ref_earnbranch01", "service_ids": ["wash"],
                          "actor": "emp-3", "branch_id": "jeddah-south"}, headers=INTERNAL)
    assert r.status_code == 200 and r.json()["earned"] == 12, r.text
    hist = client.get("/api/v1/loyalty/history/ref_earnbranch01",
                      headers=_auth("loyalty.read")).json()
    assert hist["entries"][0]["branch_id"] == "jeddah-south"
    # And the balance is still ONE across branches — that is the design, and this proves the
    # branch is a label on the movement rather than a partition of the account.
    assert client.get("/api/v1/loyalty/balance/ref_earnbranch01",
                      headers=_auth("loyalty.read")).json()["points"] == 12


def test_the_customer_page_says_it_has_a_programme_when_rewards_exist(client, owner):
    """AND THE OTHER HALF OF هـ-1, on the route that carries it: a shop that HAS rewards says so,
    or a bug closing this section would close the customer's points card on everybody. Asserted on
    the key itself and not through a default — an absent flag is the failure being tested for."""
    _reward(client, owner, name="خصم كبير", cost=150, type="discount", discount_halalas=20000)
    _earn(client, points=400, visit="v-menu", subject="ref_menucust0001")

    assert client.get("/internal/loyalty/portal/balance",
                      params={"tenant": TENANT, "subject_ref": "ref_menucust0001"},
                      headers=INTERNAL).json()["has_programme"] is True


def test_the_body_cannot_choose_which_branch_a_spend_is_filed_under():
    """و-5 · loyalty holds no staff list, so a branch on the request is a claim nothing can check.

    It is resolved from the operator's own row instead, and the field is GONE rather than accepted
    and ignored: a body field that is silently dropped is the shape that made the till and the
    screen disagree in the first place — one of them was sending something the server pretended to
    take.
    """
    from app.api.v1.loyalty import RedeemIn

    assert "branch_id" not in RedeemIn.model_fields
