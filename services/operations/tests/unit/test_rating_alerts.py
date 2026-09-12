"""`rating_alerts.evaluate` (the pure policy) and `check_and_notify` (the wiring) — last 10 rated
visits, minimum 5 counted, average below 4.5, the owner's own explicit numbers (2026-09-12).
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.adapters.datastore.memory import MemoryDataStore
from app.core import rating_alerts as RA
from app.core.models import Operator, Visit
from app.core.stores import AccountSettingsStore, OperatorStore, VisitStore

TENANT = "tnt_alpha"


def run(coro):
    return asyncio.run(coro)


# ── evaluate() — the pure policy ──────────────────────────────────────────────────────────────
def test_fewer_than_five_ratings_never_alerts_no_matter_how_low():
    v = RA.evaluate([1, 1])
    assert v.should_alert is False
    assert v.sample_size == 2


def test_five_ratings_averaging_below_the_threshold_alerts():
    v = RA.evaluate([4, 4, 4, 4, 3])   # average 3.8
    assert v.should_alert is True
    assert v.sample_size == 5
    assert round(v.average, 2) == 3.8


def test_five_ratings_averaging_at_or_above_the_threshold_does_not_alert():
    v = RA.evaluate([5, 5, 5, 5, 3])   # average 4.6
    assert v.should_alert is False


def test_exactly_at_the_threshold_does_not_alert():
    """Strictly BELOW 4.5, never at it — the owner's own number is a floor a shop can sit on."""
    v = RA.evaluate([5, 5, 5, 5, 5, 4, 4, 4, 4, 4])   # average 4.5 exactly
    assert round(v.average, 2) == 4.5
    assert v.should_alert is False


def test_more_than_ten_ratings_is_the_callers_job_not_evaluates():
    """evaluate() trusts its input is already windowed — VisitStore.ratings(limit=WINDOW) does
    the trimming; this just proves evaluate() itself does not re-trim silently."""
    v = RA.evaluate([1] * 11)
    assert v.sample_size == 11


# ── check_and_notify() — the wiring ───────────────────────────────────────────────────────────
class _FakeAuthz:
    async def list_assignments(self, tenant):
        return [{"subject": "owner_1", "roles": [], "capabilities": ["operations.manage"]}]

    async def effective_capabilities(self, tenant, subject, roles):
        return set()


class _FakeNotifier:
    def __init__(self):
        self.calls: list[dict] = []

    async def send(self, **kw):
        self.calls.append(kw)
        return True


def _container(store):
    return SimpleNamespace(datastore=store, authz_desk=_FakeAuthz(), inapp_notifier=_FakeNotifier())


async def _seed_ratings(store, operator_id: str, ratings: list[int], branch_id: str = "") -> str:
    """Writes one Visit per rating, oldest first by `rated_at`; returns the LAST (newest, highest
    `rated_at`) visit's id — the one `check_and_notify` is called for."""
    last_id = ""
    for i, r in enumerate(ratings):
        vid = f"v_{operator_id}_{i}"
        v = Visit(tenant=TENANT, id=vid, customer_id="cus_1", operator_id=operator_id,
                  branch_id=branch_id, rating=r, rated_at=1000 + i, created=1000 + i)
        await VisitStore(store).save(v)
        last_id = vid
    return last_id


def test_a_qualifying_drop_notifies_every_resolved_manager():
    store = MemoryDataStore()
    last_id = run(_seed_ratings(store, "op_1", [4, 4, 4, 4, 3]))   # average 3.8, 5 samples
    c = _container(store)
    run(RA.check_and_notify(c, tenant=TENANT, operator_id="op_1", operator_name="سارة",
                            branch_id="", triggering_visit_id=last_id))
    assert len(c.inapp_notifier.calls) == 1
    call = c.inapp_notifier.calls[0]
    assert call["user_id"] == "owner_1"
    assert call["template_key"] == RA.TEMPLATE_KEY
    assert call["variables"]["name"] == "سارة"
    assert call["variables"]["average"] == "3.8"
    assert last_id in call["idempotency_key"]
    assert "owner_1" in call["idempotency_key"]


def test_fewer_than_five_ratings_sends_nothing():
    store = MemoryDataStore()
    last_id = run(_seed_ratings(store, "op_1", [1, 1]))
    c = _container(store)
    run(RA.check_and_notify(c, tenant=TENANT, operator_id="op_1", operator_name="سارة",
                            branch_id="", triggering_visit_id=last_id))
    assert c.inapp_notifier.calls == []


