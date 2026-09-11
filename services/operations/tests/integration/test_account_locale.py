"""«/account/me/locale» — the language preference moved off `Operator` (staff.py's own, now
superseded route) onto a platform-wide store, specifically so an OWNER account — which holds no
`Operator` row at all — can set one too. `require_user` only: no capability, no subscription, no
Operator row required.
"""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest

TOKEN_SECRET = "h" * 40
ISS, AUD = "iss", "aud"
KEK = "unit-test-kek-not-a-real-key"


def _make_app(**env_over):
    from app.config import get_settings
    from fastapi.testclient import TestClient

    env = {
        "ENV": "test",
        "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": TOKEN_SECRET,
        "TOKEN_ISSUER": ISS,
        "TOKEN_AUDIENCE": AUD,
        "RATELIMIT_MAX": "1000",
        "SECRETS_KEK": KEK,
        "PII_SALT": "s" * 32,
    }
    env.update(env_over)
    os.environ.update(env)
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


def _auth(subject: str = "owner1", *caps: str, tenant: str = "t1") -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": subject, "iss": ISS, "aud": AUD, "caps": list(caps),
                      "tenant": tenant,
                      "exp": now + dt.timedelta(minutes=5), "iat": now},
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
def client(env_guard):
    return _make_app()


def test_defaults_to_empty_for_an_account_with_no_preference_saved(client):
    r = client.get("/api/v1/account/me/locale", headers=_auth("owner_new"))
    assert r.status_code == 200
    assert r.json() == {"locale": ""}


def test_no_capability_or_operator_row_needed_at_all_owner_included(client):
    """The whole point: an OWNER — no operations.read, no bookings.*, no Operator row — can still
    set and read his own language, which staff.py's Operator-only route could never offer him."""
    r = client.patch("/api/v1/account/me/locale", headers=_auth("owner1"), json={"locale": "en"})
    assert r.status_code == 200
    assert r.json() == {"locale": "en"}

    r = client.get("/api/v1/account/me/locale", headers=_auth("owner1"))
    assert r.status_code == 200
    assert r.json() == {"locale": "en"}


def test_refuses_an_unknown_locale(client):
    # The platform's own error handler strips an HTTPException's detail (CWE-209) — same
    # "BAD_REQUEST" shape every other 400 in this service returns, `staff.py`'s identical
    # `UNKNOWN_LOCALE` raise included.
    r = client.patch("/api/v1/account/me/locale", headers=_auth("owner2"), json={"locale": "xx"})
    assert r.status_code == 400


def test_two_accounts_never_share_a_row(client):
    client.patch("/api/v1/account/me/locale", headers=_auth("acct_a"), json={"locale": "ur"})
    client.patch("/api/v1/account/me/locale", headers=_auth("acct_b"), json={"locale": "ha"})
    assert client.get("/api/v1/account/me/locale", headers=_auth("acct_a")).json() == {"locale": "ur"}
    assert client.get("/api/v1/account/me/locale", headers=_auth("acct_b")).json() == {"locale": "ha"}


def test_isolated_by_tenant_too(client):
    client.patch("/api/v1/account/me/locale", headers=_auth("acct_c", tenant="t1"), json={"locale": "fil"})
    r = client.get("/api/v1/account/me/locale", headers=_auth("acct_c", tenant="t2"))
    assert r.json() == {"locale": ""}


def test_carries_forward_an_already_saved_operator_locale_once(client):
    """An operator who picked a language under the OLD, Operator-only mechanism must not see it
    silently reset the day the platform-wide store takes over."""
    import asyncio
    from app.core.models import Operator
    from app.core.stores import OperatorStore

    asyncio.run(OperatorStore(client.app.state.container.datastore).save(Operator(
        id="opr_carry", tenant="t_carry", name="موظف", role="operator",
        branch_id="brn-1", person_id="op_carry", active=True, locale="ur")))

    r = client.get("/api/v1/account/me/locale", headers=_auth("op_carry", tenant="t_carry"))
    assert r.json() == {"locale": "ur"}
