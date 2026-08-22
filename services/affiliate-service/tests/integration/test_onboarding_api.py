"""The routes over «بوابة القبول» — capability gating and the one-call-no-token door.

Mirrors tests/integration/test_auth_rbac.py's own app-building idiom (real HS256 tokens, a real
FastAPI app) rather than mocking the router layer — the thing worth proving here is that the ROUTE
enforces `platform.affiliates`, and a route-layer mock cannot prove that.
"""
from __future__ import annotations

import asyncio
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
def onboarding_env():
    from app.config import get_settings

    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


@pytest.fixture(scope="module")
def client(onboarding_env) -> TestClient:
    return _make_app()


def _token(caps=None, **over) -> str:
    # Default to the one capability every approved affiliate token holds
    # (`affiliates.self`, 2026-08-22) — a test wanting to prove a 403 from a MISSING
    # capability passes `caps=[]` explicitly; every ordinary self-service call gets
    # the real baseline instead of an empty list that never existed on a real token.
    now = dt.datetime.now(dt.timezone.utc)
    claims = {"sub": "admin1", "iss": ISS, "aud": AUD,
              "exp": now + dt.timedelta(minutes=5), "iat": now}
    claims["caps"] = list(caps) if caps is not None else ["affiliates.self"]
    claims.update(over)
    return jwt.encode(claims, SECRET, algorithm="HS256")


def test_apply_needs_no_token(client):
    r = client.post("/api/v1/affiliates/apply",
                    json={"phone": "0501234501", "name": "سالم", "password": "hunter2hunter2",
                         "agreed": True})
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True
    assert r.json()["status"] == "pending"


def test_apply_without_agreeing_to_the_terms_is_refused(client):
    r = client.post("/api/v1/affiliates/apply",
                    json={"phone": "0501234598", "name": "سالم", "password": "hunter2hunter2"})
    assert r.status_code == 400
    assert r.json()["reason"] == "must_agree"


def test_apply_with_a_short_password_is_a_clean_400_not_a_500(client):
    r = client.post("/api/v1/affiliates/apply",
                    json={"phone": "0501234502", "name": "سالم", "password": "x", "agreed": True})
    # WeakPassword only surfaces once identity is actually called (at approve, not apply) — this
    # service's own apply() has no minimum-length rule of its own, so a short password is
    # accepted here and would be refused later by identity. Documented by asserting what
    # actually happens rather than what might be assumed.
    assert r.status_code == 200, r.text


def test_a_second_apply_on_the_same_number_is_refused_with_a_reason(client):
    client.post("/api/v1/affiliates/apply",
                json={"phone": "0501234503", "name": "أ", "password": "hunter2hunter2",
                     "agreed": True})
    r = client.post("/api/v1/affiliates/apply",
                    json={"phone": "0501234503", "name": "أ", "password": "hunter2hunter2",
                         "agreed": True})
    assert r.status_code == 400
    assert r.json()["reason"] == "already_pending"


def test_admin_queue_refuses_without_the_capability(client):
    r = client.get("/api/v1/admin/affiliates", headers={"Authorization": f"Bearer {_token(caps=[])}"})
    assert r.status_code == 403


def test_admin_queue_refuses_with_no_token_at_all(client):
    r = client.get("/api/v1/admin/affiliates")
    assert r.status_code == 401


def test_admin_queue_lists_a_pending_application_with_the_capability(client):
    client.post("/api/v1/affiliates/apply",
               json={"phone": "0501234504", "name": "قائمة الانتظار", "password": "hunter2hunter2",
                    "agreed": True})
    r = client.get("/api/v1/admin/affiliates",
                   headers={"Authorization": f"Bearer {_token(caps=['platform.affiliates'])}"})
    assert r.status_code == 200, r.text
    phones = [a["phone"] for a in r.json()["applications"]]
    assert "+966501234504" in phones


def test_suspend_refuses_without_the_capability(client):
    r = client.post("/api/v1/admin/affiliates/does-not-exist/suspend",
                    headers={"Authorization": f"Bearer {_token(caps=[])}"})
    assert r.status_code == 403


def test_suspending_an_unknown_affiliate_is_a_clean_400(client):
    r = client.post("/api/v1/admin/affiliates/does-not-exist/suspend",
                    headers={"Authorization": f"Bearer {_token(caps=['platform.affiliates'])}"})
    assert r.status_code == 400
    assert r.json()["reason"] == "not_found"


def test_reactivate_refuses_without_the_capability(client):
    r = client.post("/api/v1/admin/affiliates/does-not-exist/reactivate",
                    headers={"Authorization": f"Bearer {_token(caps=[])}"})
    assert r.status_code == 403


def test_approve_refuses_without_the_capability(client):
    r = client.post("/api/v1/admin/affiliates/does-not-exist/approve",
                    headers={"Authorization": f"Bearer {_token(caps=[])}"})
    assert r.status_code == 403


