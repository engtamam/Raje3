"""X-Internal-Token enforcement (constant-time compare) and malformed-payload handling on this
service's own internal HTTP surface.
"""
from tests.conftest import INTERNAL_TOKEN


def test_tick_without_internal_token_is_refused(client):
    resp = client.post("/internal/whatsapp_assistant/tick", json={"tenant": "t1"})
    assert resp.status_code == 401


def test_tick_with_wrong_internal_token_is_refused(client):
    resp = client.post("/internal/whatsapp_assistant/tick", json={"tenant": "t1"},
                       headers={"X-Internal-Token": "wrong" * 10})
    assert resp.status_code == 401


def test_tick_with_malformed_json_body_does_not_crash(client):
    resp = client.post("/internal/whatsapp_assistant/tick", data=b"{not json",
                       headers={"X-Internal-Token": INTERNAL_TOKEN,
                               "Content-Type": "application/json"})
    # Never a 500 — a malformed body is handled and answered, not a stack trace.
    assert resp.status_code != 500


def test_tick_with_no_tenant_is_rejected_cleanly_not_crashed(client):
    resp = client.post("/internal/whatsapp_assistant/tick", json={},
                       headers={"X-Internal-Token": INTERNAL_TOKEN})
    assert resp.status_code != 500
    assert resp.json().get("error") == "tenant is required"


def test_manifest_requires_internal_token(client):
    resp = client.get("/internal/manifest")
    assert resp.status_code == 401
