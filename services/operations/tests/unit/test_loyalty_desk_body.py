"""What the desk actually PUTS ON THE WIRE — the link a fake adapter can never test.

The route tests replace `container.loyalty_desk` with a stand-in and assert on the keyword
arguments it received. That proves the route calls the desk correctly and nothing at all about the
JSON the real desk sends: a field dropped between the signature and the request body passes every
one of those tests, which is the exact shape of د-14 one layer down.

So this test keeps the real `LoyaltyDesk` and captures the request instead.
"""
from __future__ import annotations

import asyncio
import json

from app.adapters.loyalty_desk import LoyaltyDesk


class _Captured(Exception):
    """Raised in place of a network call, carrying what would have been sent."""

    def __init__(self, body: dict):
        self.body = body
        super().__init__("captured")


def _body_of(**kw) -> dict:
    desk = LoyaltyDesk(base_url="http://loyalty.invalid", token="t" * 40)

    def _fake(path, *, body=None):
        raise _Captured(body or {})

    desk._call = _fake                                   # noqa: SLF001 — the seam under test
    try:
        asyncio.run(desk.redeem(**kw))
    except _Captured as got:
        return got.body
    raise AssertionError("the desk did not send a request")


def test_the_approver_reaches_the_wire():
    """د-14 — loyalty refuses any reward above the shop's threshold without a name, and this is the
    last place that name can be lost. A manager who signed for a redemption and a body that omits
    him are indistinguishable at the ledger: both arrive as «nobody approved this»."""
    body = _body_of(tenant="t1", subject_ref="ref_x", reward_id="rw_1",
                    idempotency_key="k1", actor="cashier", approved_by="خالد المدير")
    assert body["approved_by"] == "خالد المدير", body
    # AND IT SURVIVES ENCODING — the Arabic name is what a Saudi shop will actually type.
    assert "خالد المدير" in json.dumps(body, ensure_ascii=False)


def test_an_ordinary_redemption_sends_an_empty_approver_rather_than_omitting_it():
    """Most redemptions are below the threshold. The key is still present and empty: the service
    decides whether that is allowed, and a caller that sometimes omits a field teaches the reader
    on the other side to treat «absent» and «empty» as the same thing."""
    body = _body_of(tenant="t1", subject_ref="ref_x", reward_id="rw_1",
                    idempotency_key="k2", actor="cashier")
    assert body["approved_by"] == ""
