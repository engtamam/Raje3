"""Every user-facing route this service actually serves is declared in the manifest.

THE HOLE THIS CLOSES, FOUND THE HARD WAY. POST /api/v1/subscription had been live and undeclared
since the day it was written. The completeness gate that should have caught it reads DECLARED
ACTIONS against the MANIFEST — so a route present in neither is a route nothing checks. It surfaced
only because two new routes were declared beside it and the guard followed the trail.

The manifest is what the platform's route table, the gateway and every reviewer read. A route
missing from it is a surface nobody audits: not in the capability review, not in the action
coverage, not in the security posture. It works, which is the problem.

So this compares the manifest against the app itself rather than against another document.
"""
from __future__ import annotations

from app.config import get_settings
from app.main import app
from app.manifest import build_manifest


def _declared(user_facing_only: bool = True) -> set[tuple[str, str]]:
    """(METHOD, path) from the manifest, with the chart's {} placeholders normalised away.

    THE MANIFEST IS DELIBERATELY WIDER THAN THIS TEST. It declares the internal routes too, because
    a route table that omits the service-to-service surface hides exactly the paths that carry a
    shared token — and that is right. What this test compares is the subset a PERSON can reach, so
    the same filter is applied to both sides rather than only to one. Applying it to one side was
    this test's own first bug: it reported nineteen internal routes as phantoms.
    """
    out = set()
    for e in build_manifest(get_settings()).get("endpoints", []):
        path = e["path"].replace("{}", "*")
        if user_facing_only and not _in_scope(path):
            continue
        out.add((e.get("method", "GET").upper(), path))
    return out


def _in_scope(path: str) -> bool:
    """The surface a person reaches with a capability. /internal/* carries a shared service token
    rather than a capability; /metrics and the docs belong to the framework."""
    if path.startswith("/internal/"):
        return False
    if path in ("/metrics", "/docs", "/redoc", "/openapi.json"):
        return False
    return path.startswith("/api/v1/") or path in ("/healthz", "/readyz")


def _served() -> set[tuple[str, str]]:
    """(METHOD, path) actually registered on the app, with FastAPI's {name} normalised the same."""
    import re

    out = set()
    for route in app.routes:
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", set()) or set()
        # INTERNAL AND INFRASTRUCTURE ROUTES ARE NOT IN SCOPE. /internal/* is service-to-service and
        # carries a shared token rather than a capability; /metrics, /docs and the OpenAPI schema
        # are the framework's. What this test is about is the surface a PERSON can reach.
        norm = re.sub(r"\{[^}]+\}", "*", path)
        if not _in_scope(norm):
            continue
        for m in methods:
            if m in ("HEAD", "OPTIONS"):
                continue
            out.add((m.upper(), norm))
    return out


def test_every_served_route_is_declared_in_the_manifest():
    missing = sorted(_served() - _declared())
    assert not missing, (
        "these routes are live and absent from the manifest, so nothing audits them — "
        "not the capability review, not the action coverage, not the route table: "
        + ", ".join(f"{m} {p}" for m, p in missing))


def test_the_manifest_declares_no_route_that_does_not_exist():
    """The other direction, and it fails more quietly: a declared route that 404s puts a button in
    the console that does nothing."""
    phantom = sorted(_declared() - _served())
    assert not phantom, (
        "the manifest declares routes this service does not serve — the console renders a button "
        "that 404s: " + ", ".join(f"{m} {p}" for m, p in phantom))
