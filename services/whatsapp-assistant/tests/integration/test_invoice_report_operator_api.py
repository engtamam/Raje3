"""/api/v1/assistant/operator/growth/invoice-report — average invoice value across every AI-made
booking (package or plain service), fed by a stubbed bookings-service peer + catalogue, same
harness shape as test_upsell_operator_api.py."""
from __future__ import annotations

import datetime as dt
import os
import time
from typing import Any

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
                      "tenant": "t1", "exp": now + dt.timedelta(minutes=5), "iat": now},
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


class _StubActorReport:
    """Records every call it gets (call-counting, not value-only) and answers with a fixed page of
    bookings — `bookings`/`calls` are read back by the tests below."""

    def __init__(self, bookings: list[dict[str, Any]], *, truncated: bool = False) -> None:
        self._bookings = bookings
        self._truncated = truncated
        self.calls: list[dict[str, Any]] = []

    async def by_actor(self, tenant, created_by, *, branch_id="", since=None, until=None):
        self.calls.append({"tenant": tenant, "created_by": created_by, "branch_id": branch_id,
                           "since": since, "until": until})
        rows = [b for b in self._bookings
               if (since is None or b["created"] >= since) and (until is None or b["created"] <= until)]
        return {"bookings": rows, "truncated": self._truncated}


class _StubCatalog:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    async def list_active(self, tenant):
        return self._rows


def _wire(client, *, bookings: list[dict], services: list[dict] | None = None,
         packages: list[dict] | None = None, truncated: bool = False) -> _StubActorReport:
    c = client.app.state.container
    stub = _StubActorReport(bookings, truncated=truncated)
    c.booking_actor_report = stub
    c.service_catalog = _StubCatalog(services or [])
    c.package_catalog = _StubCatalog(packages or [])
    return stub


def test_report_needs_the_capability(client, reader_auth):
    _wire(client, bookings=[])
    assert client.get(f"{PREFIX}/growth/invoice-report", headers=reader_auth).status_code == 403


def test_report_with_no_bookings_is_honestly_zero(client, operator_auth):
    _wire(client, bookings=[])
    body = client.get(f"{PREFIX}/growth/invoice-report", headers=operator_auth).json()
    assert body["current"]["_all"] == {
        "branch_id": "_all", "status_breakdown": {}, "attended_priced": 0,
        "attended_unpriced": 0, "avg_invoice_value_minor": None,
    }


def test_report_averages_only_attended_bookings_with_a_known_price(client, operator_auth):
    now = int(time.time())
    stub = _wire(client, bookings=[
        {"id": "b1", "branch_id": "brnA", "status": "attended", "service_ids": ["svc1"],
         "package_id": "", "price_override_minor": None, "created": now - 10},
        {"id": "b2", "branch_id": "brnA", "status": "booked", "service_ids": ["svc1"],
         "package_id": "", "price_override_minor": None, "created": now - 5},
        {"id": "b3", "branch_id": "brnA", "status": "no_show", "service_ids": ["svc1"],
         "package_id": "", "price_override_minor": None, "created": now - 3},
        {"id": "b4", "branch_id": "brnA", "status": "cancelled", "service_ids": ["svc1"],
         "package_id": "", "price_override_minor": None, "created": now - 2},
    ], services=[{"id": "svc1", "price_minor": 5000}])

    body = client.get(f"{PREFIX}/growth/invoice-report", headers=operator_auth).json()
    all_stats = body["current"]["_all"]
    # cancelled is dropped entirely — never counted anywhere, not even status_breakdown.
    assert all_stats["status_breakdown"] == {"attended": 1, "booked": 1, "no_show": 1}
    assert all_stats["attended_priced"] == 1
    assert all_stats["avg_invoice_value_minor"] == 5000

    # PROVES the peer was actually called with this actor's own constant, not a wildcard.
    assert stub.calls[0]["created_by"] == "whatsapp-assistant"
    assert stub.calls[0]["tenant"] == "t1"


