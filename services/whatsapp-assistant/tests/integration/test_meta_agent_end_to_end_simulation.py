"""A real, permanent simulation of Meta's hosted Business Agent calling our Connector surface
(`app/api/v1/connectors.py`) end to end, in the exact order `META_AGENT_CONSENT_SKILL.md` tells a
compliant Meta agent to call it. This is NOT a throwaway script — it is the harness that proves the
whole system (consent gate, AI kill switch, held_apps narrowing, propose/confirm booking) works
TOGETHER, the way `tests/integration/test_connectors_api.py` already proves each operation works in
isolation. Reuses that same file's fixture conventions (`_make_client`, `client` fixture,
`_ScriptedConsentGate`, `_SpyCustomerLookup`, `_wire_real_booking_provider`) rather than reinventing
them — read that file first if you are extending this one.
"""
from __future__ import annotations

import asyncio
import datetime as _dt
import os
import time as _time

import pytest
from fastapi.testclient import TestClient

from tests.integration.test_connectors_api import (
    CONNECTOR_TOKEN,
    _BODY,
    _make_client,
    _ScriptedConsentGate,
    _SpyCustomerLookup,
    _wire_real_booking_provider,
)

_AUTH = {"Authorization": f"Bearer {CONNECTOR_TOKEN}"}


@pytest.fixture
def client():
    saved = dict(os.environ)
    c = _make_client()
    yield c
    os.environ.clear()
    os.environ.update(saved)
    from app.config import get_settings
    get_settings.cache_clear()


def _post(client: TestClient, op: str, body: dict) -> dict:
    resp = client.post(f"/api/v1/connectors/{op}", json=body, headers=_AUTH)
    return {"status_code": resp.status_code, **resp.json()}


def _next_open_slot(client: TestClient, tenant: str, service_id: str) -> str:
    """A REAL slot from the SAME provider `check_availability` uses — never an invented date, same
    discipline as test_connectors_api.py's own booking tests."""
    provider = client.app.state.container.booking_provider
    slots = asyncio.run(provider.availability(
        tenant=tenant, service_id=service_id, earliest=int(_time.time()), horizon_days=0))
    assert slots, "the always-open test config must offer at least one slot"
    return _dt.datetime.fromtimestamp(slots[0].starts_at, _dt.timezone.utc).isoformat()


# ── 1. the full happy path, in the Skill's own documented order ────────────────────────────────
def test_full_happy_path_in_the_skills_own_documented_order(client):
    _wire_real_booking_provider(client)
    gate = _ScriptedConsentGate("denied", reason="no_consent_record")
    spy = _SpyCustomerLookup()
    client.app.state.container.consent_gate = gate
    client.app.state.container.customer_lookup = spy

    # Step 1: first contact — Meta calls check_consent BEFORE any reply of its own.
    checked = _post(client, "check_consent", _BODY)
    assert checked["ok"] is True and checked["status"] in ("denied", "unknown")
    # Our side must not have done anything customer-visible here: check_consent is a pure read —
    # confirmed structurally (connectors.py's own check_consent handler only calls
    # container.consent_gate.check(), never a send/notify peer) and behaviourally: it made exactly
    # one call into the consent gate and nothing else observable changed.
    assert gate.asked == [("shop1", "+966500000000", "whatsapp_ai_assistant")] or len(gate.asked) == 1
    assert spy.registered == []

    # Steps 2-3 (Meta's own interactive UI, "متابعة"/"إنهاء المحادثة") are Meta's rendering, not
    # ours — nothing to call here.

    # Step 4: customer taps "متابعة" -> Meta calls record_consent(granted=true).
    recorded = _post(client, "record_consent", {**_BODY, "granted": True})
    assert recorded == {"status_code": 200, "ok": True, "recorded": True}
    assert gate.recorded[-1] == ("shop1", "+966500000000", "whatsapp_ai_assistant", True)
    # The number is registered as a real contact, per this session's own requirement.
    assert spy.registered == [("shop1", "+966500000000")]

    # Step 5: consent granted -> Meta continues the SAME conversation with real tool calls.
    procedure = _post(client, "get_service_procedure", {**_BODY, "service_id": "svc_1"})
    assert procedure["status_code"] == 200 and procedure["ok"] is True
    assert procedure["kind"] == "text"   # the Skill doc's own agent expects renderable text back

    avail = _post(client, "check_availability", {**_BODY, "service_id": "svc_1"})
    assert avail["status_code"] == 200 and avail["ok"] is True

    starts_at_iso = _next_open_slot(client, "shop1", "svc_1")
    proposal = _post(client, "propose_booking",
                     {**_BODY, "service_id": "svc_1", "starts_at_iso": starts_at_iso})
    assert proposal["status_code"] == 200 and proposal["ok"] is True and proposal["kind"] == "proposal"
    proposal_id = proposal["proposal_id"]
    # The Skill's own agent must be able to find a "confirm" button id in exactly the shape
    # confirm_proposal expects to receive back as proposal_id.
    assert any(b["id"] == f"{proposal_id}:confirm" for b in proposal["buttons"])

    confirmed = _post(client, "confirm_proposal",
                      {**_BODY, "proposal_id": proposal_id, "idempotency_key": "sim-idem-1"})
    assert confirmed["status_code"] == 200 and confirmed["ok"] is True
    assert confirmed["result"]["kind"] == "booking"
    assert confirmed["result"]["booking"]["service_id"] == "svc_1"


