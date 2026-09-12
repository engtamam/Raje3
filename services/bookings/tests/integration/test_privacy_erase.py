"""The DSAR erasure route — /internal/privacy/erase — actually leaves a trace of itself.

bookings-r2-002 (QA audit, 2026-09-12): erasing a data subject's booking notes is one of the most
legally significant, irreversible actions this service ever performs, and it emitted no audit event
at all — an investigator asking "did we honour this DSAR?" would find nothing here to answer with.
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

INTERNAL = "t" * 40


def _make_app(**env_over) -> TestClient:
    from app.config import get_settings

    env = {
        "ENV": "test",
        "INTERNAL_SERVICE_TOKEN": INTERNAL,
        "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": "h" * 40,
        "TOKEN_ISSUER": "iss",
        "TOKEN_AUDIENCE": "aud",
        "RATELIMIT_MAX": "1000",
        "PII_SALT": "s" * 32,
    }
    env.update(env_over)
    os.environ.update(env)
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture
def env_guard():
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
    from app.config import get_settings

    get_settings.cache_clear()


def test_erasing_a_subject_leaves_an_audit_entry(env_guard):
    c = _make_app()
    r = c.post("/internal/privacy/erase", json={"tenant": "tnt_1", "subject": "0501234567"},
              headers={"X-Internal-Token": INTERNAL})
    assert r.status_code == 200, r.text

    sink = c.app.state.auditor._sink
    actions = [e.action for e in sink.events]
    assert "bookings.subject_erased" in actions
    entry = next(e for e in sink.events if e.action == "bookings.subject_erased")
    assert entry.tenant == "tnt_1"
    # The pseudonym, never the raw phone number, is what the resource names.
    assert "0501234567" not in entry.resource
    assert entry.resource.startswith("subject:")
