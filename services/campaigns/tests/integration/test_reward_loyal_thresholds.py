"""«كافئ المخلصين» — the owner's own audience thresholds (2026-09-13), live and per campaign
rather than a fixed 90-day/3-visit rule baked into the code. Proves the API layer actually applies
`loyalty_window_days`/`loyalty_min_visits` from the request, not `audience.resolve`'s own
pre-existing hardcoded defaults.
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
DAY = 86_400
NOW = int(dt.datetime.now(dt.timezone.utc).timestamp())


@pytest.fixture
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
    from app.adapters.peers import NullAudience, NullTemplates
    app.state.container.templates = NullTemplates([
        {"type": "mkt_loyalty_activation", "name": "mkt_loyalty_activation",
         "fills": ["system", "system", "system", "catalogue", "stop_link"],
         "variables": [1, 2, 3, 4, 5],
         "body": "بشارة {{1}}، جمّعت نقاط في {{2}}، وتقدر تستبدلها بـ{{4}}. {{5}}"},
    ])
    # THREE CUSTOMERS: one who qualifies under both the default (90d/3 visits) and a much
    # narrower rule (10d/5 visits), one who qualifies ONLY under the default, one who never
    # qualifies under any reasonable rule tested here.
    app.state.container.audience._c = NullAudience(rows=[
        {"subject_ref": "keeps_coming", "last_visit": NOW - 2 * DAY, "visit_count": 6},
        {"subject_ref": "occasional", "last_visit": NOW - 40 * DAY, "visit_count": 3},
        {"subject_ref": "long_gone", "last_visit": NOW - 200 * DAY, "visit_count": 1},
    ])
    yield app, TestClient(app, raise_server_exceptions=False)
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


def _auth(tenant="tnt_loyal"):
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "u1", "iss": ISS, "aud": AUD, "tenant": tenant,
                      "caps": ["campaigns.read", "campaigns.manage"],
                      "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


def _body(**over):
    body = {"goal": "reward_loyal", "owner_text": "", "package_id": "pkg1",
           "package_name": "باقة العناية", "expires_at": NOW + 7 * DAY}
    body.update(over)
    return body


def test_the_default_thresholds_match_two_of_the_three(client):
    app, http = client
    r = http.post("/api/v1/campaigns/preview", json=_body(), headers=_auth())
    assert r.status_code == 200, r.text
    assert r.json()["reaches"] == 2


def test_a_narrower_window_and_higher_visit_floor_matches_only_the_frequent_one(client):
    app, http = client
    r = http.post("/api/v1/campaigns/preview",
                  json=_body(loyalty_window_days=10, loyalty_min_visits=5), headers=_auth())
    assert r.status_code == 200, r.text
    assert r.json()["reaches"] == 1


def test_a_wide_enough_window_and_a_floor_of_one_visit_matches_all_three(client):
    app, http = client
    r = http.post("/api/v1/campaigns/preview",
                  json=_body(loyalty_window_days=365, loyalty_min_visits=1), headers=_auth())
    assert r.status_code == 200, r.text
    assert r.json()["reaches"] == 3


def test_an_out_of_range_window_is_refused_with_a_reason(client):
    app, http = client
    r = http.post("/api/v1/campaigns/preview",
                  json=_body(loyalty_window_days=400), headers=_auth())
    assert r.status_code == 422  # Pydantic's own `le=365` refuses it before this route even runs


def test_the_stored_thresholds_ride_the_campaign_row_for_the_send_to_re_read(client):
    """dispatch.py's own `_resolver` re-reads these from the STORED row on every pass — never
    trusted from whenever the preview ran (same discipline `package_id`'s own re-check follows)."""
    app, http = client
    r = http.post("/api/v1/campaigns",
                  json=_body(loyalty_window_days=10, loyalty_min_visits=5), headers=_auth())
    assert r.status_code in (200, 201), r.text
    cid = (r.json().get("campaign") or r.json()).get("id")

    listed = http.get("/api/v1/campaigns", headers=_auth())
    row = next(c for c in listed.json()["campaigns"] if c["id"] == cid)
    assert row["loyalty_window_days"] == 10
    assert row["loyalty_min_visits"] == 5


def test_a_campaign_that_never_set_them_stores_todays_defaults(client):
    app, http = client
    r = http.post("/api/v1/campaigns", json=_body(), headers=_auth())
    assert r.status_code in (200, 201), r.text
    cid = (r.json().get("campaign") or r.json()).get("id")

    listed = http.get("/api/v1/campaigns", headers=_auth())
    row = next(c for c in listed.json()["campaigns"] if c["id"] == cid)
    assert row["loyalty_window_days"] == 90
    assert row["loyalty_min_visits"] == 3
