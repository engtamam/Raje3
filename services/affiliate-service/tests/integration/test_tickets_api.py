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
    claims = {"sub": "nobody", "iss": ISS, "aud": AUD,
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
