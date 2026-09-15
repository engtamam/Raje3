"""POST /internal/tickets/escalation-sweep — migrated off its own CronJob to job-service push
dispatch (2026-09-16), same as commissions/sweep and leads/tick. Now requires a valid, unreplayed
push signature on top of the shared internal token."""
from __future__ import annotations

from tests.conftest import INTERNAL_TOKEN, push_headers


def test_escalation_sweep_refuses_without_a_push_signature_even_with_a_valid_internal_token(client):
    resp = client.post("/internal/tickets/escalation-sweep",
                       headers={"X-Internal-Token": INTERNAL_TOKEN})
    assert resp.status_code == 401


def test_escalation_sweep_with_a_valid_push_signature_succeeds(client):
    resp = client.post("/internal/tickets/escalation-sweep",
                       headers={"X-Internal-Token": INTERNAL_TOKEN, **push_headers(b"")})
    assert resp.status_code == 200, resp.text


def test_escalation_sweep_with_a_replayed_old_signature_is_refused(client):
    import time

    old_headers = push_headers(b"", ts=int(time.time()) - 600)
    resp = client.post("/internal/tickets/escalation-sweep",
                       headers={"X-Internal-Token": INTERNAL_TOKEN, **old_headers})
    assert resp.status_code == 401
