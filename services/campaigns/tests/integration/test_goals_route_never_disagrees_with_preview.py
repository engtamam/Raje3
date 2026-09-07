"""A card `/goals` shows available must never be the one `/preview` then refuses.

THE BUG: an owner opened «رجّع اللي غابوا» (win_back), it looked pressable, and `/preview`
answered "لا يوجد قالب مفعّل لهذا الهدف — فعّله أولاً" the moment he asked for a number. The
route used to ask `enabled_types()` and `pick()` as two SEPARATE peer calls answering the same
underlying question — this fakes a peer where they disagree (the shape a cache race or a stale
read could produce) and proves the route no longer trusts the separate call at all.
"""
from __future__ import annotations

import datetime as dt
import os
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient

SECRET = "g" * 40
ISS, AUD, TENANT = "iss", "aud", "tnt_goals_race"


class _DivergingTemplates:
    """Claims `mkt_winback` is enabled (`enabled_types`) while `pick` — the fact `/preview`
    itself asks — says there is no row for it at all. The one shape that used to slip past
    `/goals` and only surface at `/preview`."""
    driver = "null"

    async def pick(self, tenant: str, template_type: str) -> dict[str, Any] | None:
        return None

    async def enabled_types(self, tenant: str) -> set[str]:
        return {"mkt_winback"}

    async def blocked_reasons(self, tenant: str) -> dict[str, str]:
        return {}


@pytest.fixture()
def client():
    from app.config import get_settings

    saved = dict(os.environ)
    os.environ.update({
        "ENV": "test", "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256", "TOKEN_HS256_SECRET": SECRET,
        "TOKEN_ISSUER": ISS, "TOKEN_AUDIENCE": AUD, "RATELIMIT_MAX": "1000",
    })
    get_settings.cache_clear()
    from app.main import create_app

    app = create_app()
    app.state.container.templates = _DivergingTemplates()
    yield TestClient(app, raise_server_exceptions=False)
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


def _auth(*caps: str) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "u1", "iss": ISS, "aud": AUD, "tenant": TENANT,
                      "caps": list(caps), "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


def test_the_card_is_locked_rather_than_trusting_a_stale_enabled_types(client):
    r = client.get("/api/v1/campaigns/goals", headers=_auth("campaigns.read"))
    assert r.status_code == 200, r.text
    card = next(g for g in r.json()["goals"] if g["goal"] == "win_back")
    assert card["available"] is False
    assert card["needs_enabling"] is True
    assert card["unavailable_reason"]


def test_preview_agrees_it_is_refused_for_the_same_underlying_reason(client):
    r = client.post("/api/v1/campaigns/preview",
                    json={"goal": "win_back"}, headers=_auth("campaigns.read"))
    assert r.status_code == 400
    assert "قالب" in r.json()["reason"]
