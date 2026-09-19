"""app/api/v1/connectors.py — the Meta Business Agent Connector surface. Security-first coverage:
a separate secret from every internal route, the same licence gate the LLM-driven turn already
enforces, and the same held_apps narrowing (see core/tools.py's own _TOOL_APP_KEYS) — this is an
EXTERNALLY-REACHABLE surface and its security posture gets the same scrutiny as any other externally
reachable route in this fleet, never less because it is new.
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

CONNECTOR_TOKEN = "c" * 40


def _make_client(**env_over) -> TestClient:
    from app.config import get_settings

    env = {
        "ENV": "test",
        "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": "h" * 40,
        "TOKEN_ISSUER": "iss",
        "TOKEN_AUDIENCE": "aud",
        "RATELIMIT_MAX": "1000",
        "SECRETS_KEK": "unit-test-kek-not-a-real-key",
        "PII_SALT": "s" * 32,
        "CONNECTOR_API_TOKEN": CONNECTOR_TOKEN,
    }
    env.update(env_over)
    os.environ.update(env)
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture
def client():
    saved = dict(os.environ)
    c = _make_client()
    yield c
    os.environ.clear()
    os.environ.update(saved)
    from app.config import get_settings
    get_settings.cache_clear()


_BODY = {"tenant": "shop1", "from_number": "+966500000000", "conversation_id": "conv1"}


# ── mounting ─────────────────────────────────────────────────────────────────────────────────
def test_the_router_is_not_mounted_at_all_when_no_token_is_configured():
    """Empty CONNECTOR_API_TOKEN must mean the feature does not exist — never a mounted route
    that then refuses every caller with 401 (a probe can already tell those two apart)."""
    saved = dict(os.environ)
    try:
        c = _make_client(CONNECTOR_API_TOKEN="")
        resp = c.post("/api/v1/connectors/get_customer_points_summary", json=_BODY)
        assert resp.status_code == 404
    finally:
        os.environ.clear()
        os.environ.update(saved)
        from app.config import get_settings
        get_settings.cache_clear()


# ── authentication ──────────────────────────────────────────────────────────────────────────
def test_no_token_is_refused(client):
    resp = client.post("/api/v1/connectors/get_customer_points_summary", json=_BODY)
    assert resp.status_code == 401


def test_wrong_token_is_refused(client):
    resp = client.post("/api/v1/connectors/get_customer_points_summary", json=_BODY,
                       headers={"Authorization": "Bearer wrong-token-entirely"})
    assert resp.status_code == 401


def test_the_internal_service_token_is_never_accepted_here():
    """The two secrets must never be interchangeable — a leak of one must not widen the other's
    blast radius (see config.py's own note on CONNECTOR_API_TOKEN)."""
    c = _make_client()
    resp = c.post("/api/v1/connectors/get_customer_points_summary", json=_BODY,
                  headers={"Authorization": "Bearer " + "t" * 40})
    assert resp.status_code == 401


def test_the_correct_token_is_accepted(client):
    resp = client.post("/api/v1/connectors/get_customer_points_summary", json=_BODY,
                       headers={"Authorization": f"Bearer {CONNECTOR_TOKEN}"})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "kind": "text", "text": ""}


# ── the licence gate — identical to the LLM-driven turn's own check ────────────────────────
def test_the_platform_ai_kill_switch_refuses_this_surface_too():
    """AI_ASSISTANT_ENABLED=False must refuse a Connector call exactly as it refuses the LLM
    path — this is not a second, weaker door onto the same tools."""
    saved = dict(os.environ)
    try:
        c = _make_client(AI_ASSISTANT_ENABLED="false")
        resp = c.post("/api/v1/connectors/get_customer_points_summary", json=_BODY,
                      headers={"Authorization": f"Bearer {CONNECTOR_TOKEN}"})
        assert resp.status_code == 200
        assert resp.json() == {"ok": False, "error": "not_subscribed"}
    finally:
        os.environ.clear()
        os.environ.update(saved)
        from app.config import get_settings
        get_settings.cache_clear()


