"""GET /api/v1/reminders/reasons/{reason_id}/preview — a template carrying a real flow_button
(the rating app's own «قيّم زيارتك») now surfaces it as `buttons` on the option, matching what
Meta actually renders under the bubble (MessagePreview.tsx's own new button footer, console
side). Real data existed on the row already (operations' templates.seed.json); nothing before
this ever put it where the preview screen could see it.
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
                # THE RATING TEMPLATE — a real flow_button, same shape as
                # operations/data/templates.seed.json's own svc_visit_confirmation_rating row.
                {"name": "svc_visit_confirmation_rating_warm",
                 "type": "svc_visit_confirmation_rating", "tone": "warm", "active": True,
                 "body": "يا هلا {{1}}، نوّرتنا اليوم في {{2}}.",
                 "variables": [1, 2], "fills": ["system", "system"],
                 "button": "قيّم زيارتك", "flow_button": {"flow_name": "rating_flow"}},
                # AN ORDINARY TEMPLATE — no button at all, the vast majority.
                {"name": "svc_visit_confirmation_warm", "type": "svc_visit_confirmation",
                 "tone": "warm", "active": True, "body": "يا هلا {{1}}، نوّرتنا اليوم في {{2}}.",
                 "variables": [1, 2], "fills": ["system", "system"], "button": ""},
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


def test_a_flow_carrying_template_surfaces_its_button(client):
    r = client.get("/api/v1/reminders/reasons/rating_requested/preview", headers=_auth())
    assert r.status_code == 200, r.text
    options = r.json()["options"]
    row = next(o for o in options if o["name"] == "svc_visit_confirmation_rating_warm")
    assert row["buttons"] == [{"label": "قيّم زيارتك", "kind": "flow", "flow_name": "rating_flow"}]


def test_an_ordinary_template_carries_no_buttons_key_at_all(client):
    r = client.get("/api/v1/reminders/reasons/visit_recorded/preview", headers=_auth())
    assert r.status_code == 200, r.text
    options = r.json()["options"]
    row = next(o for o in options if o["name"] == "svc_visit_confirmation_warm")
    assert "buttons" not in row