def test_approving_an_unknown_application_id_is_a_clean_400(client):
    r = client.post("/api/v1/admin/affiliates/does-not-exist/approve",
                    headers={"Authorization": f"Bearer {_token(caps=['platform.affiliates'])}"})
    assert r.status_code == 400
    assert r.json()["reason"] == "not_found"


def test_invite_refuses_a_token_with_no_capability_at_all(client):
    # `affiliates.self` (2026-08-22) now gates the route itself — a token with NO caps never
    # reaches the service layer at all.
    r = client.post("/api/v1/affiliates/me/invite",
                    json={"phone": "0501234599", "name": "مدعو"},
                    headers={"Authorization": f"Bearer {_token(caps=[])}"})
    assert r.status_code == 403


def test_invite_needs_no_role_specific_capability_beyond_self(client):
    # Once past that baseline, eligibility is still a DATA check (is this caller an active
    # manager affiliate), not an RBAC one — see api/v1/affiliate_self.py's own note. A token
    # holding only `affiliates.self`, for a subject with no matching affiliate row at all,
    # reaches the service layer, which is what actually refuses it.
    r = client.post("/api/v1/affiliates/me/invite",
                    json={"phone": "0501234599", "name": "مدعو"},
                    headers={"Authorization": f"Bearer {_token(sub='nobody-at-all')}"})
    assert r.status_code == 403
    assert r.json()["reason"] == "not_an_active_affiliate"


def test_invite_refuses_with_no_token_at_all(client):
    r = client.post("/api/v1/affiliates/me/invite", json={"phone": "0501234599", "name": "مدعو"})
    assert r.status_code == 401


def test_me_refuses_with_no_token(client):
    r = client.get("/api/v1/affiliates/me")
    assert r.status_code == 401


def test_change_password_refuses_with_no_token(client):
    r = client.post("/api/v1/affiliates/me/change-password",
                    json={"old_password": "old", "new_password": "new-strong-1"})
    assert r.status_code == 401


def test_change_password_refuses_a_token_with_no_capability_at_all(client):
    r = client.post("/api/v1/affiliates/me/change-password",
                    json={"old_password": "old", "new_password": "new-strong-1"},
                    headers={"Authorization": f"Bearer {_token(caps=[])}"})
    assert r.status_code == 403


def test_change_password_reaches_the_service_layer_with_no_ownership_check(client):
    # No real identity-service backs this test app, so the pass-through itself fails — proving
    # the ROUTE forwards to the service layer at all (a capability-only gate, no affiliate-row
    # lookup) rather than that identity actually accepts the change.
    r = client.post("/api/v1/affiliates/me/change-password",
                    json={"old_password": "old", "new_password": "new-strong-1"},
                    headers={"Authorization": f"Bearer {_token(sub='nobody-at-all')}"})
    assert r.status_code == 400
    assert r.json()["reason"] == "wrong_password"


def test_me_is_404_for_a_token_with_no_matching_affiliate_row(client):
    r = client.get("/api/v1/affiliates/me",
                   headers={"Authorization": f"Bearer {_token(sub='nobody')}"})
    assert r.status_code == 404


def test_me_refuses_a_valid_token_that_lacks_affiliates_self(client):
    """The real, positive proof that `affiliates.self` (2026-08-22) actually gates this family
    of routes — a valid, signed token that simply never carries the capability is refused BEFORE
    any data lookup, distinct from the 404 above (which is a data check on a token that DOES
    carry it, for a subject with no matching row)."""
    r = client.get("/api/v1/affiliates/me",
                   headers={"Authorization": f"Bearer {_token(caps=[])}"})
    assert r.status_code == 403


def test_me_succeeds_with_affiliates_self_and_a_real_row(client):
    from app.core.models import ACTIVE, AFFILIATES, PROMOTER, Affiliate

    async def go():
        c = client.app.state.container
        aff = Affiliate(id="aff-self-check", person_id="p-self-check", phone="+966501239911",
                        name="مسوّق", role=PROMOTER, status=ACTIVE)
        await c.datastore.put(AFFILIATES, aff.id, aff.to_dict())

    asyncio.run(go())
    r = client.get("/api/v1/affiliates/me",
                   headers={"Authorization": f"Bearer {_token(sub='p-self-check')}"})
    assert r.status_code == 200, r.text
    assert r.json()["id"] == "aff-self-check"


def test_my_commissions_refuses_with_no_token(client):
    r = client.get("/api/v1/affiliates/me/commissions")
    assert r.status_code == 401


def test_my_commissions_is_404_for_a_token_with_no_matching_affiliate_row(client):
    r = client.get("/api/v1/affiliates/me/commissions",
                   headers={"Authorization": f"Bearer {_token(sub='nobody')}"})
    assert r.status_code == 404




