"""`/api/v1/field/customers/ensure` — resolve-or-create by phone, no visit attached.

bookings' console dialog needs a `customer_id` before it can create a booking
(docs/خطة-تنفيذ-الحجوزات.md §6.2). This proves it is the SAME resolve-or-create act
`record_visit` makes, not a second implementation.
"""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest

SECRET = "h" * 40
ISS, AUD = "iss", "aud"
PATH = "/api/v1/field/customers/ensure"


def _make_app(**env_over):
    from app.config import get_settings

    env = {
        "ENV": "test",
        "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": SECRET,
        "TOKEN_ISSUER": ISS,
        "TOKEN_AUDIENCE": AUD,
        "RATELIMIT_MAX": "1000",
        "PII_SALT": "s" * 32,
    }
    env.update(env_over)
    os.environ.update(env)
    get_settings.cache_clear()
    from app.main import create_app
    from fastapi.testclient import TestClient

    return TestClient(create_app(), raise_server_exceptions=False)


def _auth(tenant: str = "tnt_ensure") -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "op1", "tenant": tenant, "iss": ISS, "aud": AUD,
                      "caps": ["operations.record"],
                      "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture
def client(env_guard):
    return _make_app()


@pytest.fixture(scope="module")
def env_guard():
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
    from app.config import get_settings
    get_settings.cache_clear()


def test_ensuring_a_customer_indexes_him_for_search_too(client):
    # A customer created via the booking dialog (this route) could not be
    # FOUND by his own phone number until his first visit was confirmed — `index_customer_row`
    # used to run only from `after_visit`. This proves the ensure route is the second caller its
    # own docstring ("TWO CALLERS, ONE SHAPE") already anticipated.
    calls = []

    async def fake_index(**kwargs):
        calls.append(kwargs)

    client.app.state.container.seams.index_customer_row = fake_index
    r = client.post(PATH, json={"phone": "966500009999", "name": "خالد"}, headers=_auth())
    assert r.status_code == 200, r.text
    assert len(calls) == 1
    assert calls[0]["phone"] == "966500009999"
    assert calls[0]["name"] == "خالد"
    assert calls[0]["customer_id"] == r.json()["customer"]["id"]


def test_a_new_phone_creates_a_customer(client):
    r = client.post(PATH, json={"phone": "966500001111", "name": "سارة"}, headers=_auth())
    assert r.status_code == 200, r.text
    body = r.json()["customer"]
    assert body["phone"] == "966500001111"
    assert body["name"] == "سارة"
    assert body["subject_ref"]


def test_the_same_phone_twice_returns_the_same_customer(client):
    first = client.post(PATH, json={"phone": "966500002222"}, headers=_auth()).json()["customer"]
    second = client.post(PATH, json={"phone": "966500002222"}, headers=_auth()).json()["customer"]
    assert first["id"] == second["id"]


def test_a_later_name_fills_a_blank_but_never_overwrites(client):
    tenant_auth = _auth()
    client.post(PATH, json={"phone": "966500003333", "name": "محمد"}, headers=tenant_auth)
    second = client.post(PATH, json={"phone": "966500003333", "name": "آخر"},
                        headers=tenant_auth).json()["customer"]
    assert second["name"] == "محمد"


def test_an_empty_phone_is_refused(client):
    r = client.post(PATH, json={"phone": ""}, headers=_auth())
    assert r.status_code == 422   # Pydantic's own min_length=1 refuses before the handler runs


def test_a_phone_with_no_usable_digits_is_refused_by_the_handler(client):
    # RETURNED, NOT RAISED — same rule as `record_visit`'s own refusal: the platform strips
    # HTTPException detail on the way out, so this answers 200 with `customer: null` and the
    # actual reason, the same shape the console dialog checks explicitly for.
    r = client.post(PATH, json={"phone": "---"}, headers=_auth())
    assert r.status_code == 200
    body = r.json()
    assert body["customer"] is None
    assert body["reason"]
