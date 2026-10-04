"""Stage 7 of the simulator's own build plan (see ../README.md): checks — a generic pass/fail
security rule applicable to ANY HTTP action, regardless of what it does or which app it belongs
to (Schemathesis's own "checks" concept — schema/endpoint-agnostic validations — is the direct
precedent this taxonomy is named after; see the README's own research section).

Every check here takes plain (method, url, headers, json body) — never an app's own Action class
— on purpose: a check that only worked against `RegisterReferralAction`'s own shape would not be
generic at all. Any future action, in any app, gets the same four checks for free just by having
a URL and a tenant-bearing header.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from . import httpclient


@dataclass
class CheckResult:
    ok: bool
    detail: str = ""


async def _call(method: str, url: str, *, headers: dict[str, str],
                json_body: dict[str, Any] | None, timeout: float) -> httpx.Response:
    return await httpclient.request(method, url, json=json_body, headers=headers, timeout=timeout)


async def check_forged_signature_is_refused(
    *, method: str, url: str, json_body: dict[str, Any] | None, forged_headers: dict[str, str],
    timeout: float = 10.0,
) -> CheckResult:
    """A token with an honest-looking claims payload, signed with the WRONG secret. A service
    verifying signatures correctly refuses this with 401 regardless of what the claims say —
    never 200, and never any OTHER status that would suggest the signature was never actually
    checked at all."""
    r = await _call(method, url, headers=forged_headers, json_body=json_body, timeout=timeout)
    if r.status_code == 401:
        return CheckResult(ok=True, detail="forged signature correctly refused with 401")
    return CheckResult(ok=False,
                       detail=f"forged signature got {r.status_code}, expected 401: {r.text[:200]}")


async def check_wrong_capability_is_refused(
    *, method: str, url: str, json_body: dict[str, Any] | None, headers: dict[str, str],
    timeout: float = 10.0,
) -> CheckResult:
    """A VALIDLY SIGNED token — the signature check above is not what's being probed here — that
    simply does not carry the capability this route enforces. Must be refused with 403, never
    200 and never 401 (401 would mean the signature check itself is broken, a different failure
    this check must not be confused with)."""
    r = await _call(method, url, headers=headers, json_body=json_body, timeout=timeout)
    if r.status_code == 403:
        return CheckResult(ok=True, detail="missing capability correctly refused with 403")
    return CheckResult(ok=False, detail=f"missing-capability call got {r.status_code}, "
                                        f"expected 403: {r.text[:200]}")


async def check_adversarial_input_never_crashes(
    *, method: str, url: str, json_body: dict[str, Any] | None, headers: dict[str, str],
    timeout: float = 10.0,
) -> CheckResult:
    """A hostile/malformed body (an injection-shaped string, an out-of-range number, a wrong
    type) reaching a REAL route. The one thing that must never happen is a 5xx — a clean 4xx
    refusal is a correctly-behaving service; a 500 means the input reached code that assumed it
    would never see something like this."""
    r = await _call(method, url, headers=headers, json_body=json_body, timeout=timeout)
    if r.status_code >= 500:
        return CheckResult(ok=False,
                           detail=f"adversarial input caused a server error {r.status_code}: "
                                  f"{r.text[:300]}")
    return CheckResult(ok=True, detail=f"adversarial input refused cleanly with {r.status_code}")


async def check_cross_tenant_isolation(
    *, method: str, url: str, tenant_a_headers: dict[str, str], tenant_b_headers: dict[str, str],
    timeout: float = 10.0,
) -> CheckResult:
    """The SAME url, two DIFFERENT tenants' own validly-signed, correctly-capable tokens — tenant
    B must never see what tenant A can see through it. Works for any resource whose scoping comes
    from the TOKEN (`principal.tenant`), never the URL itself, which is exactly how every route
    reviewed across this whole project's own referral/affiliate feature is built."""
    ra = await httpclient.request(method, url, headers=tenant_a_headers, timeout=timeout)
    rb = await httpclient.request(method, url, headers=tenant_b_headers, timeout=timeout)
    if ra.status_code == 200 and rb.status_code == 200 and ra.text == rb.text:
        return CheckResult(ok=False, detail="tenant B's own token saw tenant A's exact data — "
                                            "cross-tenant leak")
    return CheckResult(ok=True,
                       detail=f"tenant A -> {ra.status_code}, tenant B -> {rb.status_code}, "
                              f"no leak observed")
