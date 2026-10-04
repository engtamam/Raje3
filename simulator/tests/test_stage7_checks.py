"""Stage 7 proof: the four generic checks (common/checks.py) run against REAL routes on a REAL,
unmodified services/operations — proving they are genuinely endpoint-agnostic by applying the
SAME four functions to two entirely different routes (add-affiliate and register-referral),
never a check written specifically for one of them."""
from __future__ import annotations

import asyncio

import httpx

from simulator.apps.operations.service import spawn
from simulator.common.checks import (
    check_adversarial_input_never_crashes, check_cross_tenant_isolation,
    check_forged_signature_is_refused, check_wrong_capability_is_refused,
)
from simulator.shared.auth import auth_header, forged_auth_header

TENANT_A = "sim-stage7-a"
TENANT_B = "sim-stage7-b"


def run(coro):
    return asyncio.run(coro)


AFFILIATE_BODY = {"phone": "0511111111", "code": "CHK001", "discount_percent": 15,
                 "reward_type": "fixed_points", "reward_params": {"points": 40}}

REGISTER_BODY = {"code": "NOSUCHCODE", "phone": "0522222222"}


# ── forged signature: two entirely different routes, same check, same result ───────────────────
def test_forged_signature_is_refused_on_the_affiliate_add_route():
    async def _go():
        async with spawn() as svc:
            headers = forged_auth_header(tenant=TENANT_A, caps=("operations.manage",))
            return await check_forged_signature_is_refused(
                method="POST", url=f"{svc.base_url}/api/v1/affiliates",
                json_body=AFFILIATE_BODY, forged_headers=headers)

    result = run(_go())
    assert result.ok, result.detail


def test_forged_signature_is_refused_on_the_till_register_route():
    async def _go():
        async with spawn() as svc:
            headers = forged_auth_header(tenant=TENANT_A, caps=("operations.record",))
            return await check_forged_signature_is_refused(
                method="POST", url=f"{svc.base_url}/api/v1/till/referral/register",
                json_body=REGISTER_BODY, forged_headers=headers)

    result = run(_go())
    assert result.ok, result.detail


# ── missing capability: a validly-signed token that simply lacks the right one ──────────────────
def test_a_till_credential_cannot_reach_the_owner_only_affiliate_add_route():
    async def _go():
        async with spawn() as svc:
            headers = auth_header(tenant=TENANT_A, caps=("operations.record",))  # till, not owner
            return await check_wrong_capability_is_refused(
                method="POST", url=f"{svc.base_url}/api/v1/affiliates",
                json_body=AFFILIATE_BODY, headers=headers)

    result = run(_go())
    assert result.ok, result.detail


def test_a_read_only_credential_cannot_reach_the_till_register_route():
    async def _go():
        async with spawn() as svc:
            headers = auth_header(tenant=TENANT_A, caps=("operations.read",))  # read, not till
            return await check_wrong_capability_is_refused(
                method="POST", url=f"{svc.base_url}/api/v1/till/referral/register",
                json_body=REGISTER_BODY, headers=headers)

    result = run(_go())
    assert result.ok, result.detail


# ── adversarial input: hostile-shaped bodies must never reach a 500 ─────────────────────────────
def test_an_injection_shaped_code_never_crashes_the_register_route():
    async def _go():
        async with spawn() as svc:
            headers = auth_header(tenant=TENANT_A, caps=("operations.record",))
            body = {"code": "1' OR '1'='1", "phone": "0533333333"}
            return await check_adversarial_input_never_crashes(
                method="POST", url=f"{svc.base_url}/api/v1/till/referral/register",
                json_body=body, headers=headers)

    result = run(_go())
    assert result.ok, result.detail


def test_a_negative_invoice_minor_never_crashes_the_register_route():
    async def _go():
        async with spawn() as svc:
            headers = auth_header(tenant=TENANT_A, caps=("operations.record",))
            body = {"code": "ANYTHING", "phone": "0544444444", "invoice_minor": -999999}
            return await check_adversarial_input_never_crashes(
                method="POST", url=f"{svc.base_url}/api/v1/till/referral/register",
                json_body=body, headers=headers)

    result = run(_go())
    assert result.ok, result.detail


def test_a_wildly_out_of_range_discount_percent_never_crashes_the_affiliate_add_route():
    async def _go():
        async with spawn() as svc:
            headers = auth_header(tenant=TENANT_A, caps=("operations.manage",))
            body = {**AFFILIATE_BODY, "discount_percent": 999999999}
            return await check_adversarial_input_never_crashes(
                method="POST", url=f"{svc.base_url}/api/v1/affiliates",
                json_body=body, headers=headers)

    result = run(_go())
    assert result.ok, result.detail


# ── cross-tenant isolation: the same URL, two tenants' own real tokens ───────────────────────────
def test_tenant_b_can_never_see_tenant_as_affiliate_through_the_real_route():
    async def _go():
        async with spawn() as svc:
            owner_a = auth_header(tenant=TENANT_A, caps=("operations.manage",))
            body = {**AFFILIATE_BODY, "code": "CHKISO1"}
            async with httpx.AsyncClient() as client:
                created = await client.post(f"{svc.base_url}/api/v1/affiliates",
                                            json=body, headers=owner_a, timeout=10.0)
            affiliate_id = created.json()["id"]

            url = f"{svc.base_url}/api/v1/affiliates/{affiliate_id}"
            headers_a = auth_header(tenant=TENANT_A, caps=("operations.affiliates_read",))
            headers_b = auth_header(tenant=TENANT_B, caps=("operations.affiliates_read",))
            return await check_cross_tenant_isolation(
                method="GET", url=url, tenant_a_headers=headers_a, tenant_b_headers=headers_b)

    result = run(_go())
    assert result.ok, result.detail