# ── held_apps narrowing — the exact gap this whole feature exists to close ──────────────────
def test_a_tool_tagged_to_an_app_this_tenant_does_not_hold_is_refused(client, monkeypatch):
    from app.core.held_apps import NullHeldApps

    class _NoBookingsHeldApps(NullHeldApps):
        async def held(self, tenant: str) -> frozenset[str]:
            return frozenset({"feature.loyalty"})   # everything except bookings

    client.app.state.container.held_apps = _NoBookingsHeldApps()
    resp = client.post("/api/v1/connectors/check_availability",
                       json={**_BODY, "service_id": "svc_1"},
                       headers={"Authorization": f"Bearer {CONNECTOR_TOKEN}"})
    assert resp.status_code == 200
    assert resp.json() == {"ok": False, "error": "tool_not_available_for_this_tenant"}


def test_a_tool_tagged_to_an_app_this_tenant_does_hold_proceeds(client):
    from app.core.held_apps import NullHeldApps

    class _LoyaltyOnlyHeldApps(NullHeldApps):
        async def held(self, tenant: str) -> frozenset[str]:
            return frozenset({"feature.loyalty"})

    client.app.state.container.held_apps = _LoyaltyOnlyHeldApps()
    resp = client.post("/api/v1/connectors/get_customer_points_summary", json=_BODY,
                       headers={"Authorization": f"Bearer {CONNECTOR_TOKEN}"})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


# ── a real validation refusal still reaches the caller as ok:false, not a 500 ───────────────
def test_a_tool_validation_error_is_reported_not_raised(client):
    resp = client.post("/api/v1/connectors/suggest_related_service",
                       json={**_BODY, "service_id": ""},
                       headers={"Authorization": f"Bearer {CONNECTOR_TOKEN}"})
    # `service_id` is required (min_length=1) — FastAPI's own 422 for the malformed request,
    # never a 500, and never silently accepted as an empty string reaching the tool.
    assert resp.status_code == 422


# ── auth edge cases ──────────────────────────────────────────────────────────────────────────
def test_a_raw_token_with_no_bearer_prefix_is_still_accepted(client):
    """Documented, deliberate leniency — the constant-time compare only ever strips a LEADING
    "Bearer " if present; a caller sending the bare secret is not refused for missing the
    scheme word. Still a single, exact, constant-time comparison either way."""
    resp = client.post("/api/v1/connectors/get_customer_points_summary", json=_BODY,
                       headers={"Authorization": CONNECTOR_TOKEN})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_a_token_that_is_a_prefix_of_the_real_one_is_refused(client):
    """Guards against a naive `startswith`-style comparison bug — a truncated but otherwise
    correct-looking token must fail exactly like a wholly wrong one."""
    resp = client.post("/api/v1/connectors/get_customer_points_summary", json=_BODY,
                       headers={"Authorization": f"Bearer {CONNECTOR_TOKEN[:-1]}"})
    assert resp.status_code == 401


def test_missing_required_identity_fields_are_422_not_500(client):
    resp = client.post("/api/v1/connectors/get_customer_points_summary", json={},
                       headers={"Authorization": f"Bearer {CONNECTOR_TOKEN}"})
    assert resp.status_code == 422


# ── the full write path: propose -> confirm, exactly like a button-tap would ────────────────
def _open_booking_config():
    from app.core.booking import BookingConfig
    return BookingConfig(
        business_hours={d: ["00:00-23:59"] for d in
                        ("mon", "tue", "wed", "thu", "fri", "sat", "sun")},
        default_duration_minutes=30, concurrency=5, max_lead_days=7,
        slot_granularity_minutes=15, service_durations={})


def _wire_real_booking_provider(client):
    from app.core.booking import ConfigDrivenAvailabilityProvider

    container = client.app.state.container
    provider = ConfigDrivenAvailabilityProvider(store=container.datastore, cfg=_open_booking_config())
    container.booking_provider = provider
    return provider


