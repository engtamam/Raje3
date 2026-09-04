"""The routes over §١٣'s ticket integration — ownership (only a shop that referred through THIS
marketer), and the shared TicketError -> HTTP status mapping.
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


class FakeTicketHttp:
    """Answers by URL prefix — same idiom as test_tickets.py's own fake."""

    def __init__(self, answers: dict[str, tuple[int, dict]]) -> None:
        self.answers = answers
        self.calls: list[str] = []

    def call(self, url, *, method, body=None, internal=False):
        self.calls.append(url)
        for prefix, answer in self.answers.items():
            if url.startswith(prefix):
                return answer
        return 500, {}


def _make_app(*, tickets_http=None) -> TestClient:
    """NOT env-leaking: every test using this restores os.environ itself via the `tickets_env`
    fixture below (same discipline as this service's other *_env fixtures) — a TICKET_SERVICE_URL
    left set past its own test would send every OTHER test's real Http at an unreachable host,
    turning a whole suite run into a chain of connect-timeouts."""
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
        "TICKET_SERVICE_URL": "http://tickets:8000" if tickets_http is not None else "",
    }
    os.environ.update(env)
    get_settings.cache_clear()
    from app.main import create_app

    app = create_app()
    if tickets_http is not None:
        app.state.container.tickets._http = tickets_http
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def tickets_env():
    from app.config import get_settings

    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


def _token(**over) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    # Every real affiliate token carries `affiliates.self` (2026-08-22) — see
    # app/core/models.py's own note. `**over` still lets a caller pass `caps=[...]` to test a
    # missing-capability 403 specifically.
    claims = {"sub": "nobody", "iss": ISS, "aud": AUD, "caps": ["affiliates.self"],
              "exp": now + dt.timedelta(minutes=5), "iat": now}
    claims.update(over)
    return jwt.encode(claims, SECRET, algorithm="HS256")


def _seed_referral(client: TestClient, *, affiliate_id: str, person_id: str, tenant: str) -> None:
    from app.core.models import ACTIVE, AFFILIATES, Affiliate

    async def seed():
        c = client.app.state.container
        aff = Affiliate(id=affiliate_id, person_id=person_id, phone=f"+96650{affiliate_id[-4:]}0001",
                        name="مسوّق", role="affiliate_manager", status=ACTIVE)
        await c.datastore.put(AFFILIATES, aff.id, aff.to_dict())
        await c.referrals.stamp(tenant=tenant, affiliate_id=affiliate_id)

    asyncio.run(seed())


def test_referred_shops_lists_what_the_caller_actually_referred():
    client = _make_app(tickets_http=FakeTicketHttp({}))
    _seed_referral(client, affiliate_id="aff-rs1", person_id="p-rs1", tenant="t-rs1")
    r = client.get("/api/v1/affiliates/me/referred-shops",
                   headers={"Authorization": f"Bearer {_token(sub='p-rs1')}"})
    assert r.status_code == 200, r.text
    shops = r.json()["shops"]
    assert len(shops) == 1
    assert shops[0]["tenant"] == "t-rs1"


def test_referred_shops_is_empty_for_a_marketer_who_referred_nobody():
    from app.core.models import ACTIVE, AFFILIATES, Affiliate

    client = _make_app(tickets_http=FakeTicketHttp({}))

    async def seed():
        aff = Affiliate(id="aff-rs2", person_id="p-rs2", phone="+966501230002",
                        name="مسوّق", role="affiliate_promoter", status=ACTIVE)
        await client.app.state.container.datastore.put(AFFILIATES, aff.id, aff.to_dict())

    asyncio.run(seed())
    r = client.get("/api/v1/affiliates/me/referred-shops",
                   headers={"Authorization": f"Bearer {_token(sub='p-rs2')}"})
    assert r.status_code == 200, r.text
    assert r.json() == {"shops": []}


def test_tickets_unavailable_with_no_ticket_service_configured():
    client = _make_app(tickets_http=None)
    _seed_referral(client, affiliate_id="aff-tk1", person_id="p-tk1", tenant="t-tk1")
    r = client.get("/api/v1/affiliates/me/shops/t-tk1/tickets",
                   headers={"Authorization": f"Bearer {_token(sub='p-tk1')}"})
    assert r.status_code == 503


