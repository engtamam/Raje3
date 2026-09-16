"""`POST /internal/loyalty/reverse-earn` — the HTTP door onto `Earner.reverse_earn`, at the
level of the actual route: the internal-token gate, and that it is never licence-blocked."""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

TENANT = "shop_reverse"
S = "ref_reverse_abcdef"
INTERNAL = {"X-Internal-Token": "t" * 40}


def _make_app() -> TestClient:
    from app.config import get_settings

    os.environ.update({"ENV": "test", "INTERNAL_SERVICE_TOKEN": "t" * 40,
                       "TOKEN_VERIFIER_DRIVER": "hs256", "TOKEN_HS256_SECRET": "h" * 40,
                       "TOKEN_ISSUER": "iss", "TOKEN_AUDIENCE": "aud",
                       "RATELIMIT_MAX": "1000", "PII_SALT": "s" * 32})
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture
def env_guard():
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
    from app.config import get_settings
    get_settings.cache_clear()


@pytest.fixture
def client(env_guard) -> TestClient:
    return _make_app()


def _earn(client, visit="v1", subject=S, points=200):
    client.put("/api/v1/loyalty/settings/general", json={"points": points},
              headers={"Authorization": _owner_token()})
    r = client.post("/internal/loyalty/earn",
                    json={"tenant": TENANT, "visit_id": visit, "subject_ref": subject,
                          "service_ids": ["wash"]}, headers=INTERNAL)
    assert r.status_code == 200, r.text
    return r.json()


def _owner_token() -> str:
    import datetime as dt

    import jwt

    now = dt.datetime.now(dt.timezone.utc)
    return "Bearer " + jwt.encode(
        {"sub": "owner1", "iss": "iss", "aud": "aud", "caps": ["loyalty.manage"],
         "tenant": TENANT, "exp": now + dt.timedelta(minutes=5), "iat": now},
        "h" * 40, algorithm="HS256")


def test_a_real_earn_is_reversed_over_the_wire(client):
    _earn(client)
    r = client.post("/internal/loyalty/reverse-earn",
                    json={"tenant": TENANT, "visit_id": "v1", "subject_ref": S},
                    headers=INTERNAL)
    assert r.status_code == 200, r.text
    assert r.json()["reversed"] == 200
    assert r.json()["balance"] == 0


def test_no_internal_token_is_refused(client):
    r = client.post("/internal/loyalty/reverse-earn",
                    json={"tenant": TENANT, "visit_id": "v1", "subject_ref": S})
    assert r.status_code in (401, 403)


def test_reversing_twice_over_the_wire_only_takes_back_once(client):
    _earn(client, visit="v2")
    first = client.post("/internal/loyalty/reverse-earn",
                        json={"tenant": TENANT, "visit_id": "v2", "subject_ref": S},
                        headers=INTERNAL)
    second = client.post("/internal/loyalty/reverse-earn",
                         json={"tenant": TENANT, "visit_id": "v2", "subject_ref": S},
                         headers=INTERNAL)
    assert first.json()["reversed"] == 200
    assert second.json().get("duplicate") is True


def test_a_visit_that_never_earned_reverses_nothing_but_still_answers_200(client):
    r = client.post("/internal/loyalty/reverse-earn",
                    json={"tenant": TENANT, "visit_id": "v-never", "subject_ref": S},
                    headers=INTERNAL)
    assert r.status_code == 200
    assert r.json()["reversed"] == 0
