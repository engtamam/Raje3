"""operations-r2-005 (QA audit round 2, 2026-09-12): `branch_id` on WhatsApp connect/register used
to be taken from the caller and used as-is — every other branch-scoped write in this service
(staff.py's hire/update, via `branches.resolve_required`) validates it against the tenant's real
branches first. An unrecognised id here became half of the sending identity a credential is sealed
against (`tenant:branch_id`), inventing a branch that was never created.

Proved on the CANCEL path (no Meta exchange needed, so it needs no network double), which still
resolves and stores `branch_id` exactly like FINISH does.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

PATH = "/api/v1/whatsapp/connect"
SECRET = "h" * 40
ISS, AUD = "iss", "aud"
TENANT = "tnt_branch_check"


def _client():
    from app.config import get_settings

    os.environ.update({
        "ENV": "test",
        "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": SECRET,
        "TOKEN_ISSUER": ISS,
        "TOKEN_AUDIENCE": AUD,
        "RATELIMIT_MAX": "1000",
        "SIGNUP_REQUIRE_OTP": "false",
    })
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture()
def saved_env():
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
    from app.config import get_settings
    get_settings.cache_clear()


def _headers(tenant=TENANT):
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "u1", "iss": ISS, "aud": AUD, "caps": ["billing.self"],
                      "tenant": tenant, "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


def _add_real_branch(client, tenant: str, branch_id: str):
    """A real branch row, AND the shop moved to `per_branch` — `sending_identity.resolve` drops
    any branch at all for a `central` shop (the default), so a central-mode test could never tell
    "validated and kept" apart from "dropped because central"."""
    from app.core.models import Branch
    from app.core.shop_mode import MODES, PER_BRANCH
    from app.core.stores import BranchStore

    async def go():
        await BranchStore(client.app.state.container.datastore).save(
            Branch(id=branch_id, tenant=tenant, name="فرع حقيقي", created=1))
        await client.app.state.container.datastore.put(MODES, tenant, {"mode": PER_BRANCH})

    asyncio.run(go())


def test_an_unrecognised_branch_id_is_dropped_not_sealed(saved_env):
    """A CANCEL naming a branch this tenant never created must not have that id become part of a
    sealed sending identity. The shop is put in `per_branch` mode WITHOUT the named branch ever
    being created, so a drop here proves the validation fired — not just that a central shop
    drops every branch regardless."""
    client = _client()
    from app.core.shop_mode import MODES, PER_BRANCH
    asyncio.run(client.app.state.container.datastore.put(MODES, TENANT, {"mode": PER_BRANCH}))

    r = client.post(PATH, json={"event": "CANCEL", "step": "PERMISSIONS",
                                "branch_id": "brn-does-not-exist"},
                    headers=_headers())

    assert r.status_code == 200, r.text

    from app.core import connect as C

    async def read():
        return await C.ConnectionStore(client.app.state.container.datastore).get(TENANT, "")

    attempt = asyncio.run(read())
    assert attempt is not None
    # STORED UNDER THE EMPTY (establishment-wide) BRANCH, never under the bogus id — exactly as
    # `branches.resolve` drops any id this tenant does not actually have.
    assert attempt.branch_id == ""


def test_a_real_branch_id_still_resolves_normally(saved_env):
    """The fix must not cost a legitimate chain its per-branch connection."""
    client = _client()
    _add_real_branch(client, TENANT, "brn-jeddah")

    r = client.post(PATH, json={"event": "CANCEL", "step": "PERMISSIONS",
                                "branch_id": "brn-jeddah"},
                    headers=_headers())

    assert r.status_code == 200, r.text

    from app.core import connect as C

    async def read():
        return await C.ConnectionStore(client.app.state.container.datastore).get(
            TENANT, "brn-jeddah")

    attempt = asyncio.run(read())
    assert attempt is not None and attempt.branch_id == "brn-jeddah"
