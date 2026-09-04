"""GET/PATCH /staff/operators/me[/locale] — an operator's own language preference for the
console's field screens. Self-service by design: found by WHO is asking (`sub` == a row's
`person_id`), never by an id in the path, so nobody can read or change another operator's
setting through this door.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

TOKEN_SECRET = "h" * 40
ISS, AUD = "iss", "aud"
TENANT = "tnt_locale"


def _make_app(**env_over) -> TestClient:
    from app.config import get_settings

    env = {
        "ENV": "test",
        "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": TOKEN_SECRET,
        "TOKEN_ISSUER": ISS,
        "TOKEN_AUDIENCE": AUD,
        "RATELIMIT_MAX": "1000",
        "PII_SALT": "s" * 32,
    }
    env.update(env_over)
    os.environ.update(env)
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


def _auth(subject: str, *caps: str, tenant: str = TENANT) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": subject, "iss": ISS, "aud": AUD, "caps": list(caps), "tenant": tenant,
                      "exp": now + dt.timedelta(minutes=5), "iat": now},
                     TOKEN_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


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


def _seed_operator(client, *, oid: str, person_id: str, locale: str = "") -> str:
    from app.core.models import Operator
    from app.core.stores import OperatorStore

    op = Operator(id=oid, tenant=TENANT, name="محمد", role="operator", person_id=person_id,
                 active=True, locale=locale)
    asyncio.run(OperatorStore(client.app.state.container.datastore).save(op))
    return op.id


# ── GET /operators/me ────────────────────────────────────────────────────────────────────────────
def test_an_operator_reads_his_own_row_by_identity_not_by_id_in_the_path(client):
    _seed_operator(client, oid="opr_1", person_id="person_abc", locale="ur")
    res = client.get("/api/v1/staff/operators/me", headers=_auth("person_abc", "bookings.write"))
    assert res.status_code == 200, res.text
    assert res.json()["locale"] == "ur"
    assert res.json()["id"] == "opr_1"


def test_the_owner_himself_has_no_operator_row_and_gets_a_real_404(client):
    # No Operator row seeded for this subject at all — an owner is not one.
    res = client.get("/api/v1/staff/operators/me", headers=_auth("owner_person", "bookings.write"))
    assert res.status_code == 404


def test_no_read_capability_at_all_is_refused(client):
    res = client.get("/api/v1/staff/operators/me", headers=_auth("person_abc"))
    assert res.status_code == 403


# ── PATCH /operators/me/locale ───────────────────────────────────────────────────────────────────
def test_an_operator_sets_his_own_language(client):
    _seed_operator(client, oid="opr_2", person_id="person_xyz")
    auth = _auth("person_xyz", "bookings.write")

    patched = client.patch("/api/v1/staff/operators/me/locale", json={"locale": "fil"}, headers=auth)
    assert patched.status_code == 200, patched.text
    assert patched.json()["locale"] == "fil"

    # PERSISTED, not just echoed — a fresh read agrees.
    again = client.get("/api/v1/staff/operators/me", headers=auth)
    assert again.json()["locale"] == "fil"


def test_an_unknown_locale_code_is_refused_not_silently_stored(client):
    _seed_operator(client, oid="opr_3", person_id="person_qrs")
    res = client.patch("/api/v1/staff/operators/me/locale", json={"locale": "xx"},
                       headers=_auth("person_qrs", "bookings.write"))
    assert res.status_code == 400


def test_one_operator_cannot_set_a_colleagues_language(client):
    """There is no id in this route at all — the ONLY row that can ever be touched is the
    caller's own, found by `sub`. Seeding a second operator and asserting the FIRST one's row
    is untouched is the real guarantee here, not a permission string."""
    _seed_operator(client, oid="opr_4", person_id="person_a", locale="ar")
    _seed_operator(client, oid="opr_5", person_id="person_b", locale="ar")

    client.patch("/api/v1/staff/operators/me/locale", json={"locale": "ha"},
                headers=_auth("person_b", "bookings.write"))

    untouched = client.get("/api/v1/staff/operators/me", headers=_auth("person_a", "bookings.write"))
    assert untouched.json()["locale"] == "ar"


def test_the_owner_himself_cannot_patch_a_locale_he_has_no_row_for(client):
    res = client.patch("/api/v1/staff/operators/me/locale", json={"locale": "en"},
                       headers=_auth("owner_person", "bookings.write"))
    assert res.status_code == 404
