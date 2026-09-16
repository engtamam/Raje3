"""`feature.api` is CLOSED by product decision, 2026-09-16 — see core/licence.py's own docstring
for the reasoning. `build_api_licence` must refuse everyone while `API_LINK_ENABLED` is off (the
default), and never touch billing at all while it does — and must go back to asking billing the
moment the flag is flipped on, with no other code change.
"""
from __future__ import annotations

import asyncio
import types

from app.core.licence import ClosedApiLicence, HttpApiLicence, NullApiLicence, build_api_licence


def _settings(**over) -> types.SimpleNamespace:
    base = {"API_LINK_ENABLED": False, "BILLING_SERVICE_URL": "", "BILLING_CHECK_PATH": ""}
    base.update(over)
    return types.SimpleNamespace(**base)


def test_the_door_is_closed_by_default_regardless_of_billing_config():
    licence = build_api_licence(_settings(
        BILLING_SERVICE_URL="http://billing", BILLING_CHECK_PATH="/check"))
    assert isinstance(licence, ClosedApiLicence)
    assert asyncio.run(licence.allowed("t_1")) is False


def test_a_closed_licence_never_says_it_could_not_ask():
    """A closed door answers a definite no, never «تعذّر السؤال» — a real billing outage is the
    only case allowed to say that, and this is not one."""
    licence = ClosedApiLicence()
    assert asyncio.run(licence.allowed("")) is False


def test_flipping_the_flag_restores_the_billing_check():
    licence = build_api_licence(_settings(
        API_LINK_ENABLED=True, BILLING_SERVICE_URL="http://billing", BILLING_CHECK_PATH="/check"))
    assert isinstance(licence, HttpApiLicence)


def test_flipping_the_flag_with_no_billing_wired_falls_back_to_null():
    licence = build_api_licence(_settings(API_LINK_ENABLED=True))
    assert isinstance(licence, NullApiLicence)
