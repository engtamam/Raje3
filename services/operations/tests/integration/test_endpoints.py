"""The three endpoint tiers respond correctly."""
from __future__ import annotations

from tests.conftest import INTERNAL_TOKEN


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_readyz_ready_with_no_deps(client):
    r = client.get("/readyz")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"


def test_metrics_prometheus(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "text/plain" in r.headers["content-type"]


def test_internal_manifest_requires_token(client):
    assert client.get("/internal/manifest").status_code == 401
    assert client.get("/internal/health").status_code == 401


def test_internal_manifest_with_token(client):
    r = client.get("/internal/manifest", headers={"X-Internal-Token": INTERNAL_TOKEN})
    assert r.status_code == 200
    body = r.json()
    assert body["name"]
    assert "endpoints" in body and "ports" in body and "events" in body


def test_internal_rejects_wrong_token(client):
    r = client.get("/internal/health", headers={"X-Internal-Token": "wrong"})
    assert r.status_code == 401


def test_the_retention_sweep_runs_and_takes_no_tenant(client):
    """The route exists, is internal-only, and accepts NO argument.

    A sweep that took a tenant would be a deletion endpoint with a filter on it, and every service
    in the mesh holds the internal token. This one only ever does what the clock already decided —
    on an empty store, that is nothing, and it must say so rather than fail.
    """
    r = client.post("/internal/operations/retention/sweep",
                    headers={"X-Internal-Token": INTERNAL_TOKEN})
    assert r.status_code == 200, r.text
    assert r.json()["customers"] == 0
    assert client.post("/internal/operations/retention/sweep").status_code == 401