def test_a_marketer_cannot_reach_a_shop_that_did_not_refer_through_him():
    client = _make_app(tickets_http=FakeTicketHttp({}))
    _seed_referral(client, affiliate_id="aff-tk2", person_id="p-tk2", tenant="t-tk2")
    r = client.get("/api/v1/affiliates/me/shops/some-other-tenant/tickets",
                   headers={"Authorization": f"Bearer {_token(sub='p-tk2')}"})
    assert r.status_code == 404


def test_list_tickets_for_his_own_referred_shop(monkeypatch):
    http = FakeTicketHttp({"http://tickets:8000/internal/tickets?": (200, {"tickets": [{"id": "tk-1"}]})})
    client = _make_app(tickets_http=http)
    _seed_referral(client, affiliate_id="aff-tk3", person_id="p-tk3", tenant="t-tk3")
    r = client.get("/api/v1/affiliates/me/shops/t-tk3/tickets",
                   headers={"Authorization": f"Bearer {_token(sub='p-tk3')}"})
    assert r.status_code == 200, r.text
    assert r.json() == {"tickets": [{"id": "tk-1"}]}
    assert any("grantee=aff-tk3" in u for u in http.calls)


def test_no_active_grant_is_a_clean_400_not_a_crash():
    http = FakeTicketHttp({"http://tickets:8000/internal/tickets?": (409, {})})
    client = _make_app(tickets_http=http)
    _seed_referral(client, affiliate_id="aff-tk4", person_id="p-tk4", tenant="t-tk4")
    r = client.get("/api/v1/affiliates/me/shops/t-tk4/tickets",
                   headers={"Authorization": f"Bearer {_token(sub='p-tk4')}"})
    assert r.status_code == 400
    assert r.json()["reason"] == "no_active_grant"


def test_reply_read_only_grant_is_a_clean_400():
    http = FakeTicketHttp({"http://tickets:8000/internal/tickets/tk-1/replies": (403, {})})
    client = _make_app(tickets_http=http)
    _seed_referral(client, affiliate_id="aff-tk5", person_id="p-tk5", tenant="t-tk5")
    r = client.post("/api/v1/affiliates/me/shops/t-tk5/tickets/tk-1/replies",
                    json={"body": "سنتابع فورًا"},
                    headers={"Authorization": f"Bearer {_token(sub='p-tk5')}"})
    assert r.status_code == 400
    assert r.json()["reason"] == "write_not_granted"


def test_reply_success_reaches_ticket_service_with_the_shops_tenant():
    http = FakeTicketHttp({"http://tickets:8000/internal/tickets/tk-1/replies":
                           (201, {"id": "tk-1", "status": "triaged"})})
    client = _make_app(tickets_http=http)
    _seed_referral(client, affiliate_id="aff-tk6", person_id="p-tk6", tenant="t-tk6")
    r = client.post("/api/v1/affiliates/me/shops/t-tk6/tickets/tk-1/replies",
                    json={"body": "سنتابع فورًا"},
                    headers={"Authorization": f"Bearer {_token(sub='p-tk6')}"})
    assert r.status_code == 201, r.text
    assert r.json()["id"] == "tk-1"


def test_reply_to_a_ticket_not_found_is_a_clean_404():
    http = FakeTicketHttp({"http://tickets:8000/internal/tickets/tk-1/replies": (404, {})})
    client = _make_app(tickets_http=http)
    _seed_referral(client, affiliate_id="aff-tk7", person_id="p-tk7", tenant="t-tk7")
    r = client.post("/api/v1/affiliates/me/shops/t-tk7/tickets/tk-1/replies",
                    json={"body": "سنتابع فورًا"},
                    headers={"Authorization": f"Bearer {_token(sub='p-tk7')}"})
    assert r.status_code == 404


# ── /me/home's own open_tickets carousel feed (2026-08-23) ─────────────────────────────────────

