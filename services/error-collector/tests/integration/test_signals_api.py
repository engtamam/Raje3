"""The four signal routes, driven over HTTP with the real request models in the way.

THE RULE THAT PUT THIS FILE HERE (playbook §4.20): for every rule enforced in the core, one test
must reach it through the HTTP route. A bound that lives in `SignalIn` and is dropped by a route's
own model is a 200 that stores nothing — enforced in the core, bypassed at the door.
"""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

SECRET = "h" * 40
ISS = "iss"
AUD = "aud"
INTERNAL = "t" * 40


def _make_app(**env_over) -> TestClient:
    from app.config import get_settings

    env = {
        "ENV": "test",
        "INTERNAL_SERVICE_TOKEN": INTERNAL,
        "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": SECRET,
        "TOKEN_ISSUER": ISS,
        "TOKEN_AUDIENCE": AUD,
        "RATELIMIT_MAX": "1000",
        # The blobs are capped at 16 KB by the model; the body-limit middleware must be wider than
        # that or it would refuse first and the model's own bound would never be reached — a rule
        # enforced by the wrong layer is a rule nobody can test.
        "BODY_LIMIT_BYTES": "262144",
        "PII_SALT": "p" * 40,
    }
    env.update(env_over)
    os.environ.update(env)
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture(scope="module")
def env():
    from app.config import get_settings

    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


@pytest.fixture(scope="module")
def client(env) -> TestClient:
    return _make_app()


def _token(caps=None, **over) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    claims = {"sub": "u1", "iss": ISS, "aud": AUD,
              "exp": now + dt.timedelta(minutes=5), "iat": now}
    if caps is not None:
        claims["caps"] = caps
    claims.update(over)
    return jwt.encode(claims, SECRET, algorithm="HS256")