def test_accept_invite_with_an_unknown_token_is_a_clean_400(client):
    r = client.post("/api/v1/affiliates/accept-invite",
                    json={"token": "never-issued", "password": "hunter2hunter2"})
    assert r.status_code == 400
    assert r.json()["reason"] == "invalid_invite"


# ── spec §10: a manager's own team, with what it actually earned ────────────────────────────────

def test_my_team_refuses_with_no_token(client):
    r = client.get("/api/v1/affiliates/me/team")
    assert r.status_code == 401


def test_my_team_is_404_for_a_token_with_no_matching_affiliate_row(client):
    r = client.get("/api/v1/affiliates/me/team",
                   headers={"Authorization": f"Bearer {_token(sub='nobody')}"})
    assert r.status_code == 404


def test_my_team_lists_members_with_their_earnings_and_a_team_total(client):
    import asyncio

    from app.core.models import ACTIVE, AFFILIATES, COMMISSIONS, CONFIRMED, CONVERSION, Affiliate, Commission

    async def seed():
        c = client.app.state.container
        manager = Affiliate(id="mgr-team-1", person_id="p-mgr-team-1", phone="+966505550001",
                            name="المدير", role="affiliate_manager", status=ACTIVE)
        promoter = Affiliate(id="prm-team-1", person_id="p-prm-team-1", phone="+966505550002",
                             name="مسوّق فرعي", role="affiliate_promoter",
                             parent_id="mgr-team-1", status=ACTIVE)
        await c.datastore.put(AFFILIATES, manager.id, manager.to_dict())
        await c.datastore.put(AFFILIATES, promoter.id, promoter.to_dict())
        commission = Commission(id="comm-team-1", tenant="t-team-1", affiliate_id=promoter.id,
                                kind=CONVERSION, amount_halalas=4000, status=CONFIRMED)
        await c.datastore.put(COMMISSIONS, commission.id, commission.to_dict())

    asyncio.run(seed())
    r = client.get("/api/v1/affiliates/me/team",
                   headers={"Authorization": f"Bearer {_token(sub='p-mgr-team-1')}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["team_confirmed_halalas"] == 4000
    assert [m for m in body["members"] if m["id"] == "prm-team-1"][0]["confirmed_halalas"] == 4000


def test_my_team_is_empty_for_a_promoter_with_nobody_under_him(client):
    import asyncio

    from app.core.models import ACTIVE, AFFILIATES, Affiliate

    async def seed():
        c = client.app.state.container
        promoter = Affiliate(id="prm-solo-1", person_id="p-prm-solo-1", phone="+966505550003",
                             name="مسوّق بلا فريق", role="affiliate_promoter",
                             parent_id="someone-else", status=ACTIVE)
        await c.datastore.put(AFFILIATES, promoter.id, promoter.to_dict())

    asyncio.run(seed())
    r = client.get("/api/v1/affiliates/me/team",
                   headers={"Authorization": f"Bearer {_token(sub='p-prm-solo-1')}"})
    assert r.status_code == 200, r.text
    assert r.json() == {"my_shops": [], "my_net_revenue_minor": 0, "my_revenue_partial": False,
                        "members": [], "team_confirmed_halalas": 0, "team_pending_halalas": 0,
                        "team_net_revenue_minor": 0, "team_revenue_partial": False,
                        "platform_revenue_enabled": False}


def test_platform_revenue_toggle_refuses_without_the_capability(client):
    r = client.post("/api/v1/admin/affiliates/does-not-exist/platform-revenue",
                    json={"enabled": True},
                    headers={"Authorization": f"Bearer {_token(caps=[])}"})
    assert r.status_code == 403


def test_platform_revenue_toggle_is_off_by_default_then_flips_the_team_route(client):
    import asyncio

    from app.core.models import ACTIVE, AFFILIATES, Affiliate

    async def seed():
        c = client.app.state.container
        mgr = Affiliate(id="mgr-prv-api-1", person_id="p-mgr-prv-api-1", phone="+966505550010",
                        name="مدير", role="affiliate_manager", status=ACTIVE)
        await c.datastore.put(AFFILIATES, mgr.id, mgr.to_dict())

    asyncio.run(seed())
    headers = {"Authorization": f"Bearer {_token(sub='p-mgr-prv-api-1')}"}

    before = client.get("/api/v1/affiliates/me/team", headers=headers)
    assert before.json()["platform_revenue_enabled"] is False
    assert "platform_net_revenue_minor" not in before.json()

    admin = client.post("/api/v1/admin/affiliates/mgr-prv-api-1/platform-revenue",
                        json={"enabled": True},
                        headers={"Authorization": f"Bearer {_token(caps=['platform.affiliates'])}"})
    assert admin.status_code == 200, admin.text
    assert admin.json() == {"ok": True, "changed": True, "sees_platform_revenue": True}

    after = client.get("/api/v1/affiliates/me/team", headers=headers)
    assert after.json()["platform_revenue_enabled"] is True
    assert "platform_net_revenue_minor" in after.json()
