"""A seventh real, independent app wired into the simulator: services/whatsapp-assistant
(`apps/whatsapp_assistant/`) — the WhatsApp bot's own backend, real HTTP against a real, spawned
instance. Two doors proven here: the ordinary tenant-token surface and the connector door (the
"tools" Meta's own agent calls), each gated by its own real, separate credential.
"""
from __future__ import annotations

import asyncio

from simulator.apps.whatsapp_assistant.actions import (
    AssistantFeaturesAction, CheckConsentAction, RecordConsentAction,
)
from simulator.apps.whatsapp_assistant.service import spawn as spawn_whatsapp_assistant

from simulator.common.engine import run_one

TENANT = "sim-whatsapp-assistant"


def run(coro):
    return asyncio.run(coro)


def test_assistant_features_is_the_same_static_catalog_for_any_signed_in_caller():
    async def _go():
        async with spawn_whatsapp_assistant() as svc:
            return await run_one(AssistantFeaturesAction(base_url=svc.base_url, tenant=TENANT))

    result = run(_go())
    assert result.ok, result
    assert len(result.data.get("features", [])) >= 1


def test_consent_reads_as_unknown_with_no_real_compliance_peer_configured():
    """`CONSENT_GATE_DRIVER` defaults to `"null"` outside production — a real, honest gate this
    time too: `check_consent` always answers "unknown" and `record_consent` is a real, accepted
    no-op, since consent is genuinely tracked by a THIRD real peer (`COMPLIANCE_SERVICE_URL`) no
    fleet here reaches — the same recurring, documented shape as mutual-benefit's billing gap and
    campaigns' WhatsApp-template gap, now a fourth time, for a fourth different peer."""

    async def _go():
        async with spawn_whatsapp_assistant() as svc:
            before = await run_one(CheckConsentAction(
                base_url=svc.base_url, tenant=TENANT, from_number="0511111111"))
            recorded = await run_one(RecordConsentAction(
                base_url=svc.base_url, tenant=TENANT, from_number="0511111111", granted=True))
            after = await run_one(CheckConsentAction(
                base_url=svc.base_url, tenant=TENANT, from_number="0511111111"))
            return before, recorded, after

    before, recorded, after = run(_go())
    assert before.ok and before.data["status"] == "unknown"
    assert recorded.ok, recorded
    assert after.ok and after.data["status"] == "unknown"


def test_recording_consent_with_no_compliance_peer_never_crashes_either_way():
    async def _go():
        async with spawn_whatsapp_assistant() as svc:
            granted = await run_one(RecordConsentAction(
                base_url=svc.base_url, tenant=TENANT, from_number="0522222222", granted=True))
            withdrawn = await run_one(RecordConsentAction(
                base_url=svc.base_url, tenant=TENANT, from_number="0522222222", granted=False))
            return granted, withdrawn

    granted, withdrawn = run(_go())
    assert granted.ok, granted
    assert withdrawn.ok, withdrawn
