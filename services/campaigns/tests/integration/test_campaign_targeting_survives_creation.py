"""What the owner targeted must still be true when the campaign actually fires.

THE DISPATCHER RE-RESOLVES THE AUDIENCE AT FIRE TIME from the STORED row (container.py
`_resolver`). So any targeting that lives only in the request is a preview that lies: the screen
shows a narrowed count, the run goes to everybody, and the report agrees with neither.

`service_id` was exactly that — accepted, previewed against, and never written. This proves both
it and `branch_id` survive creation.
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


@pytest.fixture(scope="module")
def client():
    from app.config import get_settings

    saved = dict(os.environ)
    os.environ.update({
        "ENV": "test",
        "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": SECRET,
        "TOKEN_ISSUER": ISS,
        "TOKEN_AUDIENCE": AUD,
        "RATELIMIT_MAX": "1000",
    })
    get_settings.cache_clear()
    from app.main import create_app

    app = create_app()
    # A LIBRARY WITH THE ONE TEMPLATE THIS GOAL NEEDS. Creation legitimately refuses a goal with
    # no enabled template, and a shop in this harness has none — so the refusal under test would
    # be the wrong one.
    from app.adapters.peers import NullTemplates
    app.state.container.templates = NullTemplates([
        {"type": "mkt_announcement", "name": "mkt_announcement", "fills": ["owner"],
         "body": "{{1}} — {{2}}"},
    ])
    yield TestClient(app, raise_server_exceptions=False)
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


def _auth(caps):
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "u1", "iss": ISS, "aud": AUD, "tenant": "tnt_branch",
                      "caps": caps, "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


# Both halves: creating needs `manage`, listing needs `read`, and one token carries both.
CAPS = ["campaigns.read", "campaigns.manage"]


def test_the_stored_campaign_remembers_its_service_and_its_branch(client):
    caps = CAPS
    body = {"goal": "announce", "owner_text": "افتتحنا فرع جدة",
            "service_id": "svc_oil", "branch_id": "brn-jed"}
    r = client.post("/api/v1/campaigns", json=body, headers=_auth(caps))
    assert r.status_code in (200, 201), r.text

    cid = (r.json().get("campaign") or r.json()).get("id")
    assert cid

    listed = client.get("/api/v1/campaigns", headers=_auth(caps))
    assert listed.status_code == 200, listed.text
    row = next(c for c in listed.json()["campaigns"] if c["id"] == cid)
    assert row["branch_id"] == "brn-jed"
    assert row["service_id"] == "svc_oil"
