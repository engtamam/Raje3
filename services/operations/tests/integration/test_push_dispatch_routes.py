"""The operations cron-driven routes that had no direct route-level test before this migration —
whatsapp/health, gauges/reconcile, visits/reseam, wallet-topups/reconcile,
templates/sync-approvals, templates/publish, partners/statements/run. All seven migrated off their
own CronJobs to job-service push dispatch (2026-09-16), same as retention/sweep, the Salla pair and
the renewal-heads-up pair — see deploy/hooks/job-schedule.sh's own header."""
from __future__ import annotations

from tests.conftest import INTERNAL_TOKEN, push_headers

_ROUTES = [
    "/internal/operations/whatsapp/health",
    "/internal/operations/gauges/reconcile",
    "/internal/operations/visits/reseam",
    "/internal/operations/wallet-topups/reconcile",
    "/internal/operations/templates/sync-approvals",
    "/internal/operations/templates/publish",
    "/internal/operations/partners/statements/run",
]


def test_every_route_refuses_without_a_push_signature_even_with_a_valid_internal_token(client):
    for path in _ROUTES:
        r = client.post(path, headers={"X-Internal-Token": INTERNAL_TOKEN})
        assert r.status_code == 401, f"{path} answered {r.status_code}, expected 401"


def test_every_route_succeeds_with_a_valid_push_signature(client):
    for path in _ROUTES:
        r = client.post(path, headers={"X-Internal-Token": INTERNAL_TOKEN, **push_headers(b"")})
        assert r.status_code == 200, f"{path} answered {r.status_code}: {r.text}"


def test_every_route_refuses_a_replayed_old_signature(client):
    import time

    old_headers = push_headers(b"", ts=int(time.time()) - 600)
    for path in _ROUTES:
        r = client.post(path, headers={"X-Internal-Token": INTERNAL_TOKEN, **old_headers})
        assert r.status_code == 401, f"{path} answered {r.status_code}, expected 401"
