"""ج-2 · the reserve the campaign must subtract, read as a number that was never a number.

`indicators.engine_reserve` answers a JUDGEMENT — `{"reserve", "basis", "weekday", "samples"}` —
and the snapshot stores that whole answer on purpose. The route that serves it to campaigns read it
with `int(...)`, which raises TypeError on a dict: the route 500s, campaigns swallows the failure
into a zero, and the reserve is never once subtracted.

So a campaign takes the shop's WHOLE allowance instead of its share. 250 where 210 was its, and the
40 it ate are the visit confirmations and service reminders the product exists to send. Nobody sees
an error: the campaign report is proud, and the reminders it displaced simply never went.
"""
from __future__ import annotations

import asyncio
import os

from fastapi.testclient import TestClient


def _client() -> TestClient:
    from app.config import get_settings

    os.environ.update({
        "ENV": "test", "INTERNAL_SERVICE_TOKEN": "t" * 40, "RATELIMIT_MAX": "5000",
        "SECRETS_KEK": "K" * 44, "PII_SALT": "s" * 32,
    })
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


def _snapshot(client: TestClient, tenant: str, value) -> None:
    from app.core.models import SNAPSHOTS

    asyncio.run(client.app.state.container.datastore.put(
        SNAPSHOTS, f"{tenant}|_all", {"tenant": tenant, "values": {"engine_reserve": value}}))


def _read(client: TestClient, tenant: str):
    return client.get(f"/internal/insights/engine-reserve?tenant={tenant}",
                      headers={"X-Internal-Token": "t" * 40})


def test_the_reserve_is_read_out_of_the_indicator_s_own_answer():
    client = _client()
    _snapshot(client, "t_res", {"reserve": 40, "basis": "p80", "weekday": 3, "samples": 8})

    r = _read(client, "t_res")

    assert r.status_code == 200, r.text
    assert r.json()["reserved"] == 40, "int({...}) raises, the route 500s, and campaigns reads 0"


def test_how_it_was_arrived_at_travels_with_it():
    """«floor» on a shop with no history is a different fact from a percentile of eight real
    weeks, and the caller that promises an owner his campaign reaches everyone should be able to
    say which it is standing on."""
    client = _client()
    _snapshot(client, "t_basis", {"reserve": 12, "basis": "floor", "weekday": 1, "samples": 0})

    assert _read(client, "t_basis").json()["basis"] == "floor"


def test_a_shop_with_no_snapshot_reserves_nothing():
    """The honest answer for a shop whose first sweep has not run: nothing is known about its
    traffic, so nothing is held back — and a new shop is not throttled by a number nobody has."""
    client = _client()

    r = _read(client, "t_new")

    assert r.status_code == 200 and r.json()["reserved"] == 0
