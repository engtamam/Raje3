"""The offer is recognised, not quoted — which is why the coupon code could be deleted at all.

WHAT THIS PINS. `Operations.apply_offer` asks `core/entitlements.py::EntitlementGateway` (built
from an injected chooser and, since the mutual-benefit pass, an injected referral engine too
— see that module's own docstring) WHICH entitlement this visit applies, from the tenant, the
pseudonym/phone and the services on the visit. Nothing a person reads aloud, nothing a person
types, and nothing that can be misheard across a counter.

WHY IT IS ASSERTED HERE. A code printed in the message was, until now, the second way to find the
same row — and the argument for deleting it is exactly this method: the first way was already
complete. If a code ever creeps back into this call, that argument stops being true and the
deletion beside it becomes a regression rather than a simplification.

THE TWO REAL DOORS ARE UNTOUCHED and stay tested where they live: `api/v1/field.py`'s `apply_offer`
(the employee's screen) and `api/v1/till.py`'s `apply_offer_at_the_counter` (an integrated
register) — see tests/integration/test_till_offer.py and test_offers_redeemed.py.
"""
from __future__ import annotations

import asyncio
import inspect

from app.core.operations import Operations


def run(c):
    return asyncio.run(c)


def test_the_chooser_is_asked_by_identity_and_scope_and_never_by_a_code():
    """The whole signature, read off the source rather than off a memory of it."""
    src = inspect.getsource(Operations.apply_offer)
    assert "gateway.choose(tenant=tenant, subject_ref=subject_ref" in src
    assert "service_ids=list(v.service_ids)" in src
    for gone in ("code", "coupon"):
        assert gone not in src.lower(), (
            f"«{gone}» in the automatic recognition path — the offer is found from what the shop "
            f"sent and who is standing there, not from a string somebody reads out")


def test_the_method_takes_no_code_argument_from_any_caller():
    params = set(inspect.signature(Operations.apply_offer).parameters)
    assert params == {"self", "tenant", "visit_id", "subject_ref"}


def test_no_source_at_all_refuses_rather_than_guessing():
    """A missing peer must not grant a discount because a URL was blank — asserted because the
    coupon deletion removed the only OTHER evidence an offer ever existed. Now two conditions
    would let this through with nothing wired at all (no gateway installed AND no legacy chooser
    installed) — both are pinned, since either alone silently guessing would be the same bug."""
    src = inspect.getsource(Operations.apply_offer)
    assert "if gateway is None:" in src
    assert "if self._choose_offer is None:" in src
    assert 'raise OperationError("تعذّر التحقق من العروض الآن")' in src
