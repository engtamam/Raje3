"""§13's auto-escalation — the properties worth a test:

  * a manager-owned referral (no parent_id) has nowhere to escalate to — skipped
  * a suspended affiliate's OPEN tickets escalate immediately, regardless of timing
  * an overdue (no first response past the timeout) ticket escalates; a fresh one does not
  * a ticket already escalated is never escalated twice (idempotent on ticket-service's own flag)
  * a resolved/closed ticket is left alone
  * one referral's ticket-service hiccup does not abort the whole sweep
"""
from __future__ import annotations

import time

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.escalation import TicketEscalationService
from app.core.models import ACTIVE, AFFILIATES, SUSPENDED, Affiliate
from app.core.referrals import ReferralRegistry

HOUR = 60 * 60


def _iso(epoch: float) -> str:
    import datetime as _dt
    return _dt.datetime.fromtimestamp(epoch, _dt.timezone.utc).isoformat()


async def _seed(store, *, affiliate_id: str, parent_id: str = "", status: str = ACTIVE,
                tenant: str = "t-1") -> ReferralRegistry:
    # STAMP WHILE ACTIVE — stamp() itself refuses a referral for an inactive affiliate; a
    # suspension happening AFTER the referral already exists is the real-world order of events.
    row = Affiliate(id=affiliate_id, person_id=f"p-{affiliate_id}", phone="+966501234567",
                    name="مسوّق", role="affiliate_promoter", parent_id=parent_id, status=ACTIVE)
    await store.put(AFFILIATES, affiliate_id, row.to_dict())
    if parent_id:
        mgr = Affiliate(id=parent_id, person_id=f"p-{parent_id}", phone="+966501234568",
                        name="مدير", role="affiliate_manager", status=ACTIVE)
        await store.put(AFFILIATES, parent_id, mgr.to_dict())
    referrals = ReferralRegistry(store=store, commission_amount_halalas=1000)
    await referrals.stamp(tenant=tenant, affiliate_id=affiliate_id)
    if status != ACTIVE:
        row.status = status
        await store.put(AFFILIATES, affiliate_id, row.to_dict())
    return referrals


class FakeTickets:
    """Scripted by tenant -> list of (ticket-row, kpis) — same "answers by key" idiom as this
    platform's other fakes. Records every escalate()/grant_share() call for assertions."""

    def __init__(self, by_tenant: dict) -> None:
        self._by_tenant = by_tenant
        self.escalated: list[dict] = []
        self.grants: list[dict] = []

    async def list_tickets(self, *, tenant: str, grantee: str) -> list[dict]:
        return [row for row, _ in self._by_tenant.get(tenant, [])]

    async def get_ticket(self, *, tenant: str, grantee: str, ticket_id: str) -> dict:
        for row, kpis in self._by_tenant.get(tenant, []):
            if row.get("id") == ticket_id:
                return {"ticket": row, "kpis": kpis}
        return {}

    async def escalate(self, *, tenant: str, grantee: str, ticket_id: str, assignee: str = "",
                       level: str = "", reason: str = "") -> dict:
        self.escalated.append({"tenant": tenant, "grantee": grantee, "ticket_id": ticket_id,
                               "assignee": assignee, "level": level})
        # Mark it escalated in the fake's own data so a re-sweep sees it as already handled.
        for row, kpis in self._by_tenant.get(tenant, []):
            if row.get("id") == ticket_id:
                kpis["escalated"] = True
        return {"id": ticket_id}

    async def grant_share(self, *, tenant: str, grantee: str, granted_by: str,
                          write: bool = True, scope=None) -> dict:
        self.grants.append({"tenant": tenant, "grantee": grantee})
        return {"granted": True}


def build(store, *, tickets, timeout_hours=24, sweep_max=200) -> TicketEscalationService:
    referrals = ReferralRegistry(store=store, commission_amount_halalas=1000)
    return TicketEscalationService(store=store, referrals=referrals, tickets=tickets,
                                   timeout_hours=timeout_hours, sweep_max=sweep_max)


