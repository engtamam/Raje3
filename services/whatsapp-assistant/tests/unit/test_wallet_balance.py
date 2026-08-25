"""HttpWalletBalance — the authorization-HOLD pattern (reserve/confirm/release) against
wallet-service's real internal routes, and the pure ceiling-sizing arithmetic."""
from __future__ import annotations

import asyncio
import json
from unittest.mock import patch

from app.core.wallet_balance import (HttpWalletBalance, NullWalletBalance,
                                     estimated_hold_halalas, new_reserve_source)


def run(c):
    return asyncio.run(c)


def client():
    return HttpWalletBalance(
        url="http://wallet-service:8000", reserve_path="/internal/wallet/reserve",
        confirm_path="/internal/wallet/confirm", release_path="/internal/wallet/release",
        token="t", timeout=8)


class _Resp:
    def __init__(self, payload, status=200):
        self._p = json.dumps(payload).encode()
        self.status = status

    def read(self):
        return self._p

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_estimated_hold_halalas_prices_the_token_ceiling_plus_the_fixed_margin():
    # 4000 tokens at 50 halalas/1k = 200, plus a 100-halala (1 SAR) margin = 300.
    assert estimated_hold_halalas(
        estimated_tokens=4000, halalas_per_1k_tokens=50, safety_margin_halalas=100) == 300


def test_estimated_hold_halalas_rounds_the_token_component_up_never_down():
    # 1500 tokens at 1 halala/1k = 1.5 -> ceil to 2, plus margin.
    assert estimated_hold_halalas(
        estimated_tokens=1500, halalas_per_1k_tokens=1, safety_margin_halalas=0) == 2


def test_estimated_hold_halalas_with_zero_rate_is_the_margin_alone():
    # No pricing decision made yet (rate=0) still holds the fixed margin, never zero.
    assert estimated_hold_halalas(
        estimated_tokens=4000, halalas_per_1k_tokens=0, safety_margin_halalas=100) == 100


def test_new_reserve_source_differs_per_call_for_the_same_conversation():
    a = new_reserve_source("t1|sub1")
    b = new_reserve_source("t1|sub1")
    assert a != b
    assert a.startswith("whatsapp_assistant:t1|sub1:")


def test_reserve_posts_net_source_and_reason_and_returns_the_hold_id():
    c = client()
    seen: dict = {}

    def _urlopen(req, timeout=0):
        seen["url"] = req.full_url
        seen["header"] = req.get_header("X-internal-token")
        seen["body"] = json.loads(req.data or b"{}")
        return _Resp({"hold_id": "hld_123", "expires_at": 999})

    with patch("urllib.request.urlopen", _urlopen):
        hold_id = run(c.reserve(tenant="shop1", amount_halalas=300, source="src1"))

    assert seen["url"] == "http://wallet-service:8000/internal/wallet/reserve"
    assert seen["header"] == "t"
    assert seen["body"] == {"tenant": "shop1", "net": 300, "source": "src1",
                            "reason": "whatsapp_assistant.llm_turn"}
    assert hold_id == "hld_123"


def test_reserve_returns_none_on_a_402_insufficient_funds():
    import urllib.error

    c = client()

    def _urlopen(req, timeout=0):
        raise urllib.error.HTTPError(req.full_url, 402, "INSUFFICIENT_FUNDS", {}, None)

    with patch("urllib.request.urlopen", _urlopen):
        hold_id = run(c.reserve(tenant="shop1", amount_halalas=300, source="src1"))
    assert hold_id is None


def test_reserve_fails_closed_when_the_peer_is_unreachable():
    """THE hard rule: an uncertain outcome must never be treated as a successful reservation —
    this is the one peer in this service that fails CLOSED, not open (see wallet_balance.py's
    module docstring)."""
    import urllib.error

    c = client()

    def _urlopen(req, timeout=0):
        raise urllib.error.URLError("connection refused")

    with patch("urllib.request.urlopen", _urlopen):
        hold_id = run(c.reserve(tenant="shop1", amount_halalas=300, source="src1"))
    assert hold_id is None


def test_confirm_and_release_post_the_hold_id_with_the_internal_token():
    c = client()
    seen: list = []

    def _urlopen(req, timeout=0):
        seen.append({"url": req.full_url, "body": json.loads(req.data or b"{}")})
        return _Resp({"ok": True})

    with patch("urllib.request.urlopen", _urlopen):
        run(c.confirm("hld_123"))
        run(c.release("hld_456"))

    assert seen[0]["url"] == "http://wallet-service:8000/internal/wallet/confirm"
    assert seen[0]["body"] == {"hold_id": "hld_123"}
    assert seen[1]["url"] == "http://wallet-service:8000/internal/wallet/release"
    assert seen[1]["body"] == {"hold_id": "hld_456"}


async def test_null_wallet_balance_always_reserves_and_never_blocks():
    w = NullWalletBalance()
    hold_id = await w.reserve(tenant="shop1", amount_halalas=999999, source="anything")
    assert hold_id is not None
    await w.confirm(hold_id)     # must not raise
    await w.release(hold_id)     # must not raise
