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


# ── the manager threshold, and the three states it actually has ───────────────────────────────
def test_zero_removes_the_manager_requirement_instead_of_being_ignored(client, owner):
    """THE DEFECT. The write was guarded by `if body.manager_threshold:`, and the field defaulted
    to 0 — so «leave it» and «remove it» were the same value, and the truthiness test discarded
    exactly the one that mattered. An owner who set 500 and then decided his operators should
    redeem freely sent 0, got a 200, and read 500 back: the screen reported his change as accepted
    while every reward over 500 kept demanding an approval no till path could supply."""
    h = _auth("loyalty.manage")
    r = client.put("/api/v1/loyalty/settings/general",
                   json={"points": 10, "manager_threshold": 500}, headers=h)
    assert r.json()["general"]["manager_threshold"] == 500

    r = client.put("/api/v1/loyalty/settings/general",
                   json={"points": 10, "manager_threshold": 0}, headers=h)
    assert r.json()["general"]["manager_threshold"] == 0, r.text


def test_omitting_the_threshold_leaves_it_alone(client, owner):
    """AND THE OPPOSITE BUG IS NOT THE FIX. Writing it unconditionally would clear the threshold on
    every request that only changes the points rule — which is most of them."""
    h = _auth("loyalty.manage")
    client.put("/api/v1/loyalty/settings/general",
               json={"points": 10, "manager_threshold": 300}, headers=h)
    r = client.put("/api/v1/loyalty/settings/general", json={"points": 20}, headers=h)
    assert r.json()["general"]["manager_threshold"] == 300, r.text


# ── does this shop run a programme at all (هـ-1) ───────────────────────────────────────────────
def test_the_customer_page_read_says_whether_the_shop_runs_a_programme(client):
    """PORTAL CANNOT INFER IT, so this route has to state it.

    Every key in this answer has a value for a shop that runs nothing — zero points, no rewards,
    a threshold of zero — so the dictionary is never empty and portal's «if we got points back,
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


def test_invoice_mode_is_refused_for_a_shop_with_no_till_with_the_reason(client, owner):
    r = client.put("/api/v1/loyalty/settings/mode",
                   json={"mode": "invoice", "points_per_riyal": 1}, headers=owner)
    assert r.status_code == 400
    # ARABIC, and the reason NAMED — this reaches the owner's screen, and the platform is
    # Arabic-only today. An English sentence here is the same bug as no sentence.
    assert "الكاشير" in r.json()["reason"]


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
    r = client.post("/internal/loyalty/tick", json={"tenant": TENANT}, headers=INTERNAL)
    assert r.status_code == 200, r.text
    assert set(r.json()) >= {"expired", "warned_sent", "seen", "more"}


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
    # Tamam, 2026-08-19: a redemption is a receipt (reward, cost, branch, when) — deleting it on
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


# ── د-14 · the approval that could be demanded and never granted ───────────────────────────────


def test_the_till_can_grant_the_approval_the_shop_demands(client, owner):
    """THE DEFECT, END TO END. `/internal/loyalty/redeem` passed the approver on as
    `getattr(body, "approved_by", "")` and `TillRedeemIn` did not declare the field — so the default
    won every time, AND FastAPI dropped the key a till did send, because a schema that does not
    declare a field does not accept it. Every reward at or above the shop's threshold was refused at
    the one door where the manager is standing right there, and no request on earth could satisfy
    the refusal.

    Nothing failed on the way: `getattr` with a default cannot. The same field, spelled identically,
    sat on `EarnIn` two hundred lines up.
    """
    client.put("/api/v1/loyalty/settings/general",
               json={"points": 10, "manager_threshold": 100}, headers=owner)
    rid = _reward(client, owner, name="خصم كبير", cost=150, type="discount",
                  discount_halalas=20000)
    _earn(client, points=400, visit="v-appr", subject="ref_apprcust0001")

    # WITHOUT A NAME it is refused — the rule the owner set, working.
    bare = client.post("/internal/loyalty/redeem",
                       json={"tenant": TENANT, "subject_ref": "ref_apprcust0001",
                             "reward_id": rid, "idempotency_key": "inv-appr-1",
                             "actor": "cashier-1"}, headers=INTERNAL)
    assert "اعتماد المدير" in bare.text, bare.text

    # WITH ONE it goes through, and the ledger keeps who allowed it.
    ok = client.post("/internal/loyalty/redeem",
                     json={"tenant": TENANT, "subject_ref": "ref_apprcust0001",
                           "reward_id": rid, "idempotency_key": "inv-appr-2",
                           "actor": "cashier-1", "approved_by": "خالد المدير"},
                     headers=INTERNAL)
    assert ok.status_code == 200, ok.text
    assert ok.json()["discount_halalas"] == 20000


def test_the_menu_says_which_rewards_need_a_manager_before_the_tap(client, owner):
    """د-14أ — AFFORDABLE IS NOT THE SAME QUESTION AS ALLOWED. Both balance payloads listed every
    reward the points covered and said nothing about the threshold, so the counter offered a reward
    it could not deliver and found out at the tap, with the customer already holding out his hand.
    The flag is computed from the same `needs_approval` the refusal uses — written twice, the offer
    and the refusal drift apart on the first change."""
    client.put("/api/v1/loyalty/settings/general",
               json={"points": 10, "manager_threshold": 100}, headers=owner)
    big = _reward(client, owner, name="خصم كبير", cost=150, type="discount",
                  discount_halalas=20000)
    small = _reward(client, owner, name="خصم صغير", cost=20, type="discount",
                    discount_halalas=1000)
    _earn(client, points=400, visit="v-menu", subject="ref_menucust0001")

    for got in (client.get("/api/v1/loyalty/balance/ref_menucust0001", headers=owner).json(),
                client.get("/internal/loyalty/portal/balance",
                           params={"tenant": TENANT, "subject_ref": "ref_menucust0001"},
                           headers=INTERNAL).json()):
        assert got["manager_threshold"] == 100, got
        flags = {r["id"]: r["needs_approval"] for r in got["rewards"]}
        assert flags[big] is True, flags
        assert flags[small] is False, flags

    # AND THE OTHER HALF OF هـ-1, on the route that carries it: a shop that HAS rewards says so,
    # or the fix would have closed the customer's points card on everybody. Asserted on the key
    # itself and not through a default — an absent flag is the failure being tested for.
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