def test_report_sums_multiple_services_for_a_plain_booking(client, operator_auth):
    now = int(time.time())
    _wire(client, bookings=[
        {"id": "b1", "branch_id": "brnA", "status": "attended",
         "service_ids": ["svc1", "svc2"], "package_id": "", "price_override_minor": None,
         "created": now - 10},
    ], services=[{"id": "svc1", "price_minor": 3000}, {"id": "svc2", "price_minor": 2000}])
    body = client.get(f"{PREFIX}/growth/invoice-report", headers=operator_auth).json()
    assert body["current"]["_all"]["avg_invoice_value_minor"] == 5000


def test_report_uses_the_packages_own_price_for_a_package_booking(client, operator_auth):
    now = int(time.time())
    _wire(client, bookings=[
        {"id": "b1", "branch_id": "brnA", "status": "attended", "service_ids": [],
         "package_id": "pkg1", "price_override_minor": None, "created": now - 10},
    ], packages=[{"id": "pkg1", "price_minor": 9000, "active": True}])
    body = client.get(f"{PREFIX}/growth/invoice-report", headers=operator_auth).json()
    assert body["current"]["_all"]["avg_invoice_value_minor"] == 9000


def test_report_prefers_the_explicit_price_override_over_the_catalogue(client, operator_auth):
    now = int(time.time())
    _wire(client, bookings=[
        {"id": "b1", "branch_id": "brnA", "status": "attended", "service_ids": ["svc1"],
         "package_id": "", "price_override_minor": 1234, "created": now - 10},
    ], services=[{"id": "svc1", "price_minor": 5000}])
    body = client.get(f"{PREFIX}/growth/invoice-report", headers=operator_auth).json()
    assert body["current"]["_all"]["avg_invoice_value_minor"] == 1234


def test_report_excludes_a_booking_whose_service_no_longer_resolves_never_zero(client, operator_auth):
    """THE HONESTY RULE this whole feature was built around — an unresolvable price must never be
    silently averaged in as 0."""
    now = int(time.time())
    _wire(client, bookings=[
        {"id": "b1", "branch_id": "brnA", "status": "attended", "service_ids": ["deleted-svc"],
         "package_id": "", "price_override_minor": None, "created": now - 10},
    ], services=[])
    body = client.get(f"{PREFIX}/growth/invoice-report", headers=operator_auth).json()
    stats = body["current"]["_all"]
    assert stats["attended_priced"] == 0
    assert stats["attended_unpriced"] == 1
    assert stats["avg_invoice_value_minor"] is None


def test_report_splits_by_branch(client, operator_auth):
    now = int(time.time())
    _wire(client, bookings=[
        {"id": "b1", "branch_id": "brnA", "status": "attended", "service_ids": ["svc1"],
         "package_id": "", "price_override_minor": None, "created": now - 10},
        {"id": "b2", "branch_id": "brnB", "status": "attended", "service_ids": ["svc1"],
         "package_id": "", "price_override_minor": None, "created": now - 10},
    ], services=[{"id": "svc1", "price_minor": 4000}])
    body = client.get(f"{PREFIX}/growth/invoice-report", headers=operator_auth).json()
    assert body["current"]["brnA"]["avg_invoice_value_minor"] == 4000
    assert body["current"]["brnB"]["avg_invoice_value_minor"] == 4000
    assert body["current"]["_all"]["attended_priced"] == 2


def test_report_calls_the_peer_twice_for_current_and_previous_window(client, operator_auth):
    stub = _wire(client, bookings=[])
    client.get(f"{PREFIX}/growth/invoice-report?days=7", headers=operator_auth)
    assert len(stub.calls) == 2
    cur, prev = stub.calls
    assert cur["since"] > prev["since"] and cur["until"] > prev["until"]
    assert prev["until"] == cur["since"]


def test_report_surfaces_truncation_honestly(client, operator_auth):
    _wire(client, bookings=[], truncated=True)
    body = client.get(f"{PREFIX}/growth/invoice-report", headers=operator_auth).json()
    assert body["truncated"] is True
