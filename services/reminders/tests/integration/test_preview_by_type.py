"""GET /api/v1/reminders/templates/by-type/{template_type}/preview — the same wording engine as
`/reasons/{id}/preview`, reached by TEMPLATE TYPE for the five campaign goals with no
reasons-registry counterpart at all (announce, awareness, seasonal_care, service_offer,
package_offer — see Launch.tsx's own GOAL_REASON_ID and campaigns/app/core/models.py's
GOAL_TEMPLATE). Without this route those five goals had no preview/edit modal at all — only the
three that share a reason id ever got it.
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

    os.environ.update({
        "ENV": "test", "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256", "TOKEN_HS256_SECRET": SECRET,
        "TOKEN_ISSUER": ISS, "TOKEN_AUDIENCE": AUD, "RATELIMIT_MAX": "1000",
    })
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture(scope="module")
def env_guard():
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
    from app.config import get_settings
    get_settings.cache_clear()


@pytest.fixture(scope="module")
def client(env_guard) -> TestClient:
    c = _make_app()

    class Library:
        async def read(self):
            return {"ok": True, "templates": [
                {"name": "mkt_announcement_warm", "type": "mkt_announcement", "tone": "warm",
                 "active": True, "body": "خبر جديد من {{2}}: {{3}}. {{4}}",
                 "variables": [1, 2, 3, 4],
                 "fills": ["system", "system", "owner", "stop_link"]},
            ]}

    class ApprovedTemplates:
        async def names(self, tenant):
            return None

    class Identity:
        async def get(self, tenant):
            return None

    c.app.state.container.library = Library()
    c.app.state.container.approved_templates = ApprovedTemplates()
    c.app.state.container.identity = Identity()
    return c


def _auth() -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "u1", "iss": ISS, "aud": AUD, "tenant": "t1",
                      "caps": ["reminders.read"], "exp": now + dt.timedelta(minutes=5),
                      "iat": now}, SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


def test_a_goal_with_a_seeded_template_previews_by_type(client):
    r = client.get("/api/v1/reminders/templates/by-type/mkt_announcement/preview", headers=_auth())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["options"][0]["name"] == "mkt_announcement_warm"
    # NO REASON ROW ATTACHED — this route answers for a goal, not a reason.
    assert "reason" not in body
    assert body["chosen"] == ""
    assert body["empty_because"] == ""


def test_a_goal_with_no_seeded_template_degrades_gracefully(client):
    # `awr_seasonal_care` — the goal has NO template rows in the library at all yet
    # (deploy/seed/templates.json's own gap). This must never look like an error.
    r = client.get("/api/v1/reminders/templates/by-type/awr_seasonal_care/preview",
                   headers=_auth())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["options"] == []
    assert body["empty_because"] == "none"
