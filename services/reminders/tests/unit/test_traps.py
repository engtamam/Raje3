"""The five traps no guard can catch — asserted here so the next service inherits them.

Each of these is a defect this codebase actually shipped. A guard cannot catch them because each
one is two components that are individually correct disagreeing where they meet, or a rule that
exists in one place and is bypassed by another. Only a test that crosses the seam can see them.
"""
from __future__ import annotations

import asyncio
import inspect

from app.adapters.datastore.memory import MemoryDataStore
from app.core import gate as G
from app.core.erasure import RemindersErasure
from app.core.models import Preferences, Schedule, as_row
from app.core.stores import ScheduleStore


def run(c):
    return asyncio.run(c)


# ── TRAP 1: a rule enforced in the core and bypassed at the door ────────────────────────────────
def test_every_field_the_core_validates_is_declared_on_the_api_model():
    """operations shipped this exact bug: TemplateLibrary refused a template asking the owner to
    fill two fields, the unit test proved it, and the live call returned 200 — because the console
    model never declared `fills`, so pydantic dropped it and the core checked an empty list.

    A unit test cannot see it: it calls the core directly and never crosses the model.
    """
    from app.api.v1 import platform as mod
    declared = set(mod.LimitsIn.model_fields)
    # Every knob the gate reasons about must be settable, or the console silently drops it.
    for field in ("daily_service_cap", "daily_total_cap", "monthly_marketing_cap",
                  "marketing_cooldown_hours"):
        assert field in declared, f"{field} is enforced but the API model would drop it"


def test_the_sending_window_is_deliberately_absent_from_the_api_model():
    """The regulator's, not ours, and not for sale. An absence is a cleaner refusal than a
    validation error — it never invites the request."""
    from app.api.v1 import platform as mod
    assert "window_start_hour" not in mod.LimitsIn.model_fields
    assert "send_window_start_hour" not in mod.LimitsIn.model_fields


# ── TRAP 2: a cap counted per campaign instead of per customer ──────────────────────────────────
def test_the_cap_is_counted_against_the_customer_not_the_campaign():
    """Two small campaigns each under the limit exceed it together, and each one is correct
    alone — which is why nobody finds it by reading either."""
    sig = inspect.signature(G.evaluate)
    assert "recent_sends" in sig.parameters
    # The evidence is that the gate takes one customer's history and nothing campaign-shaped.
    assert not any("campaign" in p for p in sig.parameters)


# ── TRAP 3: a schedule surviving its customer's erasure ─────────────────────────────────────────
def test_no_schedule_survives_an_erasure():
    """Not a leak — a message to someone who asked us to go away, which is worse."""
    st = MemoryDataStore()
    sched = ScheduleStore(st)
    for kind in ("reminder", "follow_up"):
        s = Schedule(tenant="t1", subject_ref="sub_a", service_id="oil", kind=kind, due_at=1)
        run(sched.upsert("t1", s.key, as_row(s)))
    run(RemindersErasure(store=st).erase("t1", "sub_a"))
    assert run(sched.pending_for_subject("t1", "sub_a")) == []


def test_preferences_are_erased_after_the_schedules_not_before():
    """If prefs went first and the erasure failed halfway, we would hold schedules with no record
    of what the customer switched off — the one partial state that sends MORE than before."""
    src = inspect.getsource(RemindersErasure.erase)
    order = src.index("SCHEDULES"), src.index("PREFS")
    assert order[0] < order[1]


# ── TRAP 4: the heartbeat's own path is a route no route serves ─────────────────────────────────
def test_the_heartbeats_own_path_in_the_values_file_is_a_route_this_service_serves():
    """ticket-service shipped NOTIFICATION_SEND_PATH=/internal/notifications/send against a peer
    serving /internal/notify. Every notification went to a silent 404 for weeks.

    THE HEARTBEAT ITSELF MOVED (2026-09-16): tick/receipts-pull are no longer a `cronJobs:` block
    in this file — they are a job-service schedule + push-dispatch target, provisioned by
    deploy/hooks/job-schedule.sh/job-dispatch-target.sh, whose exact commands are documented right
    above `env:` as a comment (never removed as "just prose" — this test still reads the paths out
    of it, the same invariant as before, just against the new heartbeat's own documentation)."""
    import pathlib
    import re
    from app.config import Settings
    from app.manifest import build_manifest
    values = pathlib.Path(__file__).resolve().parents[4] / "deploy/services/reminders.values.yaml"
    text = values.read_text(encoding="utf-8")
    heartbeat_paths = re.findall(r"http://reminders:8000(/internal/\S+)", text)
    assert heartbeat_paths, "the tick/receipts-pull heartbeat commands must still be documented"
    served = {e["path"] for e in build_manifest(Settings(INTERNAL_SERVICE_TOKEN="x" * 40))
              ["endpoints"]}
    for path in heartbeat_paths:
        assert path in served, f"the heartbeat drives {path}, which no route serves"


def test_every_peer_path_setting_matches_the_peer_that_serves_it():
    """The other side of the same seam: a *_PATH default naming a route nobody serves."""
    from app.config import Settings
    s = Settings(INTERNAL_SERVICE_TOKEN="x" * 40)
    # Verified against notification-service's and operations' manifests when written, and pinned
    # here so a careless edit fails a test rather than a customer's message.
    assert s.NOTIFICATION_SEND_PATH == "/internal/notify"
    assert s.OPERATIONS_RECIPIENT_PATH == "/internal/operations/recipient"
    assert s.OPERATIONS_VISITS_SINCE_PATH == "/internal/operations/visits/since"


# ── TRAP 5: a peer value that resolves in one namespace and not another ─────────────────────────
def test_no_peer_url_relies_on_being_in_the_same_namespace():
    """A postgres DSN copied from base-services into monitoring stopped resolving: `@postgres:5432`
    is not a name outside its own namespace. Ours are short too — and correct, because this
    service only ever runs beside its peers. The test pins that assumption where it can be read."""
    from app.config import Settings
    s = Settings(INTERNAL_SERVICE_TOKEN="x" * 40)
    for url in (s.NOTIFICATION_SERVICE_URL, s.OPERATIONS_SERVICE_URL, s.AUDIT_SERVICE_URL):
        if url and "://" in url:
            host = url.split("://", 1)[1].split(":")[0].split("/")[0]
            assert "." not in host or host.endswith("svc.cluster.local"), (
                f"{host} is neither a bare in-namespace name nor a fully qualified one")


# ── and the one that is not a trap but a promise ────────────────────────────────────────────────
def test_a_stopped_class_is_refused_under_every_priority():
    """The customer's own instruction outranks the ladder, the caps, and every exemption."""
    now = 1_800_000_000
    for cls in ("service", "personal", "marketing"):
        d = G.evaluate(cls=cls, template_type="svc_visit_confirmation", now=now,
                       limits=G.Limits(), prefs_stopped={cls: True}, engagement_score=100.0,
                       engagement_at=now, recent_sends=[],
                       eng_cfg=__import__("app.core.engagement", fromlist=["x"])
                       .EngagementConfig())
        assert not d.allowed