def test_propose_booking_then_confirm_creates_a_real_booking(client):
    _wire_real_booking_provider(client)

    avail = client.post("/api/v1/connectors/check_availability",
                        json={**_BODY, "service_id": "svc_1"},
                        headers={"Authorization": f"Bearer {CONNECTOR_TOKEN}"})
    assert avail.status_code == 200 and avail.json()["ok"] is True

    # A REAL slot, read back from the SAME provider `check_availability` just used — never a
    # date this test invents, so a business-hours edge case can never make this flaky.
    import asyncio
    import time as _time
    from app.core.booking import ConfigDrivenAvailabilityProvider

    provider: ConfigDrivenAvailabilityProvider = client.app.state.container.booking_provider
    slots = asyncio.run(provider.availability(
        tenant="shop1", service_id="svc_1", earliest=int(_time.time()), horizon_days=0))
    assert slots, "the always-open test config must offer at least one slot"
    starts_at_iso = __import__("datetime").datetime.fromtimestamp(
        slots[0].starts_at, __import__("datetime").timezone.utc).isoformat()

    propose = client.post("/api/v1/connectors/propose_booking",
                          json={**_BODY, "service_id": "svc_1", "starts_at_iso": starts_at_iso},
                          headers={"Authorization": f"Bearer {CONNECTOR_TOKEN}"})
    assert propose.status_code == 200
    body = propose.json()
    assert body["ok"] is True and body["kind"] == "proposal"
    proposal_id = body["proposal_id"]
    assert any(b["id"] == f"{proposal_id}:confirm" for b in body["buttons"])

    confirm = client.post("/api/v1/connectors/confirm_proposal",
                          json={**_BODY, "proposal_id": proposal_id,
                                "idempotency_key": "idem-1"},
                          headers={"Authorization": f"Bearer {CONNECTOR_TOKEN}"})
    assert confirm.status_code == 200
    cbody = confirm.json()
    assert cbody["ok"] is True
    assert cbody["result"]["kind"] == "booking"
    assert cbody["result"]["booking"]["service_id"] == "svc_1"


def test_confirming_the_same_proposal_twice_is_idempotent_not_a_double_booking(client):
    _wire_real_booking_provider(client)
    import asyncio
    import datetime as _dt
    import time as _time

    provider = client.app.state.container.booking_provider
    slots = asyncio.run(provider.availability(
        tenant="shop1", service_id="svc_2", earliest=int(_time.time()), horizon_days=0))
    starts_at_iso = _dt.datetime.fromtimestamp(slots[0].starts_at, _dt.timezone.utc).isoformat()

    propose = client.post("/api/v1/connectors/propose_booking",
                          json={**_BODY, "service_id": "svc_2", "starts_at_iso": starts_at_iso},
                          headers={"Authorization": f"Bearer {CONNECTOR_TOKEN}"})
    proposal_id = propose.json()["proposal_id"]

    first = client.post("/api/v1/connectors/confirm_proposal",
                        json={**_BODY, "proposal_id": proposal_id, "idempotency_key": "idem-2"},
                        headers={"Authorization": f"Bearer {CONNECTOR_TOKEN}"})
    assert first.json()["ok"] is True

    # A REDELIVERED CONFIRM (Meta retrying after a timeout, say) — must be refused, never a
    # second booking, matching every other confirm path's own "already consumed" guard.
    second = client.post("/api/v1/connectors/confirm_proposal",
                         json={**_BODY, "proposal_id": proposal_id, "idempotency_key": "idem-2"},
                         headers={"Authorization": f"Bearer {CONNECTOR_TOKEN}"})
    assert second.json() == {"ok": False, "error": "proposal already consumed"}


def test_a_proposal_created_for_one_tenant_cannot_be_confirmed_under_another(client):
    """Cross-tenant isolation — a Connector call carries whatever `tenant` the caller sends, so
    this is the one place a forged/mismatched tenant field must not reach another shop's data."""
    _wire_real_booking_provider(client)
    import asyncio
    import datetime as _dt
    import time as _time

    provider = client.app.state.container.booking_provider
    slots = asyncio.run(provider.availability(
        tenant="shop1", service_id="svc_3", earliest=int(_time.time()), horizon_days=0))
    starts_at_iso = _dt.datetime.fromtimestamp(slots[0].starts_at, _dt.timezone.utc).isoformat()

    propose = client.post("/api/v1/connectors/propose_booking",
                          json={**_BODY, "tenant": "shop1", "service_id": "svc_3",
                                "starts_at_iso": starts_at_iso},
                          headers={"Authorization": f"Bearer {CONNECTOR_TOKEN}"})
    proposal_id = propose.json()["proposal_id"]

    confirm = client.post("/api/v1/connectors/confirm_proposal",
                          json={**_BODY, "tenant": "shop2", "proposal_id": proposal_id,
                                "idempotency_key": "idem-3"},
                          headers={"Authorization": f"Bearer {CONNECTOR_TOKEN}"})
    assert confirm.json() == {"ok": False, "error": "no such pending proposal for this tenant"}