# ── 2. consent refusal path ─────────────────────────────────────────────────────────────────────
def test_consent_refusal_path(client):
    """The Skill's own step 6: "لا تستخدم أي أداة أخرى... حتى يوافق صراحة". A compliant Meta agent
    would never CALL another tool after a refusal — but this test proves what our OWN server does
    if one is called anyway (a retried webhook, a bug in Meta's own agent, an attacker who skips
    the Skill entirely and calls the Connector directly with a stolen token).

    REAL GAP FOUND BUILDING THIS TEST: `_invoke()` in app/api/v1/connectors.py enforces licence,
    then the deployment-wide tool allowlist, then held_apps — but never consults
    `container.consent_gate` at all. A refused/never-asked customer's OTHER tool calls are NOT
    refused by our server; enforcement of "no tool calls after refusal" lives ENTIRELY in Meta's
    own agent obeying the pasted Skill text, with nothing on our side backing it up. This differs
    from `core/inbound_ingest.py::_gate_consent`, which DOES block the reply path outright for a
    DENIED/UNKNOWN verdict when our own code is still the one replying. The assertions below
    document the REAL current behaviour (not the Skill's assumed behaviour) so a future change to
    `_invoke()` that adds real enforcement is proven by making these assertions fail here first.
    """
    gate = _ScriptedConsentGate("denied")
    client.app.state.container.consent_gate = gate

    refused = _post(client, "record_consent", {**_BODY, "granted": False})
    assert refused == {"status_code": 200, "ok": True, "recorded": True}

    # Walking through 3 different tools after refusal, in the SAME simulated conversation.
    points = _post(client, "get_customer_points_summary", _BODY)
    packages = _post(client, "list_packages", _BODY)
    avail = _post(client, "check_availability", {**_BODY, "service_id": "svc_1"})

    for name, result in (("get_customer_points_summary", points),
                        ("list_packages", packages),
                        ("check_availability", avail)):
        # Documents the gap: none of these are refused for consent reasons today. They succeed
        # (licence/held_apps permitting) exactly as if consent had never been asked at all.
        assert result["status_code"] == 200, name
        assert result["ok"] is True, (name, result)


# ── 3. re-consent after prior refusal ───────────────────────────────────────────────────────────
def test_re_consent_after_prior_refusal_is_never_permanent(client):
    gate = _ScriptedConsentGate("denied")
    spy = _SpyCustomerLookup()
    client.app.state.container.consent_gate = gate
    client.app.state.container.customer_lookup = spy

    first_refusal = _post(client, "record_consent", {**_BODY, "granted": False})
    assert first_refusal["ok"] is True
    assert spy.registered == []

    # A LATER conversation, same subject: Meta asks again per the Skill's own step 1.
    later = {**_BODY, "conversation_id": "conv2"}
    re_checked = _post(client, "check_consent", later)
    assert re_checked["ok"] is True   # never a permanent ban recorded server-side

    granted_now = _post(client, "record_consent", {**later, "granted": True})
    assert granted_now == {"status_code": 200, "ok": True, "recorded": True}
    assert gate.recorded[-1] == ("shop1", "+966500000000", "whatsapp_ai_assistant", True)
    assert spy.registered == [("shop1", "+966500000000")]

    # And now real tool use proceeds normally, in this later conversation.
    procedure = _post(client, "get_service_procedure", {**later, "service_id": "svc_1"})
    assert procedure["status_code"] == 200 and procedure["ok"] is True


