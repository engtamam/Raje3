"""/api/v1/assistant/operator/growth/upsell-report — real per-branch upsell offer/accept/decline
counts off `wa_upsell_ledger`, same harness shape as test_pricing_operator_api.py."""
from __future__ import annotations

import datetime as dt
import os
import time

import jwt
import pytest
from fastapi.testclient import TestClient

TOKEN_SECRET = "h" * 40
ISS, AUD = "iss", "aud"
KEK = "unit-test-kek-not-a-real-key"

PREFIX = "/api/v1/assistant/operator"


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
        "SECRETS_KEK": KEK,
        "PII_SALT": "s" * 32,
    }
    env.update(env_over)
    os.environ.update(env)
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


def _auth(*caps: str) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "op1", "iss": ISS, "aud": AUD, "caps": list(caps),
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


@pytest.fixture
def client(env_guard) -> TestClient:
    return _make_app()


@pytest.fixture
def operator_auth() -> dict:
    return _auth("platform.config")


@pytest.fixture
def reader_auth() -> dict:
    return _auth("reports.read")


def test_report_needs_the_capability(client, reader_auth):
    assert client.get(f"{PREFIX}/growth/upsell-report", headers=reader_auth).status_code == 403


def test_report_on_an_empty_ledger_is_honestly_zero(client, operator_auth):
    body = client.get(f"{PREFIX}/growth/upsell-report", headers=operator_auth).json()
    assert body["current"]["_all"] == {
        "branch_id": "_all", "offered": 0, "accepted": 0, "declined": 0, "pending": 0,
        "decided": 0, "acceptance_rate": None,
    }
    assert "scope_note" in body


async def _seed(store, *, proposal_id, tenant, branch_id, outcome, price_minor, proposed_at):
    from app.core.upsell_ledger import UPSELL_LEDGER
    await store.put(UPSELL_LEDGER, proposal_id, {
        "proposal_id": proposal_id, "tenant": tenant, "branch_id": branch_id,
        "subject_ref": "sub_x", "package_id": "pkg1", "price_minor": price_minor,
        "proposed_at": proposed_at, "outcome": outcome, "decided_at": proposed_at,
        "booking_id": "bkg_1" if outcome == "accepted" else ""})


def test_report_aggregates_real_ledger_rows_per_branch_and_computes_a_rate(client, operator_auth):
    container = client.app.state.container
    now = int(time.time())
    import asyncio
    asyncio.run(_seed(
        container.datastore, proposal_id="p1", tenant="t1", branch_id="brnA",
        outcome="accepted", price_minor=10000, proposed_at=now - 10))
    asyncio.run(_seed(
        container.datastore, proposal_id="p2", tenant="t1", branch_id="brnA",
        outcome="declined", price_minor=None, proposed_at=now - 5))
    asyncio.run(_seed(
        container.datastore, proposal_id="p3", tenant="t1", branch_id="brnB",
        outcome="pending", price_minor=None, proposed_at=now - 2))

    body = client.get(f"{PREFIX}/growth/upsell-report", headers=operator_auth).json()
    all_stats = body["current"]["_all"]
    assert all_stats["offered"] == 3
    assert all_stats["accepted"] == 1 and all_stats["declined"] == 1 and all_stats["pending"] == 1
    assert all_stats["acceptance_rate"] == 0.5   # 1 accepted / (1 accepted + 1 declined)

    a = body["current"]["brnA"]
    assert a["offered"] == 2 and a["accepted"] == 1 and a["declined"] == 1
    b = body["current"]["brnB"]
    assert b["offered"] == 1 and b["pending"] == 1 and b["acceptance_rate"] is None


def test_report_counts_an_accepted_row_regardless_of_whether_its_price_was_ever_known(
        client, operator_auth):
    """`price_minor` no longer feeds any average HERE (that honesty rule now lives in
    invoice_report.py's own average-invoice-value stat, over bookings-service's own rows) — this
    ledger's report only ever counts offer/accept/decline, so an unpriced accepted row still counts
    as accepted."""
    container = client.app.state.container
    now = int(time.time())
    import asyncio
    asyncio.run(_seed(
        container.datastore, proposal_id="p1", tenant="t1", branch_id="brnA",
        outcome="accepted", price_minor=None, proposed_at=now - 10))

    body = client.get(f"{PREFIX}/growth/upsell-report", headers=operator_auth).json()
    stats = body["current"]["_all"]
    assert stats["accepted"] == 1
    assert "accepted_with_unknown_price" not in stats
    assert "avg_ticket_increase_minor" not in stats