@pytest.mark.anyio
async def test_no_tickets_configured_is_a_quiet_no_op():
    store = MemoryDataStore()
    svc = TicketEscalationService(store=store, referrals=ReferralRegistry(store=store),
                                  tickets=None)
    out = await svc.sweep()
    assert out == {"swept": False, "reason": "tickets_not_configured"}


@pytest.mark.anyio
async def test_a_manager_owned_referral_has_nowhere_to_escalate_to():
    store = MemoryDataStore()
    referrals = await _seed(store, affiliate_id="mgr-1", parent_id="")   # a manager, no parent
    tickets = FakeTickets({"t-1": [({"id": "tk-1", "status": "new"}, {})]})
    svc = TicketEscalationService(store=store, referrals=referrals, tickets=tickets)
    out = await svc.sweep()
    assert out["tickets_escalated"] == 0
    assert tickets.escalated == []


@pytest.mark.anyio
async def test_a_suspended_affiliates_open_tickets_escalate_immediately():
    store = MemoryDataStore()
    referrals = await _seed(store, affiliate_id="prm-1", parent_id="mgr-1", status=SUSPENDED)
    now = time.time()
    tickets = FakeTickets({"t-1": [
        ({"id": "tk-1", "status": "new"}, {"created_at": _iso(now), "escalated": False}),
    ]})   # just created — an overdue check would NOT trigger this, suspension bypasses timing
    svc = TicketEscalationService(store=store, referrals=referrals, tickets=tickets,
                                  timeout_hours=24)
    out = await svc.sweep()
    assert out["tickets_escalated"] == 1
    assert tickets.escalated[0]["assignee"] == "mgr-1"
    assert tickets.escalated[0]["level"] == "suspended"
    assert tickets.grants[0] == {"tenant": "t-1", "grantee": "mgr-1"}   # manager gets his own share


@pytest.mark.anyio
async def test_an_overdue_ticket_with_no_first_response_escalates():
    store = MemoryDataStore()
    referrals = await _seed(store, affiliate_id="prm-2", parent_id="mgr-2", tenant="t-2")
    old = time.time() - 25 * HOUR
    tickets = FakeTickets({"t-2": [
        ({"id": "tk-1", "status": "new"}, {"created_at": _iso(old), "escalated": False}),
    ]})
    svc = TicketEscalationService(store=store, referrals=referrals, tickets=tickets,
                                  timeout_hours=24)
    out = await svc.sweep()
    assert out["tickets_escalated"] == 1
    assert tickets.escalated[0]["level"] == "timeout"


@pytest.mark.anyio
async def test_a_fresh_ticket_inside_the_timeout_does_not_escalate():
    store = MemoryDataStore()
    referrals = await _seed(store, affiliate_id="prm-3", parent_id="mgr-3", tenant="t-3")
    recent = time.time() - 1 * HOUR
    tickets = FakeTickets({"t-3": [
        ({"id": "tk-1", "status": "new"}, {"created_at": _iso(recent), "escalated": False}),
    ]})
    svc = TicketEscalationService(store=store, referrals=referrals, tickets=tickets,
                                  timeout_hours=24)
    out = await svc.sweep()
    assert out["tickets_escalated"] == 0


@pytest.mark.anyio
async def test_a_ticket_with_a_first_response_never_times_out():
    store = MemoryDataStore()
    referrals = await _seed(store, affiliate_id="prm-4", parent_id="mgr-4", tenant="t-4")
    old = time.time() - 48 * HOUR
    tickets = FakeTickets({"t-4": [
        ({"id": "tk-1", "status": "new"},
         {"created_at": _iso(old), "first_response_at": _iso(old + 60), "escalated": False}),
    ]})
    svc = TicketEscalationService(store=store, referrals=referrals, tickets=tickets,
                                  timeout_hours=24)
    out = await svc.sweep()
    assert out["tickets_escalated"] == 0


