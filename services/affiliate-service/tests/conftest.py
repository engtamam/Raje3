"""Shared test setup.

Sets a valid environment BEFORE the app is imported so config validation passes,
then exposes a TestClient. ENV=test keeps logging silent and disables prod-only
behavior (HSTS, hidden docs).
"""
from __future__ import annotations

import os

# Must be set before any `app.*` import triggers config validation.
os.environ.setdefault("ENV", "test")
os.environ.setdefault("INTERNAL_SERVICE_TOKEN", "t" * 40)
os.environ.setdefault("BODY_LIMIT_BYTES", "2048")
os.environ.setdefault("REQUEST_TIMEOUT_MS", "30000")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


INTERNAL_TOKEN = os.environ["INTERNAL_SERVICE_TOKEN"]


@pytest.fixture(scope="session")
def client() -> TestClient:
    from app.main import app

    return TestClient(app)


@pytest.fixture(autouse=True)
def _restore_environ():
    """Undoes any `os.environ.update(...)` a test made — several integration tests build their
    own app with `os.environ.update({"TOKEN_VERIFIER_DRIVER": "hs256", ...})` (real process env,
    never cleaned up) rather than `monkeypatch.setenv`, which leaks into whichever test runs next
    in the same process. Found live: test_auth_rbac.py's own leak made
    test_ports_hardening.py::test_known_drivers_build read "hs256" off a fresh Settings() call
    that asked for nothing but the class default ("null") — passing in isolation, failing only in
    the full suite, which is the exact signature of this leak."""
    snapshot = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(snapshot)
    from app.config import get_settings

    get_settings.cache_clear()
