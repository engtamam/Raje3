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


def test_tick_with_no_tenant_sweeps_every_tenant_instead_of_erroring(client):
    """A CronJob posts NO body at all (one fixed TARGET_URL, no per-tenant templating — see
    platform/deploy/chart/templates/cronjob.yaml) — the exact shape this hits. Refusing an empty
    `tenant` used to mean the heartbeat failed on every single scheduled invocation while every
    probe stayed green (the same defect class reminders' own /reminders/tick already carries the
    fix for). An empty body now means "every tenant with a conversation row", not an error."""
    resp = client.post("/internal/whatsapp_assistant/tick", json={},
                       headers={"X-Internal-Token": INTERNAL_TOKEN})
    assert resp.status_code == 200
    body = resp.json()
    assert "error" not in body
    assert body["tenant"] == ""
    assert "tenants_swept" in body


def test_manifest_requires_internal_token(client):
    resp = client.get("/internal/manifest")
    assert resp.status_code == 401


async def test_one_tenants_broken_compose_reply_does_not_wedge_the_whole_tick(client):
    """The real incident this guards: `compose_reply` is the one real LLM/network round trip in
    the tick, so it is the one call that can fail on data this service does not control (a
    malformed provider response, a transient outage, one poisoned conversation). Before the
    per-conversation try/except in `_tick_one_tenant`, this exception propagated out of BOTH
    loops — every OTHER tenant still queued behind the broken one in `tick()` never ran, on
    every single scheduled invocation, until someone intervened by hand."""
    import app.api.internal as internal_module

    c = client.app.state.container
    real_sweep_due = c.engine.sweep_due
    real_compose_reply = c.engine.compose_reply
    real_active_tenants = internal_module._active_tenants

    async def fake_active_tenants(container, limit=2000):
        # a fixed two-tenant worklist, regardless of what is really in the datastore — this test
        # only needs to prove one broken tenant does not stop the other from being swept.
        return ["broken-tenant", "fine-tenant"]

    async def fake_sweep_due(tenant, *, now=None, batch=200):
        return ["broken-subject"] if tenant == "broken-tenant" else ["fine-subject"]

    call_log: list[str] = []

    async def fake_compose_reply(tenant, subject_ref, *, now=None):
        call_log.append(tenant)
        if tenant == "broken-tenant":
            raise RuntimeError("simulated malformed LLM response")
        from app.core.conversation import ReplyPlan

        return ReplyPlan(kind="none")

    internal_module._active_tenants = fake_active_tenants
    c.engine.sweep_due = fake_sweep_due
    c.engine.compose_reply = fake_compose_reply
    try:
        resp = client.post(
            "/internal/whatsapp_assistant/tick",
            json={},
            headers={"X-Internal-Token": INTERNAL_TOKEN},
        )
    finally:
        internal_module._active_tenants = real_active_tenants
        c.engine.sweep_due = real_sweep_due
        c.engine.compose_reply = real_compose_reply

    # NEVER a 500 — the broken tenant's failure is swallowed and logged, not raised.
    assert resp.status_code == 200, resp.text
    # AND the fine tenant's conversation was still actually attempted — proof the broken tenant
    # did not abort the loop before reaching it.
    assert "fine-tenant" in call_log
    assert "broken-tenant" in call_log