@pytest.mark.anyio
async def test_an_already_escalated_ticket_is_never_escalated_twice():
    store = MemoryDataStore()
    referrals = await _seed(store, affiliate_id="prm-5", parent_id="mgr-5", tenant="t-5")
    old = time.time() - 48 * HOUR
    tickets = FakeTickets({"t-5": [
        ({"id": "tk-1", "status": "new"}, {"created_at": _iso(old), "escalated": True}),
    ]})
    svc = TicketEscalationService(store=store, referrals=referrals, tickets=tickets,
                                  timeout_hours=24)
    out = await svc.sweep()
    assert out["tickets_escalated"] == 0


@pytest.mark.anyio
async def test_a_resolved_ticket_is_left_alone():
    store = MemoryDataStore()
    referrals = await _seed(store, affiliate_id="prm-6", parent_id="mgr-6", tenant="t-6")
    old = time.time() - 48 * HOUR
    tickets = FakeTickets({"t-6": [
        ({"id": "tk-1", "status": "resolved"}, {"created_at": _iso(old), "escalated": False}),
    ]})
    svc = TicketEscalationService(store=store, referrals=referrals, tickets=tickets,
                                  timeout_hours=24)
    out = await svc.sweep()
    assert out["tickets_escalated"] == 0


@pytest.mark.anyio
async def test_one_referrals_hiccup_never_aborts_the_whole_sweep():
    store = MemoryDataStore()
    referrals = await _seed(store, affiliate_id="prm-7", parent_id="mgr-7", tenant="t-7")

    class BrokenOnList(FakeTickets):
        async def list_tickets(self, *, tenant, grantee):
            raise RuntimeError("ticket-service unreachable")

    svc = TicketEscalationService(store=store, referrals=referrals,
                                  tickets=BrokenOnList({}), timeout_hours=24)
    out = await svc.sweep()
    assert out["swept"] is True
    assert out["tickets_escalated"] == 0   # never raised past the sweep


@pytest.mark.anyio
async def test_sweep_reads_a_repeat_affiliates_row_only_once():
    """THE DEDUP THIS CLOSES. `sweep()` used to call `store.get(AFFILIATES, ...)` once per
    referral with no memoization — a manager referred by five shops had his own row fetched five
    separate times in one sweep pass. Proved by counting real `get` calls against the store, not
    just the escalation outcome: a fix that still re-fetched per referral would still pass a
    value-only assertion."""
    store = MemoryDataStore()
    referrals = await _seed(store, affiliate_id="prm-9", parent_id="mgr-9", tenant="t-9a")
    # THE SAME PROMOTER, TWO MORE SHOPS. Three referrals, one affiliate row.
    await referrals.stamp(tenant="t-9b", affiliate_id="prm-9")
    await referrals.stamp(tenant="t-9c", affiliate_id="prm-9")

    now = time.time()
    tickets = FakeTickets({
        "t-9a": [({"id": "tk-a", "status": "new"}, {"created_at": _iso(now), "escalated": False})],
        "t-9b": [({"id": "tk-b", "status": "new"}, {"created_at": _iso(now), "escalated": False})],
        "t-9c": [({"id": "tk-c", "status": "new"}, {"created_at": _iso(now), "escalated": False})],
    })

    calls = {"n": 0}
    real_get = store.get

    async def counting_get(collection, key):
        if collection == AFFILIATES and key == "prm-9":
            calls["n"] += 1
        return await real_get(collection, key)

    store.get = counting_get

    svc = TicketEscalationService(store=store, referrals=referrals, tickets=tickets,
                                  timeout_hours=24)
    out = await svc.sweep()

    assert out["referrals_checked"] == 3
    assert calls["n"] == 1, f"expected one memoized read of prm-9, got {calls['n']}"
