"""The programme stops GROWING when the shop has not bought it — and never stops paying its debts.

THE DEFECT: `feature.loyalty` is on the price list and nothing in the fleet checked it. Every shop
on every plan earned points, edited rewards and changed the earning rules.

THE HALF THAT MUST NOT BE "FIXED": redeeming and reading. His customer opens his own page — which
is forbidden from consulting billing at all (§16.4.2) — and reads a balance. If the till then
refused to honour it, the customer would know something the shop cannot see, and the operator
would be arguing with a phone. A debt is paid whether or not the shop renewed this month.
"""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

SECRET = "h" * 40
ISS = "iss"
AUD = "aud"
INTERNAL = "t" * 40


def _make_app() -> TestClient:
    from app.config import get_settings

    os.environ.update({
        "ENV": "test",
        "INTERNAL_SERVICE_TOKEN": INTERNAL,
        "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": SECRET,
        "TOKEN_ISSUER": ISS,
        "TOKEN_AUDIENCE": AUD,
        "RATELIMIT_MAX": "1000",
    })
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture(scope="module")
def client():
    saved = dict(os.environ)
    app = _make_app()
    yield app
    os.environ.clear()
    os.environ.update(saved)
    from app.config import get_settings
    get_settings.cache_clear()


def _auth(caps, tenant="t1") -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "u1", "iss": ISS, "aud": AUD, "tenant": tenant, "caps": caps,
                      "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


class _Licence:
    def __init__(self, allowed):
        self._allowed = allowed
        self.asked = []

    async def allowed(self, tenant):
        self.asked.append(tenant)
        return self._allowed


@pytest.fixture
def unlicensed(client):
    container = client.app.state.container
    before = getattr(container, "licence", None)
    licence = _Licence(False)
    container.licence = licence
    yield licence
    container.licence = before


MANAGE = ["loyalty.manage", "loyalty.read", "loyalty.redeem"]


# ── the growing half: refused ──────────────────────────────────────────────────────────────────
def test_minting_points_by_hand_is_refused(client, unlicensed):
    from app.core.licence import NOT_INCLUDED

    r = client.post("/api/v1/loyalty/adjust",
                    json={"subject_ref": "sub_aaaaaaaa", "delta": 50, "note": "اعتذار للعميل",
                          "idempotency_key": "adj-1"},
                    headers=_auth(MANAGE))
    assert r.status_code == 402
    assert r.json().get("reason") == NOT_INCLUDED


def test_creating_a_reward_is_refused(client, unlicensed):
    r = client.post("/api/v1/loyalty/rewards",
                    json={"name": "غسيل مجاني", "cost": 40, "type": "service",
                          "service_id": "svc_1"},
                    headers=_auth(MANAGE))
    assert r.status_code == 402


def test_changing_the_earning_rule_is_refused(client, unlicensed):
    r = client.put("/api/v1/loyalty/settings/general", json={"points": 10},
                   headers=_auth(MANAGE))
    assert r.status_code == 402


def test_earning_on_a_visit_is_refused_and_says_so_without_erroring(client, unlicensed):
    """THE ONE NOBODY PRESSES: every recorded visit arrives here on the bus. It answers
    `earned: 0` with a reason rather than raising — the bus swallows exceptions and the catch-up
    would call it again for ever."""
    from app.core.licence import NOT_INCLUDED

    r = client.post("/internal/loyalty/earn",
                    json={"tenant": "t1", "visit_id": "v1", "subject_ref": "sub_aaaaaaaa",
                          "service_ids": ["svc_1"]},
                    headers={"X-Internal-Token": INTERNAL})
    assert r.status_code == 200
    assert r.json()["earned"] == 0
    assert r.json()["reason"] == NOT_INCLUDED


def test_the_check_asks_about_the_caller_s_own_establishment(client, unlicensed):
    client.put("/api/v1/loyalty/settings/general", json={"points": 10},
               headers=_auth(MANAGE, tenant="shop_9"))
    assert unlicensed.asked == ["shop_9"]


# ── the honouring half: never refused ──────────────────────────────────────────────────────────
def test_reading_a_balance_is_never_refused(client, unlicensed):
    """His own page is showing this number right now, and it may not consult billing at all."""
    r = client.get("/api/v1/loyalty/balance/sub_aaaaaaaa", headers=_auth(MANAGE))
    assert r.status_code == 200
    # AND THE LICENCE WAS NEVER ASKED — not "asked and allowed". A read that consults billing is a
    # read that fails when billing does.
    assert unlicensed.asked == []


def test_reading_the_rewards_table_is_never_refused(client, unlicensed):
    assert client.get("/api/v1/loyalty/rewards", headers=_auth(MANAGE)).status_code == 200
    assert unlicensed.asked == []


def test_redeeming_what_is_already_owed_is_never_refused(client, unlicensed):
    """A lapsed subscription must not strand points a customer already holds. The refusal here is
    about the reward being unaffordable or unknown — never about the shop's invoice."""
    r = client.post("/api/v1/loyalty/redeem",
                    json={"subject_ref": "sub_aaaaaaaa", "reward_id": "rwd_none"},
                    headers=_auth(MANAGE))
    assert r.status_code != 402
    assert unlicensed.asked == []


def test_history_is_never_refused(client, unlicensed):
    assert client.get("/api/v1/loyalty/history/sub_aaaaaaaa",
                      headers=_auth(MANAGE)).status_code == 200
    assert unlicensed.asked == []
