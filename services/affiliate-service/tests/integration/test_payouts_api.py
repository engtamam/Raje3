"""The routes over the withdrawal itself — capability gating for the admin/finance side, and
the self-tier's own 404-when-not-an-affiliate discipline (test_onboarding_api.py's own pattern).
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


def _make_app() -> TestClient:
    from app.config import get_settings

    env = {
        "ENV": "test",
        "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": SECRET,
        "TOKEN_ISSUER": ISS,
        "TOKEN_AUDIENCE": AUD,
        "RATELIMIT_MAX": "1000",
        "PII_SALT": "s" * 16,
        "IDENTITY_SERVICE_URL": "http://identity:8000",
        "AFFILIATE_TENANT": "raje3-affiliates",
    }
    os.environ.update(env)
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture(scope="module")
def payouts_env():
    from app.config import get_settings

    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


@pytest.fixture(scope="module")
def client(payouts_env) -> TestClient:
    return _make_app()


def _token(caps=None, **over) -> str:
    # Default to the one capability every approved affiliate token holds
    # (`affiliates.self`, 2026-08-22) — a test wanting to prove a 403 from a MISSING
    # capability passes `caps=[]` explicitly; every ordinary self-service call gets
    # the real baseline instead of an empty list that never existed on a real token.
    now = dt.datetime.now(dt.timezone.utc)
    claims = {"sub": "nobody", "iss": ISS, "aud": AUD,
              "exp": now + dt.timedelta(minutes=5), "iat": now}
    claims["caps"] = list(caps) if caps is not None else ["affiliates.self"]
    claims.update(over)
    return jwt.encode(claims, SECRET, algorithm="HS256")


def test_set_payout_method_refuses_with_no_token(client):
    r = client.put("/api/v1/affiliates/me/payout-method",
                   json={"channel": "bank_iban", "account_ref": "SA00"})
    assert r.status_code == 401


def test_set_payout_method_404s_for_a_non_affiliate(client):
    r = client.put("/api/v1/affiliates/me/payout-method",
                   json={"channel": "bank_iban", "account_ref": "SA00"},
                   headers={"Authorization": f"Bearer {_token()}"})
    assert r.status_code == 404


def test_reading_the_payout_method_reports_unset_before_anything_is_saved(client):
    from app.core.models import ACTIVE, AFFILIATES, Affiliate

    async def seed():
        c = client.app.state.container
        aff = Affiliate(id="aff-pm1", person_id="p-pm1", phone="+966501300001",
                        name="مسوّق", role="affiliate_promoter", status=ACTIVE)
        await c.datastore.put(AFFILIATES, aff.id, aff.to_dict())

    asyncio.run(seed())
    r = client.get("/api/v1/affiliates/me/payout-method",
                   headers={"Authorization": f"Bearer {_token(sub='p-pm1')}"})
    assert r.status_code == 200, r.text
    assert r.json() == {"set": False}


def test_setting_then_reading_the_payout_method_returns_only_a_masked_ref(client):
    from app.core.models import ACTIVE, AFFILIATES, Affiliate

    async def seed():
        c = client.app.state.container
        aff = Affiliate(id="aff-pm2", person_id="p-pm2", phone="+966501300002",
                        name="مسوّق", role="affiliate_promoter", status=ACTIVE)
        await c.datastore.put(AFFILIATES, aff.id, aff.to_dict())

    asyncio.run(seed())
    headers = {"Authorization": f"Bearer {_token(sub='p-pm2')}"}
    put = client.put("/api/v1/affiliates/me/payout-method",
                     json={"channel": "bank_iban", "account_ref": "SA4420000001234567891234"},
                     headers=headers)
    assert put.status_code == 200, put.text

    got = client.get("/api/v1/affiliates/me/payout-method", headers=headers)
    assert got.status_code == 200, got.text
    assert got.json() == {"set": True, "channel": "bank_iban", "channel_name": "",
                          "masked_account_ref": "••••1234"}
    assert "SA4420000001234567891234" not in got.text


def test_balance_404s_for_a_non_affiliate(client):
    r = client.get("/api/v1/affiliates/me/balance",
                   headers={"Authorization": f"Bearer {_token()}"})
    assert r.status_code == 404


def test_request_withdrawal_404s_for_a_non_affiliate(client):
    r = client.post("/api/v1/affiliates/me/withdrawals",
                    headers={"Authorization": f"Bearer {_token()}"})
    assert r.status_code == 404


def test_admin_withdrawals_queue_refuses_without_the_finance_capability(client):
    r = client.get("/api/v1/admin/withdrawals",
                   headers={"Authorization": f"Bearer {_token(caps=[])}"})
    assert r.status_code == 403


def test_admin_withdrawals_queue_refuses_with_the_wrong_affiliates_capability(client):
    # platform.affiliates (application review) must NOT double as platform.affiliates_payouts
    # (settling money) — the whole point of splitting them.
    r = client.get("/api/v1/admin/withdrawals",
                   headers={"Authorization": f"Bearer {_token(caps=['platform.affiliates'])}"})
    assert r.status_code == 403


def test_admin_withdrawals_queue_works_with_the_finance_capability(client):
    r = client.get("/api/v1/admin/withdrawals",
                   headers={"Authorization": f"Bearer {_token(caps=['platform.affiliates_payouts'])}"})
    assert r.status_code == 200, r.text
    assert r.json() == {"withdrawals": []}


def test_complete_refuses_without_the_finance_capability(client):
    r = client.post("/api/v1/admin/withdrawals/does-not-exist/complete",
                    json={"receipt_reference": "r"},
                    headers={"Authorization": f"Bearer {_token(caps=[])}"})
    assert r.status_code == 403


def test_completing_an_unknown_withdrawal_is_a_clean_400(client):
    r = client.post("/api/v1/admin/withdrawals/does-not-exist/complete",
                    json={"receipt_reference": "r"},
                    headers={"Authorization": f"Bearer {_token(caps=['platform.affiliates_payouts'])}"})
    assert r.status_code == 400
    assert r.json()["reason"] == "not_found"


def test_reject_refuses_without_the_finance_capability(client):
    r = client.post("/api/v1/admin/withdrawals/does-not-exist/reject", json={},
                    headers={"Authorization": f"Bearer {_token(caps=[])}"})
    assert r.status_code == 403


# ── the receipt itself: upload, and the two ways to download it ─────────────────────────────────
import asyncio

from app.core.models import ACTIVE, AFFILIATES, COMMISSIONS, CONFIRMED, CONVERSION, Affiliate, Commission

FINANCE = {"Authorization": f"Bearer {_token(caps=['platform.affiliates_payouts'])}"}


_seed_counter = [0]


def _seed_withdrawal(client: TestClient) -> tuple[str, str]:
    """Returns (affiliate_id, withdrawal_id) for a real, REQUESTED withdrawal — seeded directly
    through the container, same idiom as this platform's own test_internal_invoices.py-style
    fixtures: the onboarding chain needs a real identity backend this test app does not have.
    A FRESH affiliate id per call — the client fixture (and its container/store) is shared
    across this whole module, so reusing one id would find an already-open request from an
    earlier test and refuse with already_pending."""
    _seed_counter[0] += 1
    n = _seed_counter[0]
    async def seed():
        c = client.app.state.container
        aff = Affiliate(id=f"aff-r{n}", person_id=f"p-r{n}", phone=f"+96650111{n:04d}",
                        name="مسوّق", role="affiliate_manager", status=ACTIVE)
        await c.datastore.put(AFFILIATES, aff.id, aff.to_dict())
        commission = Commission(id=f"comm-r{n}", tenant=f"t-r{n}", affiliate_id=aff.id,
                                kind=CONVERSION, amount_halalas=4000, status=CONFIRMED)
        await c.datastore.put(COMMISSIONS, commission.id, commission.to_dict())
        await c.payouts.set_payout_method(aff.id, channel="bank_iban", account_ref="SA00")
        out = await c.payouts.request_withdrawal(aff.id)
        return aff.id, out["id"]
    return asyncio.run(seed())


def test_uploading_an_unsupported_file_type_is_refused(client):
    aff_id, wd_id = _seed_withdrawal(client)
    r = client.post(f"/api/v1/admin/withdrawals/{wd_id}/receipt", headers=FINANCE,
                    files={"file": ("r.txt", b"hello", "text/plain")})
    assert r.status_code == 400


def test_uploading_a_receipt_then_downloading_it_as_admin(client):
    aff_id, wd_id = _seed_withdrawal(client)
    up = client.post(f"/api/v1/admin/withdrawals/{wd_id}/receipt", headers=FINANCE,
                     files={"file": ("r.png", b"\x89PNG-fake-bytes", "image/png")})
    assert up.status_code == 200, up.text
    assert up.json()["receipt_reference"] == f"object:withdrawals/{wd_id}/receipt"

    down = client.get(f"/api/v1/admin/withdrawals/{wd_id}/receipt", headers=FINANCE)
    assert down.status_code == 200
    assert down.content == b"\x89PNG-fake-bytes"
    assert down.headers["content-type"] == "image/png"


def test_uploading_replaces_the_previous_receipt_not_accumulates(client):
    aff_id, wd_id = _seed_withdrawal(client)
    client.post(f"/api/v1/admin/withdrawals/{wd_id}/receipt", headers=FINANCE,
               files={"file": ("first.png", b"first", "image/png")})
    client.post(f"/api/v1/admin/withdrawals/{wd_id}/receipt", headers=FINANCE,
               files={"file": ("second.png", b"second", "image/png")})
    down = client.get(f"/api/v1/admin/withdrawals/{wd_id}/receipt", headers=FINANCE)
    assert down.content == b"second"


def test_the_marketer_can_download_his_own_uploaded_receipt(client):
    aff_id, wd_id = _seed_withdrawal(client)
    person_id = aff_id.replace("aff-r", "p-r")
    client.post(f"/api/v1/admin/withdrawals/{wd_id}/receipt", headers=FINANCE,
               files={"file": ("r.png", b"proof", "image/png")})
    down = client.get(f"/api/v1/affiliates/me/withdrawals/{wd_id}/receipt",
                      headers={"Authorization": f"Bearer {_token(sub=person_id)}"})
    assert down.status_code == 200
    assert down.content == b"proof"


def test_a_marketer_cannot_download_someone_elses_receipt(client):
    aff_id, wd_id = _seed_withdrawal(client)
    client.post(f"/api/v1/admin/withdrawals/{wd_id}/receipt", headers=FINANCE,
               files={"file": ("r.png", b"proof", "image/png")})
    down = client.get(f"/api/v1/affiliates/me/withdrawals/{wd_id}/receipt",
                      headers={"Authorization": f"Bearer {_token(sub='somebody-else')}"})
    assert down.status_code == 404


def test_downloading_with_no_receipt_at_all_is_a_clean_404(client):
    aff_id, wd_id = _seed_withdrawal(client)
    down = client.get(f"/api/v1/admin/withdrawals/{wd_id}/receipt", headers=FINANCE)
    assert down.status_code == 404


def test_a_pasted_url_receipt_cannot_be_streamed_back(client):
    aff_id, wd_id = _seed_withdrawal(client)
    client.post(f"/api/v1/admin/withdrawals/{wd_id}/complete", headers=FINANCE,
               json={"receipt_reference": "https://example.com/receipt.pdf"})
    down = client.get(f"/api/v1/admin/withdrawals/{wd_id}/receipt", headers=FINANCE)
    assert down.status_code == 409


def test_upload_refuses_without_the_finance_capability(client):
    aff_id, wd_id = _seed_withdrawal(client)
    r = client.post(f"/api/v1/admin/withdrawals/{wd_id}/receipt",
                    headers={"Authorization": f"Bearer {_token(caps=[])}"},
                    files={"file": ("r.png", b"x", "image/png")})
    assert r.status_code == 403
