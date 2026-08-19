"""The billing-plans boot guard: a deployment that cannot list or read subscriptions sells nothing.

WHAT WENT WRONG WITHOUT THIS. `BILLING_PLANS_DRIVER` defaults to "null" — right for a service
under test, silent poison in production. Every path around it (`BILLING_SUBSCRIPTIONS_PATH`,
`BILLING_PLANS_PATH`, `BILLING_SUBSCRIBE_PATH`) was set on a real deployment and the driver flag
itself was not, so `build_plans()` returned `NullPlans()` and stayed there: no plan could be
listed, no purchase could be made, and `/api/v1/subscription/apps` answered `base: null` for
every shop forever, with no error and no log line pointing at why.
"""
from __future__ import annotations

import pytest

from app.config import Settings
from app.container import build_container

_OK = {"INTERNAL_SERVICE_TOKEN": "x" * 40}


def test_dev_defaults_boot_with_zero_infrastructure():
    Settings(ENV="test", **_OK).assert_billing_plans_config_ok()


def test_production_refuses_the_default_null_driver():
    with pytest.raises(ValueError, match="not 'http'"):
        Settings(ENV="production", **_OK).assert_billing_plans_config_ok()


def test_production_refuses_http_with_a_path_missing():
    with pytest.raises(ValueError, match="configured and inert"):
        Settings(ENV="production", BILLING_PLANS_DRIVER="http",
                 BILLING_SERVICE_URL="", **_OK).assert_billing_plans_config_ok()


def test_production_happy_config_passes():
    Settings(ENV="production", BILLING_PLANS_DRIVER="http",
             BILLING_SERVICE_URL="http://billing-service:8000", **_OK).assert_billing_plans_config_ok()


def test_the_configured_driver_is_what_gets_wired():
    c = build_container(Settings(BILLING_PLANS_DRIVER="http",
                                 BILLING_SERVICE_URL="http://billing-service:8000", **_OK))
    assert c.billing_plans.driver == "http"


def test_the_null_driver_answers_none_rather_than_an_empty_list():
    """`None` is «could not read»; a caller that treats it as «holds nothing» would let a second
    base subscription through during an outage — see subscribe.py's own note on the method."""
    import asyncio

    c = build_container(Settings(**_OK))
    assert asyncio.run(c.billing_plans.subscriptions("t1")) is None