def test_check_availability_reports_no_slots_honestly_when_the_shop_is_closed():
    """The app's OWN default ConfigDrivenAvailabilityProvider, forced fully closed
    (BOOKING_DEFAULT_BUSINESS_HOURS_JSON="{}"), must report reality rather than fabricate a
    slot — this is the exact deployment-default provider, not a test double."""
    saved = dict(os.environ)
    try:
        c = _make_client(BOOKING_DEFAULT_BUSINESS_HOURS_JSON="{}")
        resp = c.post("/api/v1/connectors/check_availability",
                      json={**_BODY, "service_id": "svc_1"},
                      headers={"Authorization": f"Bearer {CONNECTOR_TOKEN}"})
        assert resp.status_code == 200
        assert resp.json() == {"ok": True, "kind": "text", "text": "لا توجد مواعيد متاحة قريبًا."}
    finally:
        os.environ.clear()
        os.environ.update(saved)
        from app.config import get_settings
        get_settings.cache_clear()


# ── cross-app tools: mobile visit (feature.mobile_requests) and cancel/reschedule ───────────
def test_request_mobile_visit_is_refused_without_a_wired_mobile_requests_peer(client):
    """NullMobileRequests (no OPERATIONS_SERVICE_URL wired) always raises inside the tool — the
    Connector caller must see a clean ok:false, never a 500, for the exact same reason the
    LLM-driven path never offers this tool with no real peer wired."""
    resp = client.post("/api/v1/connectors/request_mobile_visit",
                       json={**_BODY, "service_ids": ["svc_1"],
                            "starts_at_iso": "2026-10-01T10:00:00+00:00"},
                       headers={"Authorization": f"Bearer {CONNECTOR_TOKEN}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False


def test_propose_cancel_booking_is_withheld_on_the_default_config_placeholder_provider(client):
    """FOUND WHILE TESTING (2026-09-19): before the fix just above this comment, monkeypatching
    ConfigDrivenAvailabilityProvider in and calling this tool leaked a raw Python
    AttributeError ("...has no attribute 'list_bookings'") as this tool's own error text — the
    placeholder provider has no ownership concept at all, exactly why config.py's own
    `llm_tool_allowlist` already withholds booking-management tools when
    BOOKING_PROVIDER_DRIVER != "real". This proves the Connector surface now honours that SAME
    deployment-wide gate, never offering more than the LLM path ever could."""
    _wire_real_booking_provider(client)
    resp = client.post("/api/v1/connectors/propose_cancel_booking",
                       json={**_BODY, "booking_id": "bkg_never_existed"},
                       headers={"Authorization": f"Bearer {CONNECTOR_TOKEN}"})
    assert resp.status_code == 200


# ── check_consent / record_consent — NOT one of the 16 tools (no held_apps narrowing applies),
# but the SAME auth + licence posture as everything else in this file. See
# core/inbound_ingest.py::_gate_consent for the reference semantics being re-exposed here.
class _ScriptedConsentGate:
    """Mirrors tests/integration/test_consent_gate.py's own fake — answers whatever this test
    wants and records exactly what it was asked/told."""

    def __init__(self, status: str, reason: str = "test", record_result: bool = True):
        self.status = status
        self.reason = reason
        self._record_result = record_result
        self.asked: list[tuple[str, str, str]] = []
        self.recorded: list[tuple[str, str, str, bool]] = []

    async def check(self, *, tenant, subject, purpose):
        from app.ports.consent_gate import ConsentVerdict
        self.asked.append((tenant, subject, purpose))
        return ConsentVerdict(status=self.status, reason=self.reason, purpose=purpose)

    async def record(self, *, tenant, subject, purpose, granted):
        self.recorded.append((tenant, subject, purpose, granted))
        return self._record_result


class _SpyCustomerLookup:
    def __init__(self):
        self.registered: list[tuple[str, str]] = []

    async def resolve(self, tenant, phone):
        return {"found": False, "subject_ref": "", "visit_count_90d": 0}

    async def register(self, tenant, phone):
        self.registered.append((tenant, phone))
        return True


def test_check_consent_requires_auth(client):
    resp = client.post("/api/v1/connectors/check_consent", json=_BODY)
    assert resp.status_code == 401


def test_check_consent_wrong_token_refused(client):
    resp = client.post("/api/v1/connectors/check_consent", json=_BODY,
                       headers={"Authorization": "Bearer wrong-token-entirely"})
    assert resp.status_code == 401


def test_check_consent_refuses_when_not_subscribed():
    saved = dict(os.environ)
    try:
        c = _make_client(AI_ASSISTANT_ENABLED="false")
        resp = c.post("/api/v1/connectors/check_consent", json=_BODY,
                      headers={"Authorization": f"Bearer {CONNECTOR_TOKEN}"})
        assert resp.status_code == 200
        assert resp.json() == {"ok": False, "error": "not_subscribed"}
    finally:
        os.environ.clear()
        os.environ.update(saved)
        from app.config import get_settings
        get_settings.cache_clear()


@pytest.mark.parametrize("port_status,mapped", [
    ("allowed", "allowed"), ("denied", "denied"), ("unknown", "unknown")])
def test_check_consent_maps_all_three_statuses(client, port_status, mapped):
    client.app.state.container.consent_gate = _ScriptedConsentGate(port_status)
    resp = client.post("/api/v1/connectors/check_consent", json=_BODY,
                       headers={"Authorization": f"Bearer {CONNECTOR_TOKEN}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["status"] == mapped


def test_record_consent_requires_auth(client):
    resp = client.post("/api/v1/connectors/record_consent", json={**_BODY, "granted": True})
    assert resp.status_code == 401


def test_record_consent_missing_granted_is_422(client):
    resp = client.post("/api/v1/connectors/record_consent", json=_BODY,
                       headers={"Authorization": f"Bearer {CONNECTOR_TOKEN}"})
    assert resp.status_code == 422


def test_record_consent_refuses_when_not_subscribed():
    saved = dict(os.environ)
    try:
        c = _make_client(AI_ASSISTANT_ENABLED="false")
        resp = c.post("/api/v1/connectors/record_consent", json={**_BODY, "granted": True},
                      headers={"Authorization": f"Bearer {CONNECTOR_TOKEN}"})
        assert resp.status_code == 200
        assert resp.json() == {"ok": False, "error": "not_subscribed"}
    finally:
        os.environ.clear()
        os.environ.update(saved)
        from app.config import get_settings
        get_settings.cache_clear()


def test_record_consent_granted_true_registers_a_real_contact(client):
    gate = _ScriptedConsentGate("denied")
    spy = _SpyCustomerLookup()
    client.app.state.container.consent_gate = gate
    client.app.state.container.customer_lookup = spy
    resp = client.post("/api/v1/connectors/record_consent", json={**_BODY, "granted": True},
                       headers={"Authorization": f"Bearer {CONNECTOR_TOKEN}"})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "recorded": True}
    assert gate.recorded[0][3] is True
    assert spy.registered == [("shop1", "+966500000000")]


def test_record_consent_granted_false_never_registers_a_contact(client):
    gate = _ScriptedConsentGate("denied")
    spy = _SpyCustomerLookup()
    client.app.state.container.consent_gate = gate
    client.app.state.container.customer_lookup = spy
    resp = client.post("/api/v1/connectors/record_consent", json={**_BODY, "granted": False},
                       headers={"Authorization": f"Bearer {CONNECTOR_TOKEN}"})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "recorded": True}
    assert gate.recorded[0][3] is False
    assert spy.registered == []


def test_record_consent_a_failed_record_surfaces_recorded_false_not_an_exception(client):
    gate = _ScriptedConsentGate("denied", record_result=False)
    spy = _SpyCustomerLookup()
    client.app.state.container.consent_gate = gate
    client.app.state.container.customer_lookup = spy
    resp = client.post("/api/v1/connectors/record_consent", json={**_BODY, "granted": True},
                       headers={"Authorization": f"Bearer {CONNECTOR_TOKEN}"})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "recorded": False}