def _auth(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


def _internal(tok: str = INTERNAL) -> dict:
    return {"X-Internal-Token": tok}


READER = None


def _reader() -> dict:
    return _auth(_token(caps=["platform.observability"], tenant="t1"))


# ── the shapes the two real callers actually send ─────────────────────────────────────────────
# These are the payloads deploy/k3s/fluent-bit.yaml's lua filter and
# apps/console/src/lib/errorReporter.ts each build. Written out in full rather than generated, so
# a change on either side that breaks the contract fails HERE and not in production.
FLUENT_BIT_SHAPED = {
    "source": "server_log",
    "severity": "error",
    "service": "loyalty",
    "message": "connection refused talking to postgres",
    "occurred_at": 1_760_000_000,
    "status_code": 500,
    "request_id": "req-abc123",
    "detail": {"logger": "app.core.ledger", "exception": "ConnectionRefusedError",
               "stack": "Traceback (most recent call last): ..."},
    "context": {"pod": "loyalty-6d4f-xyz", "namespace": "base-services", "node": "node-1",
                "container": "loyalty"},
}

BROWSER_SHAPED = {
    "source": "browser",
    "severity": "error",
    "service": "console",
    "message": "TypeError: Cannot read properties of undefined (reading 'map')",
    "detail": {"stack": "at Board (Board.tsx:44)\\n at renderWithHooks (react-dom.js:1)",
               "kind": "onerror"},
    "context": {"url": "https://admin.raje3.sa/bookings", "user_agent": "Mozilla/5.0",
                "tenant": "t1"},
}


# ── /internal/signals/ingest ──────────────────────────────────────────────────────────────────
def test_ingest_requires_the_internal_token(client):
    assert client.post("/internal/signals/ingest", json=FLUENT_BIT_SHAPED).status_code == 401
    r = client.post("/internal/signals/ingest", json=FLUENT_BIT_SHAPED,
                    headers=_internal("wrong-token"))
    assert r.status_code == 401
    # And a session JWT is not a substitute — this door is for infrastructure.
    r = client.post("/internal/signals/ingest", json=FLUENT_BIT_SHAPED, headers=_reader())
    assert r.status_code == 401


def test_ingest_accepts_a_fluent_bit_shaped_record(client):
    r = client.post("/internal/signals/ingest", json=FLUENT_BIT_SHAPED, headers=_internal())
    assert r.status_code == 200, r.text
    assert r.json() == {"stored": 1, "ids": [r.json()["ids"][0]]}


def test_ingest_accepts_the_batch_a_log_shipper_actually_flushes(client):
    """Fluent Bit's http output sends a JSON ARRAY, not an object, and that is not configurable
    away. A route declaring a single object answers 422 to every flush — with the DaemonSet
    Running, the collector Ready, and the screen empty in the way «no errors» looks."""
    batch = [dict(FLUENT_BIT_SHAPED, message="batched-a"),
             dict(FLUENT_BIT_SHAPED, message="batched-b", severity="warning")]
    r = client.post("/internal/signals/ingest", json=batch, headers=_internal())
    assert r.status_code == 200, r.text
    assert r.json()["stored"] == 2 and len(r.json()["ids"]) == 2

    # AND ONE BAD ELEMENT REFUSES THE WHOLE FLUSH rather than storing half of it silently.
    bad = [dict(FLUENT_BIT_SHAPED), {"log": "raw", "time": "now"}]
    assert client.post("/internal/signals/ingest", json=bad,
                       headers=_internal()).status_code == 422


def test_ingest_refuses_a_raw_unshaped_record(client):
    """THE REASON THE FLUENT BIT CONFIG HAS FILTERS AT ALL. A raw tail record — `log`, `time`,
    `kubernetes` — is not this contract, and it is refused at the door rather than stored as a row
    no screen can render."""
    raw = {"log": "something exploded", "time": "2026-09-08T00:00:00Z",
           "kubernetes": {"pod_name": "loyalty-1"}}
    assert client.post("/internal/signals/ingest", json=raw,
                       headers=_internal()).status_code == 422


def test_ingest_refuses_an_oversized_blob_through_the_route(client):
    payload = dict(FLUENT_BIT_SHAPED, detail={"stack": "x" * 40_000})
    assert client.post("/internal/signals/ingest", json=payload,
                       headers=_internal()).status_code == 422


# ── /api/v1/signals/report ────────────────────────────────────────────────────────────────────
def test_report_needs_a_session_but_no_special_capability(client):
    assert client.post("/api/v1/signals/report", json=BROWSER_SHAPED).status_code == 401
    # An ordinary user, with no caps at all.
    r = client.post("/api/v1/signals/report", json=BROWSER_SHAPED,
                    headers=_auth(_token(caps=[], tenant="t1")))
    assert r.status_code == 200, r.text


def test_report_refuses_an_oversized_blob_through_the_route(client):
    payload = dict(BROWSER_SHAPED, detail={"stack": "x" * 40_000})
    r = client.post("/api/v1/signals/report", json=payload,
                    headers=_auth(_token(caps=[], tenant="t1")))
    assert r.status_code == 422


# ── /api/v1/signals ───────────────────────────────────────────────────────────────────────────
def test_reading_the_stream_needs_the_platform_capability(client):
    assert client.get("/api/v1/signals").status_code == 401
    assert client.get("/api/v1/signals",
                      headers=_auth(_token(caps=[], tenant="t1"))).status_code == 403
    assert client.get("/api/v1/signals",
                      headers=_auth(_token(caps=["loyalty.read"]))).status_code == 403
    assert client.get("/api/v1/signals", headers=_reader()).status_code == 200


def test_both_doors_land_in_the_same_table_and_are_read_by_one_query(client):
    """THE END-TO-END SANITY CHECK. A Fluent-Bit-shaped POST and a browser-shaped POST, then one
    GET that returns both — which is the entire product claim of a single `signals` table."""
    marker = "same-table-check-9f2a"
    client.post("/internal/signals/ingest",
                json=dict(FLUENT_BIT_SHAPED, message=f"{marker} from a pod"),
                headers=_internal())
    client.post("/api/v1/signals/report",
                json=dict(BROWSER_SHAPED, message=f"{marker} from a browser"),
                headers=_auth(_token(caps=[], tenant="t1")))

    body = client.get("/api/v1/signals", params={"q": marker, "limit": 50},
                      headers=_reader()).json()
    rows = body["signals"]
    assert len(rows) == 2
    assert {r["source"] for r in rows} == {"server_log", "browser"}
    assert {r["service"] for r in rows} == {"loyalty", "console"}

    by_source = {r["source"]: r for r in rows}
    pod = by_source["server_log"]
    assert pod["status_code"] == 500
    assert pod["request_id"] == "req-abc123"
    assert pod["occurred_at"] == 1_760_000_000
    assert pod["context"]["namespace"] == "base-services"
    assert pod["detail"]["exception"] == "ConnectionRefusedError"

    browser = by_source["browser"]
    assert browser["status_code"] is None          # null stays null, never 0
    assert browser["context"]["url"].endswith("/bookings")
    # The browser's own clock was not sent, so occurred_at fell back to arrival — never to 1970.
    assert browser["occurred_at"] == browser["received_at"]

    # NEITHER ROW CARRIES ATTRIBUTION OUTWARD. The reporter's pseudonym is stored (it is what an
    # erasure finds the row by) and is not part of what the screen reads.
    assert "subject_ref" not in browser and "tenant" not in browser


def test_a_search_narrowed_to_one_customers_pseudonym_excludes_everyone_elses_errors(client):
    """The admin panel's «أخطاء هذا العميل» search: resolve phone -> subject_ref elsewhere
    (operations), then filter here by (tenant, subject_ref) — never subject_ref alone, see
    SignalStore.browse's own note on why."""
    from app.config import get_settings
    from app.core.pii import subject_ref as _sref

    marker = "customer-scoped-check-7a1b"
    # Customer A's own browser report — the route computes subject_ref from the caller's token,
    # exactly as a real customer-facing report would.
    client.post("/api/v1/signals/report",
                json=dict(BROWSER_SHAPED, message=f"{marker} customer A"),
                headers=_auth(_token(caps=[], sub="alice@x.com", tenant="tnt_a")))
    # A different customer, SAME tenant — must not leak into A's filtered view.
    client.post("/api/v1/signals/report",
                json=dict(BROWSER_SHAPED, message=f"{marker} customer B"),
                headers=_auth(_token(caps=[], sub="bob@x.com", tenant="tnt_a")))

    salt = get_settings().PII_SALT
    ref_a = _sref(salt, "tnt_a", "alice@x.com")

    body = client.get("/api/v1/signals",
                      params={"q": marker, "tenant": "tnt_a", "subject_ref": ref_a},
                      headers=_reader()).json()
    rows = [r for r in body["signals"] if marker in r["message"]]
    assert len(rows) == 1 and rows[0]["message"].endswith("customer A")


def test_a_tenant_only_search_with_no_subject_ref_returns_the_whole_shop(client):
    marker = "tenant-only-check-3c9d"
    client.post("/api/v1/signals/report",
                json=dict(BROWSER_SHAPED, message=f"{marker} one"),
                headers=_auth(_token(caps=[], sub="carol@x.com", tenant="tnt_c")))
    client.post("/api/v1/signals/report",
                json=dict(BROWSER_SHAPED, message=f"{marker} two"),
                headers=_auth(_token(caps=[], sub="dave@x.com", tenant="tnt_c")))

    body = client.get("/api/v1/signals", params={"q": marker, "tenant": "tnt_c"},
                      headers=_reader()).json()
    rows = [r for r in body["signals"] if marker in r["message"]]
    assert len(rows) == 2


def test_a_subject_ref_with_no_tenant_is_refused_not_a_cross_tenant_leak(client):
    """See SignalStore.browse's own note: subject_ref is only ever honoured alongside tenant.
    Silently dropping it used to WIDEN the query to every tenant instead of narrowing it — the one
    direction a filter must never fail in — so this is now a 400, not a silent no-op."""
    from app.config import get_settings
    from app.core.pii import subject_ref as _sref

    salt = get_settings().PII_SALT
    ref = _sref(salt, "tnt_e", "erin@x.com")

    resp = client.get("/api/v1/signals", params={"subject_ref": ref}, headers=_reader())
    assert resp.status_code == 400


def test_the_filter_lists_come_back_with_the_page(client):
    body = client.get("/api/v1/signals", headers=_reader()).json()
    assert "browser" in body["sources"] and "server_log" in body["sources"]
    assert "error" in body["severities"]
    assert "console" in body["services"]


def test_filters_narrow_the_stream(client):
    only_browser = client.get("/api/v1/signals", params={"source": "browser", "limit": 100},
                              headers=_reader()).json()["signals"]
    assert only_browser and all(r["source"] == "browser" for r in only_browser)

    # A comma list and repeated params mean the same thing to anybody who types either.
    a = client.get("/api/v1/signals", params={"source": "browser,server_log", "limit": 100},
                   headers=_reader()).json()["signals"]
    b = client.get("/api/v1/signals?source=browser&source=server_log&limit=100",
                   headers=_reader()).json()["signals"]
    assert len(a) == len(b) and len(a) > len(only_browser)


def test_a_new_severity_needs_no_migration_and_is_immediately_filterable(client):
    """The extensibility claim, proven rather than asserted: nothing on this service knows the word
    `warning`, and a filter for it works the moment one exists."""
    client.post("/internal/signals/ingest",
                json=dict(FLUENT_BIT_SHAPED, severity="warning",
                          message="disk 81% on node-2"),
                headers=_internal())
    body = client.get("/api/v1/signals", params={"severity": "warning", "limit": 50},
                      headers=_reader()).json()
    assert body["signals"] and all(r["severity"] == "warning" for r in body["signals"])
    assert "warning" in body["severities"]


# ── /internal/signals/reap ────────────────────────────────────────────────────────────────────
def test_reap_requires_the_internal_token(client):
    assert client.post("/internal/signals/reap", json={}).status_code == 401


def test_reap_accepts_the_empty_post_a_scheduler_sends(client):
    """PLAYBOOK §4.41. The platform's cron template posts an empty body with a JSON content type;
    a required Pydantic body answers 422 before a line of this route's code runs, and every probe
    stays green while the store grows without bound."""
    for body in ({}, None):
        r = client.post("/internal/signals/reap", json=body, headers=_internal())
        assert r.status_code == 200, r.text
        assert r.json() == {"removed": 0}   # nothing in this suite is ten days old

    # And with no body at all, which is the other shape a scheduler can send.
    r = client.post("/internal/signals/reap", headers=_internal())
    assert r.status_code == 200 and r.json() == {"removed": 0}


# ── the manifest tells the truth about all of it ──────────────────────────────────────────────
def test_the_manifest_declares_the_routes_and_the_capability(client):
    m = client.get("/internal/manifest", headers=_internal()).json()
    assert "platform.observability" in m["capabilities"]
    paths = {(e["method"], e["path"]) for e in m["endpoints"]}
    assert ("POST", "/internal/signals/ingest") in paths
    assert ("POST", "/internal/signals/reap") in paths
    assert ("GET", "/api/v1/signals") in paths
    assert ("POST", "/api/v1/signals/report") in paths
    ids = {a["id"] for a in m["admin_actions"]}
    assert "errors.list" in ids
    action = next(a for a in m["admin_actions"] if a["id"] == "errors.list")
    assert action["capability"] == "platform.observability"
    assert action["method"] == "GET" and action["path"] == "/api/v1/signals"