def test_home_open_tickets_carries_open_ones_only_with_the_shops_name_attached():
    http = FakeTicketHttp({
        "http://tickets:8000/internal/tickets?tenant=t-hm1": (200, {"tickets": [
            {"id": "tk-open", "subject": "الجهاز متوقف", "status": "open", "created_at": 200},
            {"id": "tk-closed", "subject": "قديمة", "status": "closed", "created_at": 100},
        ]}),
    })
    client = _make_app(tickets_http=http)
    _seed_referral(client, affiliate_id="aff-hm1", person_id="p-hm1", tenant="t-hm1")

    r = client.get("/api/v1/affiliates/me/home",
                   headers={"Authorization": f"Bearer {_token(sub='p-hm1')}"})
    assert r.status_code == 200, r.text
    tickets = r.json()["open_tickets"]
    assert [t["id"] for t in tickets] == ["tk-open"]   # the closed one is filtered out
    assert tickets[0]["tenant"] == "t-hm1"
    assert tickets[0]["shop_name"]   # falls back to the tenant id when unnamed — never blank


def test_home_open_tickets_skips_a_shop_with_no_active_grant_without_blanking_the_rest():
    http = FakeTicketHttp({
        "http://tickets:8000/internal/tickets?tenant=t-hm2a": (409, {}),
        "http://tickets:8000/internal/tickets?tenant=t-hm2b": (200, {"tickets": [
            {"id": "tk-ok", "status": "open", "created_at": 50},
        ]}),
    })
    client = _make_app(tickets_http=http)
    _seed_referral(client, affiliate_id="aff-hm2", person_id="p-hm2", tenant="t-hm2a")

    async def refer_second():
        await client.app.state.container.referrals.stamp(tenant="t-hm2b", affiliate_id="aff-hm2")
    asyncio.run(refer_second())

    r = client.get("/api/v1/affiliates/me/home",
                   headers={"Authorization": f"Bearer {_token(sub='p-hm2')}"})
    assert r.status_code == 200, r.text
    assert [t["id"] for t in r.json()["open_tickets"]] == ["tk-ok"]


def test_home_open_tickets_is_empty_with_no_ticket_service_configured():
    client = _make_app(tickets_http=None)
    _seed_referral(client, affiliate_id="aff-hm3", person_id="p-hm3", tenant="t-hm3")
    r = client.get("/api/v1/affiliates/me/home",
                   headers={"Authorization": f"Bearer {_token(sub='p-hm3')}"})
    assert r.status_code == 200, r.text
    assert r.json()["open_tickets"] == []


def test_an_operators_config_override_changes_the_withdrawal_threshold_live_on_home():
    """The end-to-end proof for the question: "400 ريال، وممكن يتغير — أتوقع
    فيه مكان لتعديلها" — an operator's PUT /api/v1/affiliates/operator/config takes effect on the NEXT
    /me/home read, no redeploy, exactly the surface `platform.config` already exists for."""
    client = _make_app(tickets_http=None)
    marketer_headers = {"Authorization": f"Bearer {_token(sub='p-cfg1')}"}
    from app.core.models import ACTIVE, AFFILIATES, Affiliate
    async def seed():
        aff = Affiliate(id="aff-cfg1", person_id="p-cfg1", phone="+966501230099",
                        name="مسوّق", role="affiliate_manager", status=ACTIVE)
        await client.app.state.container.datastore.put(AFFILIATES, aff.id, aff.to_dict())
    asyncio.run(seed())

    before = client.get("/api/v1/affiliates/me/home", headers=marketer_headers).json()
    assert before["min_withdrawal_halalas"] == 0   # this test env's own boot default

    operator_headers = {"Authorization": f"Bearer {_token(sub='op1', caps=['platform.config'])}"}
    put = client.put("/api/v1/affiliates/operator/config",
                     json={"key": "AFFILIATE_WITHDRAWAL_MIN_HALALAS", "value": 40000},
                     headers=operator_headers)
    assert put.status_code == 200, put.text

    after = client.get("/api/v1/affiliates/me/home", headers=marketer_headers).json()
    assert after["min_withdrawal_halalas"] == 40000
