"""ك-4: the owner's HTTP answer must never carry `stamp_error`.

`core/signup.py` still returns the field for internal callers (`api/internal.py`'s own
`seed_tenant`, which is an operator surface). The two PUBLIC routes here — `open_shop` and
`claim` — are the ones an owner's browser actually reads, and this is what strips it there.
"""
from __future__ import annotations

import asyncio
import types

from app.api.v1 import signup as signup_routes


class _FakeSvc:
    def __init__(self, out: dict) -> None:
        self._out = out

    async def open_shop(self, shop):
        return dict(self._out)

    async def claim(self, phone, code, password):
        return dict(self._out)


def _request(svc):
    container = types.SimpleNamespace(signup=svc)
    state = types.SimpleNamespace(container=container)
    return types.SimpleNamespace(app=types.SimpleNamespace(state=state))


def test_open_shop_never_forwards_stamp_error():
    svc = _FakeSvc({"tenant": "t-1", "phone": "+9665...", "services": 5,
                    "stamp_error": "unknown partner key", "data_map_error": ""})
    body = signup_routes.OpenShopIn(phone="0501234567", password="x", shop_name="ورشة",
                                    sector="tyres")
    out = asyncio.run(signup_routes.open_shop(_request(svc), body))
    assert "stamp_error" not in out
    assert out["tenant"] == "t-1"           # the rest of the answer still arrives


def test_claim_never_forwards_stamp_error():
    svc = _FakeSvc({"tenant": "t-1", "phone": "+9665...", "services": 5,
                    "stamp_error": "unknown partner key", "data_map_error": ""})
    body = signup_routes.ClaimIn(phone="0501234567", code="123456", password="x")
    out = asyncio.run(signup_routes.claim(_request(svc), body))
    assert "stamp_error" not in out
    assert out["tenant"] == "t-1"