def test_a_healthy_average_sends_nothing():
    store = MemoryDataStore()
    last_id = run(_seed_ratings(store, "op_1", [5, 5, 5, 5, 5]))
    c = _container(store)
    run(RA.check_and_notify(c, tenant=TENANT, operator_id="op_1", operator_name="سارة",
                            branch_id="", triggering_visit_id=last_id))
    assert c.inapp_notifier.calls == []


def test_no_operator_id_is_refused_before_any_read():
    store = MemoryDataStore()
    c = _container(store)
    run(RA.check_and_notify(c, tenant=TENANT, operator_id="", operator_name="",
                            branch_id="", triggering_visit_id="v1"))
    assert c.inapp_notifier.calls == []


def test_only_the_operators_own_last_ten_ratings_are_considered():
    """A second operator's bad ratings must never pull the first operator's average down."""
    store = MemoryDataStore()
    last_id = run(_seed_ratings(store, "op_1", [5, 5, 5, 5, 5]))
    run(_seed_ratings(store, "op_2", [1, 1, 1, 1, 1]))
    c = _container(store)
    run(RA.check_and_notify(c, tenant=TENANT, operator_id="op_1", operator_name="سارة",
                            branch_id="", triggering_visit_id=last_id))
    assert c.inapp_notifier.calls == []


# ── per-recipient locale ───────────────────────────────────────────────────────────────────────
def test_a_recipients_own_saved_locale_is_used():
    store = MemoryDataStore()
    last_id = run(_seed_ratings(store, "op_1", [4, 4, 4, 4, 3]))
    run(AccountSettingsStore(store).set_locale(TENANT, "owner_1", "ur"))
    c = _container(store)
    run(RA.check_and_notify(c, tenant=TENANT, operator_id="op_1", operator_name="سارة",
                            branch_id="", triggering_visit_id=last_id))
    assert c.inapp_notifier.calls[0]["locale"] == "ur"


def test_no_saved_locale_falls_back_to_arabic():
    store = MemoryDataStore()
    last_id = run(_seed_ratings(store, "op_1", [4, 4, 4, 4, 3]))
    c = _container(store)
    run(RA.check_and_notify(c, tenant=TENANT, operator_id="op_1", operator_name="سارة",
                            branch_id="", triggering_visit_id=last_id))
    assert c.inapp_notifier.calls[0]["locale"] == "ar"


def test_a_locale_outside_the_registered_five_falls_back_to_arabic():
    """A stale/foreign value (predating this list, or never validated at write time) must not be
    handed straight to notify() — the template is registered in exactly these five, and an
    unregistered locale would fail the send outright rather than degrade to Arabic."""
    store = MemoryDataStore()
    last_id = run(_seed_ratings(store, "op_1", [4, 4, 4, 4, 3]))
    run(AccountSettingsStore(store).set_locale(TENANT, "owner_1", "fr"))
    c = _container(store)
    run(RA.check_and_notify(c, tenant=TENANT, operator_id="op_1", operator_name="سارة",
                            branch_id="", triggering_visit_id=last_id))
    assert c.inapp_notifier.calls[0]["locale"] == "ar"


def test_two_recipients_each_get_their_own_locale():
    store = MemoryDataStore()
    run(_seed_operator(store, person_id="mgr_1", branch_id="", visible_all=True))
    last_id = run(_seed_ratings(store, "op_1", [4, 4, 4, 4, 3]))
    run(AccountSettingsStore(store).set_locale(TENANT, "owner_1", "en"))
    run(AccountSettingsStore(store).set_locale(TENANT, "mgr_1", "ha"))
    authz = _FakeAuthzTwo()
    notifier = _FakeNotifier()
    c = SimpleNamespace(datastore=store, authz_desk=authz, inapp_notifier=notifier)
    run(RA.check_and_notify(c, tenant=TENANT, operator_id="op_1", operator_name="سارة",
                            branch_id="", triggering_visit_id=last_id))
    by_user = {call["user_id"]: call["locale"] for call in notifier.calls}
    assert by_user == {"owner_1": "en", "mgr_1": "ha"}


class _FakeAuthzTwo:
    async def list_assignments(self, tenant):
        return [
            {"subject": "owner_1", "roles": [], "capabilities": ["operations.manage"]},
            {"subject": "mgr_1", "roles": [], "capabilities": ["operations.manage"]},
        ]

    async def effective_capabilities(self, tenant, subject, roles):
        return set()


async def _seed_operator(store, **over) -> None:
    base = dict(tenant=TENANT, id=f"op_{over.get('person_id', 'x')}", name="x")
    base.update(over)
    await OperatorStore(store).save(Operator(**base))
