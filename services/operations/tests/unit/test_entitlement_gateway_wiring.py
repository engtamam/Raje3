"""`container.entitlement_gateway` was built WITHOUT `store=` for a while after
`EntitlementGateway` gained that parameter (2026-10-04, for pricing a mutual-benefit gift grant at
its own catalogue price and a group-scope discount against its real package members) — a real,
silent production gap this file guards against: without `store`, every gift/group-scope candidate
would have priced as unpriceable and always lost the real-value comparison to a lesser offer, with
nothing red anywhere to say so.
"""
from __future__ import annotations

from app.config import Settings
from app.container import build_container


def _settings() -> Settings:
    return Settings(_env_file=None, INTERNAL_SERVICE_TOKEN="t" * 40)


def test_the_production_entitlement_gateway_is_wired_with_a_store():
    c = build_container(_settings())
    assert c.entitlement_gateway._store is not None, (
        "EntitlementGateway built with no store — a mutual-benefit gift grant or group-scope "
        "discount can never be priced in production, and silently loses every real-value "
        "comparison instead")
