# =============================================================================
# error-collector — API dependencies
# -----------------------------------------------------------------------------
# require_user now performs REAL token verification (app/api/auth.py) via the
# configured TokenVerifier port; the default 'null' verifier still denies all
# (deny-by-default). Re-exported here so routes keep importing from one place.
# =============================================================================
from __future__ import annotations

from fastapi import Request

from app.api.auth import Principal, require_user
from app.container import Container

__all__ = ["get_container", "get_guard", "get_runtime_config", "require_user", "Principal"]


def get_container(request: Request) -> Container:
    """Expose the composition root's wired ports to routes."""
    return request.app.state.container


def get_guard(request: Request):
    """Expose the CWE self-guard to routes."""
    return request.app.state.cwe_guard


def get_runtime_config(request: Request):
    """The instance every reader of an operator-settable knob resolves through, so a value the
    panel accepts is a value the same instance's RUNTIME_POLICY actually offers.

    SAME FALLBACK AS `operator.py`'s OWN (local, pre-existing) copy — nothing wires
    `app.state.runtime_config` at boot in this service, so this always builds a fresh instance
    from the service's own declared RUNTIME_POLICY. Shared here so a future READ site (a sweep, a
    signal-ingest route) does not have to re-copy the construction to get the SAME policy operator.py
    itself enforces.
    """
    from app.config import Settings
    from app.core.runtime_config import RuntimeConfig
    from app.runtime_policy import RUNTIME_POLICY

    rc = getattr(request.app.state, "runtime_config", None)
    if rc is not None:
        return rc
    return RuntimeConfig(request.app.state.container.datastore, Settings, policy=RUNTIME_POLICY)