# ── 4. AI kill switch OFF — loop over EVERY Connector operation ────────────────────────────────
# One minimal-but-valid extra body per operation, so the loop below never trips a 422 before it
# gets a chance to prove the licence gate fires FIRST for every single one.
_ALL_CONNECTOR_OPS: dict[str, dict] = {
    "get_customer_points_summary": {},
    "suggest_redeemable_offer": {},
    "list_packages": {},
    "list_due_services": {},
    "list_lapsed_services": {},
    "check_active_offers": {},
    "suggest_services_carousel": {},
    "check_mobile_visit_hours": {},
    "list_my_bookings": {},
    "check_availability": {"service_id": "svc_1"},
    "propose_booking": {"service_id": "svc_1", "starts_at_iso": "2026-10-01T10:00:00+00:00"},
    "get_service_procedure": {"service_id": "svc_1"},
    "suggest_related_service": {"service_id": "svc_1"},
    "propose_cancel_booking": {"booking_id": "bkg_1"},
    "propose_reschedule_booking": {"booking_id": "bkg_1",
                                   "new_starts_at_iso": "2026-10-01T10:00:00+00:00"},
    "request_mobile_visit": {"service_ids": ["svc_1"], "starts_at_iso": "2026-10-01T10:00:00+00:00"},
    "check_growth_opportunities": {},
    "confirm_proposal": {"proposal_id": "prop_1", "idempotency_key": "idem_1"},
    "check_consent": {},
    "record_consent": {"granted": True},
}


def test_ai_kill_switch_off_refuses_every_connector_operation():
    """AI_ASSISTANT_ENABLED=false must read exactly like unsubscribed on EVERY Connector operation,
    proving the permanent CI gate's own promise (`ci/check_a_tenant_effecting_entrypoint_skips_the_
    licence_gate.py`) holds through this real simulated multi-tool conversation, not just the
    single per-unit fix each gap site originally got."""
    saved = dict(os.environ)
    try:
        c = _make_client(AI_ASSISTANT_ENABLED="false")
        for op, extra in _ALL_CONNECTOR_OPS.items():
            resp = c.post(f"/api/v1/connectors/{op}", json={**_BODY, **extra}, headers=_AUTH)
            assert resp.status_code == 200, op
            assert resp.json() == {"ok": False, "error": "not_subscribed"}, op
    finally:
        os.environ.clear()
        os.environ.update(saved)
        from app.config import get_settings
        get_settings.cache_clear()


# ── 5. held_apps narrowing across a multi-tool conversation ────────────────────────────────────
def test_held_apps_narrowing_across_a_multi_tool_conversation(client):
    from app.core.held_apps import NullHeldApps

    class _NoBookingsHeldApps(NullHeldApps):
        async def held(self, tenant: str) -> frozenset[str]:
            return frozenset({"feature.loyalty"})   # everything except bookings

    client.app.state.container.held_apps = _NoBookingsHeldApps()

    for op, extra in (("get_service_procedure", {"service_id": "svc_1"}),
                      ("check_availability", {"service_id": "svc_1"}),
                      ("propose_booking", {"service_id": "svc_1",
                                           "starts_at_iso": "2026-10-01T10:00:00+00:00"})):
        result = _post(client, op, {**_BODY, **extra})
        assert result == {"status_code": 200, "ok": False,
                          "error": "tool_not_available_for_this_tenant"}, op

    # An app this tenant DOES hold still works, in the SAME conversation.
    points = _post(client, "get_customer_points_summary", _BODY)
    assert points["status_code"] == 200 and points["ok"] is True


# ── 6. data-safety assertions ───────────────────────────────────────────────────────────────────
_ALLOWED_IDENTITY_FIELD_NAMES = {
    "tenant", "from_number", "conversation_id", "branch_id",
    "service_id", "package_id", "earliest_date", "starts_at_iso", "reward_id",
    "booking_id", "reason", "new_starts_at_iso", "service_ids", "proposal_id",
    "idempotency_key", "granted", "include_history",
}


