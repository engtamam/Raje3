"""Audit config and the boot guard: a service that cannot record what it does must not pretend to.

The guard exists because of a real, months-long failure: audit-service ran with a complete ingest
endpoint and no callers. The chain verified perfectly and held nothing. No test went red, no alert
fired, and the control existed only on paper. Fail-closed at boot is what makes that state
impossible to reach silently.
"""
from __future__ import annotations

import pytest

from app.config import Settings
from app.container import build_container
from app.ports.errors import ConfigError

_OK = {"INTERNAL_SERVICE_TOKEN": "x" * 40}


def test_url_is_base_plus_the_configured_ingest_path():
    s = Settings(AUDIT_SERVICE_URL="http://audit-service:8000/", **_OK)
    assert s.audit_ingest_url == "http://audit-service:8000/internal/audit"


def test_the_ingest_path_is_config_not_an_assumption():
    # /internal/audit is OUR convention. Another platform's audit endpoint is its own.
    s = Settings(AUDIT_SERVICE_URL="https://siem.acme", AUDIT_INGEST_PATH="/v2/events", **_OK)
    assert s.audit_ingest_url == "https://siem.acme/v2/events"


def test_no_url_yields_no_url_rather_than_a_guess():
    # A guessed host would send the audit trail somewhere the operator cannot read, while every
    # call still looked successful.
    assert Settings(**_OK).audit_ingest_url == ""


def test_dev_defaults_boot_with_zero_infrastructure():
    Settings(ENV="test", **_OK).assert_audit_config_ok()


def test_production_refuses_a_sink_that_records_nothing():
    with pytest.raises(ValueError, match="never recorded"):
        Settings(ENV="production", AUDIT_SINK_DRIVER="null", **_OK).assert_audit_config_ok()


def test_production_refuses_http_with_nowhere_to_send():
    # Every event would fail and the chain would stay empty while the service looked healthy.
    with pytest.raises(ValueError, match="AUDIT_SERVICE_URL is empty"):
        Settings(ENV="production", AUDIT_SINK_DRIVER="http", **_OK).assert_audit_config_ok()


def test_a_non_http_audit_url_is_refused():
    with pytest.raises(ValueError, match="http"):
        Settings(ENV="production", AUDIT_SINK_DRIVER="http",
                 AUDIT_SERVICE_URL="ftp://audit", **_OK).assert_audit_config_ok()


def test_production_happy_config_passes():
    Settings(ENV="production", AUDIT_SINK_DRIVER="http",
             AUDIT_SERVICE_URL="https://audit-service:8000", **_OK).assert_audit_config_ok()


def test_a_plain_http_audit_url_is_accepted_in_production():
    # NOT REFUSED — see config.py's own assert_audit_config_ok docstring: audit-service has no
    # TLS termination on its cluster-internal port, same as every other service's own
    # AUDIT_SERVICE_URL on this fleet, so a hard refusal here crash-looped this service in
    # production the moment it shipped (found live, 2026-09-28) with no https:// value that could
    # ever have satisfied it.
    Settings(ENV="production", AUDIT_SINK_DRIVER="http",
             AUDIT_SERVICE_URL="http://audit-service:8000", **_OK).assert_audit_config_ok()


# ── container wiring ──────────────────────────────────────────────────────────
# TWO DRIVERS, NOT THREE. There is no eventbus sink in this service (see app/container.py):
# its receipt means PUBLISHED rather than RECORDED, and every action here is `critical` —
# refused unless it can be proved recorded. That sink would turn the fail-closed rule into a
# fail-open one without changing a line of route code.
@pytest.mark.parametrize("driver", ["null", "http"])
def test_the_configured_driver_is_what_gets_wired(driver):
    c = build_container(Settings(AUDIT_SINK_DRIVER=driver,
                                 AUDIT_SERVICE_URL="http://audit-service:8000", **_OK))
    assert c.audit_sink.driver == driver
    assert {"port": "audit_sink", "driver": driver} in c.describe()


def test_an_unknown_driver_fails_at_boot():
    with pytest.raises(ConfigError, match="audit_sink"):
        build_container(Settings(AUDIT_SINK_DRIVER="carrier-pigeon", **_OK))
