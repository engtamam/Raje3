"""build_container's own assembly order for the Phase 5 Flow booking channel — found live,
2026-09-08, while wiring loyalty-in-booking: `container.flow_booking_provider` used to be built
BEFORE `container.service_catalog`/`customer_lookup`/`points_summary`/`branch_directory` were
assigned, so FlowBookingBackend always received the container's unset default (None) for all four
instead of the real, already-built instances — `options(dimension="service")` would have raised
the first time a real Flow request ever reached it. WHATSAPP_FLOW_BOOKING_ENABLED has never been
on in a real deployment, so this was never caught by a live request; only by actually building the
container with the flag on and inspecting what landed where.
"""
from __future__ import annotations

import os

import pytest


def _make_settings(**env_over):
    from app.config import get_settings

    env = {
        "ENV": "test",
        "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": "h" * 40,
        "TOKEN_ISSUER": "iss",
        "TOKEN_AUDIENCE": "aud",
        "RATELIMIT_MAX": "1000",
        "SECRETS_KEK": "unit-test-kek-not-a-real-key",
        "PII_SALT": "s" * 32,
        "BOOKING_PROVIDER_DRIVER": "real",
        "OPERATIONS_SERVICE_URL": "http://operations:8000",
        "BOOKINGS_SERVICE_URL": "http://bookings:8000",
        "LOYALTY_SERVICE_URL": "http://loyalty:8000",
        "WHATSAPP_FLOW_BOOKING_ENABLED": "true",
    }
    env.update(env_over)
    os.environ.update(env)
    get_settings.cache_clear()
    return get_settings()


@pytest.fixture
def env_guard():
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
    from app.config import get_settings
    get_settings.cache_clear()


def test_the_flow_booking_provider_receives_the_containers_real_catalog_instance(env_guard):
    from app.container import build_container

    settings = _make_settings()
    container = build_container(settings)

    assert container.flow_booking_provider is not None
    # THE ACTUAL REGRESSION — this used to be None (the container's own unset default) rather
    # than the exact object `container.service_catalog` holds.
    assert container.flow_booking_provider._catalog is container.service_catalog
    assert container.service_catalog is not None


def test_the_flow_booking_provider_receives_the_containers_real_branch_directory(env_guard):
    from app.container import build_container

    settings = _make_settings()
    container = build_container(settings)

    assert container.flow_booking_provider._branches is container.branch_directory
    assert container.branch_directory is not None


def test_the_flow_booking_provider_receives_the_containers_real_loyalty_peers(env_guard):
    """LOYALTY-IN-BOOKING (this session's own addition) — the reward step's two dependencies."""
    from app.container import build_container

    settings = _make_settings()
    container = build_container(settings)

    assert container.flow_booking_provider._customer_lookup is container.customer_lookup
    assert container.flow_booking_provider._points_summary is container.points_summary
    assert container.customer_lookup is not None
    assert container.points_summary is not None


def test_disabled_by_default_builds_no_flow_booking_provider(env_guard):
    from app.container import build_container

    settings = _make_settings(WHATSAPP_FLOW_BOOKING_ENABLED="false")
    container = build_container(settings)

    assert container.flow_booking_provider is None


def test_enabling_it_without_the_real_driver_fails_fast(env_guard):
    from app.container import build_container

    settings = _make_settings(BOOKING_PROVIDER_DRIVER="config")
    with pytest.raises(ValueError, match="BOOKING_PROVIDER_DRIVER"):
        build_container(settings)
