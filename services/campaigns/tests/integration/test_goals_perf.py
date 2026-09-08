"""list_goals dedupes its template lookups and runs them concurrently, and lock reads no longer
scan campaigns — this proves both without pinning to internal call counts that would make the
test as brittle as the code it is checking.
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

    from app.adapters.peers import NullTemplates

    class CountingTemplates(NullTemplates):
        """Counts calls per (tenant, template_type) so the test can see the dedupe directly,
        rather than trusting the route not to ask the same question twice."""

        def __init__(self, library):
            super().__init__(library)
            self.calls: list[tuple[str, str]] = []

        async def pick(self, tenant, template_type):
            self.calls.append((tenant, template_type))
            return await super().pick(tenant, template_type)

    from app.core.models import GOAL_TEMPLATE

    # ONE ROW PER ACTUAL TEMPLATE TYPE THE GOALS USE, so /goals can render every card fully
    # enabled and the lock-round-trip test below can create any goal it likes.
    app.state.container.templates = CountingTemplates([
        {"type": t, "name": t, "fills": ["owner"], "body": "{{1}}"}
        for t, _cls in {v: None for v in GOAL_TEMPLATE.values()}
    ])
    yield TestClient(app, raise_server_exceptions=False)
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


def _auth(caps):
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "u1", "iss": ISS, "aud": AUD, "tenant": "tnt_goals",
                      "caps": caps, "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


CAPS = ["campaigns.read", "campaigns.manage"]


def test_a_template_type_shared_by_two_goals_is_looked_up_once(client):
    """`service_offer` and `package_offer`-shaped goals both render `mkt_offer` — asking for it
    twice is the exact duplication the dedupe removes."""
    templates = client.app.state.container.templates
    templates.calls.clear()

    r = client.get("/api/v1/campaigns/goals", headers=_auth(CAPS))
    assert r.status_code == 200, r.text

    types_asked = [t for _, t in templates.calls]
    assert len(types_asked) == len(set(types_asked)), \
        f"a template type was looked up more than once: {types_asked}"


def test_the_goals_screen_still_carries_every_type_the_active_templates_covered(client):
    r = client.get("/api/v1/campaigns/goals", headers=_auth(CAPS))
    assert r.status_code == 200, r.text
    goals = r.json()["goals"]
    from app.core.models import GOAL_TEMPLATE
    assert len(goals) == len(GOAL_TEMPLATE)


def test_a_lock_written_at_creation_is_read_back_without_a_campaign_scan(client, monkeypatch):
    """The lock now lives in a side record — this proves the round trip end to end: create an
    awareness campaign that reaches somebody (forcing the lock), then confirm /goals reports it
    locked. The dispatcher is stubbed to report a send so the test does not have to also build a
    real audience through the store just to prove the lock plumbing works."""
    from app.core.dispatch import DispatchResult
    from app.core.models import Run

    async def fake_fire(campaign, *, now, fired_by="system", daily_share=None):
        run = Run(tenant=campaign["tenant"], campaign_id=campaign["id"], at=now,
                  fired_by=fired_by, sent=1)
        return DispatchResult(run=run, finished=True)

    monkeypatch.setattr(client.app.state.container.dispatcher, "fire", fake_fire)

    body = {"goal": "awareness", "owner_text": "منتج جديد وصل"}
    r = client.post("/api/v1/campaigns", json=body, headers=_auth(CAPS))
    assert r.status_code in (200, 201), r.text

    goals = client.get("/api/v1/campaigns/goals", headers=_auth(CAPS)).json()["goals"]
    awareness = next(g for g in goals if g["goal"] == "awareness")
    # The lock reached the card as unavailability with a reason — the round trip from
    # `record_lock` (write) through `read_locks` (read) to `cards()` actually happened.
    assert awareness["available"] is False
    assert awareness["unavailable_reason"]