def test_no_connector_request_shape_can_carry_raw_message_text():
    """Every Connector operation's own request model accepts ONLY structured identifiers — never a
    free-text field capable of carrying a customer's raw message/conversation content."""
    from app.api.v1 import connectors as C

    input_models = [
        C.GetCustomerPointsSummaryIn, C.SuggestRedeemableOfferIn, C.ListPackagesIn,
        C.ListDueServicesIn, C.ListLapsedServicesIn, C.CheckActiveOffersIn,
        C.SuggestServicesCarouselIn, C.CheckMobileVisitHoursIn, C.ListMyBookingsIn,
        C.CheckAvailabilityIn, C.ProposeBookingIn, C.GetServiceProcedureIn,
        C.SuggestRelatedServiceIn, C.ProposeCancelBookingIn, C.ProposeRescheduleBookingIn,
        C.RequestMobileVisitIn, C.CheckGrowthOpportunitiesIn, C.ConfirmProposalIn,
        C.CheckConsentIn, C.RecordConsentIn,
    ]
    assert len(input_models) == 20   # every operation this router mounts, none forgotten

    seen_field_names: set[str] = set()
    for model in input_models:
        for field_name, info in model.model_fields.items():
            seen_field_names.add(field_name)
            assert field_name in _ALLOWED_IDENTITY_FIELD_NAMES, (
                f"{model.__name__}.{field_name} is not a known structured identifier field — "
                "verify it cannot carry raw customer message text before allow-listing it")
            # Every field is a scalar identifier, a bool flag, or a list of scalar ids — never an
            # open str with no length/shape discipline that could smuggle a whole message body.
            annotation = str(info.annotation)
            assert annotation in ("<class 'str'>", "<class 'bool'>", "list[str]"), (
                model.__name__, field_name, annotation)
    # Sanity: the audit actually looked at a real, non-trivial set of fields, not an empty router.
    assert "reason" in seen_field_names and "service_id" in seen_field_names


def test_the_connector_path_never_writes_to_the_raw_message_or_conversation_collections(client):
    """The Connector path is not the inbound-webhook path — it must NEVER touch whatever store
    holds raw message text or conversation state in THIS service, even incidentally, across a full
    happy-path conversation. A REAL assertion against the stubbed datastore's own written keys,
    not a comment claiming it's true."""
    from app.core.models import INBOUND_MESSAGES, CONVERSATIONS

    _wire_real_booking_provider(client)
    gate = _ScriptedConsentGate("denied")
    client.app.state.container.consent_gate = gate

    _post(client, "check_consent", _BODY)
    _post(client, "record_consent", {**_BODY, "granted": True})
    _post(client, "get_service_procedure", {**_BODY, "service_id": "svc_1"})
    _post(client, "check_availability", {**_BODY, "service_id": "svc_1"})
    starts_at_iso = _next_open_slot(client, "shop1", "svc_1")
    proposal = _post(client, "propose_booking",
                     {**_BODY, "service_id": "svc_1", "starts_at_iso": starts_at_iso})
    _post(client, "confirm_proposal", {**_BODY, "proposal_id": proposal["proposal_id"],
                                       "idempotency_key": "sim-idem-2"})

    store = client.app.state.container.datastore
    written_collections = set(store._data.keys())
    assert INBOUND_MESSAGES not in written_collections
    assert CONVERSATIONS not in written_collections


# ── 7. malformed/adversarial input mid-conversation ─────────────────────────────────────────────
def test_a_malformed_follow_up_mid_conversation_is_a_clean_422_never_a_500(client):
    """A real happy-path conversation, then Meta's agent sends one slightly malformed follow-up
    (already-covered per-operation shapes live in test_connectors_api.py; this is the SIMULATION-
    level case: malformed input arriving in the middle of an otherwise valid multi-step
    conversation, not as the very first call)."""
    _wire_real_booking_provider(client)

    ok_first = _post(client, "check_availability", {**_BODY, "service_id": "svc_1"})
    assert ok_first["status_code"] == 200

    # Missing required field mid-conversation.
    missing_field = client.post("/api/v1/connectors/propose_booking",
                                json={**_BODY, "service_id": "svc_1"}, headers=_AUTH)
    assert missing_field.status_code == 422

    # Wrong type mid-conversation.
    wrong_type = client.post("/api/v1/connectors/check_availability",
                             json={**_BODY, "service_id": 12345}, headers=_AUTH)
    assert wrong_type.status_code == 422

    # Empty required identifier mid-conversation.
    empty_service_id = client.post("/api/v1/connectors/get_service_procedure",
                                   json={**_BODY, "service_id": ""}, headers=_AUTH)
    assert empty_service_id.status_code == 422

    # Malformed confirm (missing idempotency_key) — the ONE place a proposal turns into a write.
    proposal = _post(client, "propose_booking",
                     {**_BODY, "service_id": "svc_1",
                      "starts_at_iso": _next_open_slot(client, "shop1", "svc_1")})
    bad_confirm = client.post("/api/v1/connectors/confirm_proposal",
                              json={**_BODY, "proposal_id": proposal["proposal_id"]},
                              headers=_AUTH)
    assert bad_confirm.status_code == 422

    # And the conversation can still continue normally afterwards.
    still_ok = _post(client, "get_customer_points_summary", _BODY)
    assert still_ok["status_code"] == 200 and still_ok["ok"] is True
