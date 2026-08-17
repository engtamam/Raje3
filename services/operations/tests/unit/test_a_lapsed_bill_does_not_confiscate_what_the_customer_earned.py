"""ب-2 — the till refused a customer's own points because the SHOP's invoice was late.

§9.9, verbatim: «أما قراءة الرصيد واستبداله فلا تُسأل عنها فوترةٌ أبداً — عميلٌ واقفٌ عند الصندوق
يحمل نقاطاً وعده بها المحل ليس طرفاً في فاتورة المحل، واشتراكٌ منقطع لا يُصادِر ما استحقّه
العميل.» `loyalty/core/loyalty.py` applies that exactly: it guards only what GROWS the debt.

THE TILL DID THE OPPOSITE, and the reasoning that put it there was half right. `feature.api` is
the programmatic link, and a redemption IS a ledger write, so gating it looks consistent with
gating a visit. But the question that check asks billing is «is this establishment entitled
today» — and a shop whose subscription has lapsed is entitled to nothing. So the guard refused
not only the shop that never bought the link but the shop that stopped paying, at the counter,
holding points the customer earned by coming back.

WHAT STAYS GATED: recording a visit through the till. That is the link itself — the thing on the
price list — and no customer's earned balance is inside it.
"""
from __future__ import annotations

import asyncio

import pytest

from app.core.licence import NullApiLicence, refuses_machine_writes


def run(coro):
    return asyncio.run(coro)


def _guarded(source: str, route_marker: str) -> bool:
    """Does the route beginning at `route_marker` ask the licence before doing its work?

    READ FROM THE SOURCE, and that is deliberate rather than lazy: the defect is the PRESENCE of a
    call, and a test that drove the route would need a billing peer, a loyalty peer and a till
    credential to observe an absence. What must never come back is the guard itself.

    A CALL, NOT A MENTION — and the first version of this helper counted the mention. The comment
    that explains why the guard is gone names the guard, so «the word appears» reported the defect
    as present in the very code that fixed it. `await …(` is the shape of doing it.
    """
    start = source.index(route_marker)
    end = source.find("\n@router", start)
    body = source[start:end if end != -1 else len(source)]
    return "await refuses_machine_writes(" in body or "await _refuses(" in body


@pytest.fixture()
def till_source() -> str:
    import app.api.v1.till as till
    import pathlib
    return pathlib.Path(till.__file__).read_text(encoding="utf-8")


def test_redeeming_is_never_asked_about_billing(till_source):
    assert not _guarded(till_source, "async def redeem_at_the_counter"), (
        "§9.9: a lapsed subscription must not confiscate what the customer earned")


def test_applying_an_offer_is_never_asked_about_billing(till_source):
    assert not _guarded(till_source, "async def apply_offer_at_the_counter"), (
        "the shop already promised him this offer in a message he is holding")


def test_recording_a_visit_through_the_till_is_still_gated(till_source):
    """The other half, and without it this change would be «remove a guard» rather than a fix."""
    assert _guarded(till_source, "async def record_from_till"), (
        "the programmatic link is the thing being sold, and a shop that never bought it must not "
        "stream visits in")


def test_an_unreachable_billing_is_not_a_refusal():
    """Unchanged, and restated here because the whole design of the licence turns on it."""
    assert run(refuses_machine_writes(NullApiLicence(False), "shop")) is True
    assert run(refuses_machine_writes(NullApiLicence(None), "shop")) is False
    assert run(refuses_machine_writes(NullApiLicence(True), "shop")) is False
