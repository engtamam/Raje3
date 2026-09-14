"""Retention — and every case where deleting would be the wrong answer."""
from __future__ import annotations

import asyncio

from app.adapters.datastore.memory import MemoryDataStore
from app.core.retention import (DAY, YEAR, LapsedStore, Policy, due_customers, policy_for)

NOW = 1_800_000_000
P = Policy()


def run(c):
    return asyncio.run(c)


def cust(last_visit, *, phone="0501234567", name="محمد"):
    return {"id": "c1", "phone": phone, "name": name, "last_visit": last_visit}


# ── the customer clock ─────────────────────────────────────────────────────────────────────────
def test_a_customer_past_the_horizon_is_due():
    assert due_customers([cust(NOW - 6 * YEAR)], now=NOW, policy=P)


def test_a_customer_inside_the_horizon_is_not():
    """A customer away three years is EXACTLY what we sell — the whole return engine exists to
    bring back the absent. Deleting him for being absent deletes the product."""
    assert not due_customers([cust(NOW - 3 * YEAR)], now=NOW, policy=P)


def test_an_already_cleared_row_is_left_alone():
    """Running the erasure again would count work nobody did and log a deletion that deleted
    nothing."""
    assert not due_customers([cust(NOW - 9 * YEAR, phone="", name="")], now=NOW, policy=P)


def test_a_customer_with_no_last_visit_is_never_touched():
    """UNKNOWN IS NOT ANCIENT. Treating it as old would erase a customer recorded this morning by
    an import that carried no dates — the failure that looks like data loss because it is."""
    assert not due_customers([cust(0)], now=NOW, policy=P)


def test_a_shorter_policy_catches_more():
    rows = [cust(NOW - 3 * YEAR)]
    assert not due_customers(rows, now=NOW, policy=Policy(customer_years=5))
    assert due_customers(rows, now=NOW, policy=Policy(customer_years=2))


# ── the establishment clock, which we start ourselves ──────────────────────────────────────────
def store():
    return LapsedStore(MemoryDataStore())


def test_the_clock_starts_the_first_day_we_find_him_unsubscribed():
    """Billing exposes no subscription end — the same gap as trial_end. So we do not ask: we
    OBSERVE, and the date we write down is the day he actually stopped being served."""
    s = store()
    assert run(s.note("t1", now=NOW)) == NOW


def test_a_second_sweep_does_not_restart_the_clock():
    """Written once. A second write on the second day would reset the very clock it measures, and
    nothing anywhere would look wrong."""
    s = store()
    run(s.note("t1", now=NOW))
    assert run(s.note("t1", now=NOW + 30 * DAY)) == NOW


def test_coming_back_erases_the_clock_rather_than_pausing_it():
    s = store()
    run(s.note("t1", now=NOW))
    run(s.clear("t1"))
    assert run(s.since("t1")) == 0
    assert run(s.note("t1", now=NOW + YEAR)) == NOW + YEAR


def test_an_establishment_inside_its_grace_is_not_due():
    """His history waiting for him is exactly why he comes back — and deleting it is what a
    competitor needs in order to take him (§16.4.2)."""
    s = store()
    run(s.note("t1", now=NOW - 1 * YEAR))
    assert run(s.due(now=NOW, policy=P)) == []


def test_an_establishment_past_its_grace_is_due():
    s = store()
    run(s.note("t1", now=NOW - 3 * YEAR))
    assert run(s.due(now=NOW, policy=P)) == ["t1"]


# ── the setting, and the edits that must not be honoured ───────────────────────────────────────
class Cfg:
    def __init__(self, value):
        self.value = value

    async def get(self, *, tenant, key, default):
        return self.value


def test_a_shop_may_shorten_its_retention():
    assert run(policy_for(Cfg(2), "t1")).customer_years == 2


def test_a_shop_may_not_extend_it_beyond_ours():
    """'Keep everything for fifty years' is not a preference we may honour."""
    assert run(policy_for(Cfg(50), "t1")).customer_years == P.customer_years


def test_zero_falls_back_rather_than_erasing_everybody():
    """A zero in a console field would erase every customer on the next sweep — including this
    morning's."""
    assert run(policy_for(Cfg(0), "t1")).customer_years == P.customer_years
    assert run(policy_for(Cfg(-1), "t1")).customer_years == P.customer_years


def test_a_nonsense_value_falls_back():
    assert run(policy_for(Cfg("abc"), "t1")).customer_years == P.customer_years


def test_no_config_at_all_uses_our_default():
    assert run(policy_for(None, "t1")).customer_years == P.customer_years


# ── the sweep itself ───────────────────────────────────────────────────────────────────────────
class Subs:
    """Answers live / gone / unknown, on command."""

    def __init__(self, answer):
        self.answer = answer

    async def live(self, tenant):
        return self.answer


class Eraser:
    def __init__(self):
        self.calls = []

    async def erase(self, tenant, subject):
        self.calls.append((tenant, subject))
        return {}


def sweeper(rows, *, subs=None, cfg=None):
    from app.core.models import CUSTOMERS
    from app.core.retention import Sweeper
    store = MemoryDataStore()
    for i, r in enumerate(rows):
        run(store.put(CUSTOMERS, f"{r['tenant']}|c{i}", dict(r, id=f"c{i}")))
    e = Eraser()
    return Sweeper(store=store, eraser=e, runtime_config=cfg, subscriptions=Subs(subs)), e


def row(tenant, last_visit, phone="0501234567"):
    return {"tenant": tenant, "phone": phone, "name": "محمد", "last_visit": last_visit}


def test_the_sweep_erases_through_the_erasure_that_already_exists():
    """Not a second deletion written here. A second definition of 'erased' would eventually
    disagree with the first, and one of them would be the one a regulator read."""
    sw, e = sweeper([row("t1", NOW - 7 * YEAR)])
    out = run(sw.sweep(now=NOW))
    assert out.customers == 1
    assert e.calls == [("t1", "0501234567")]


def test_a_recent_customer_survives_the_sweep():
    sw, e = sweeper([row("t1", NOW - DAY)])
    assert run(sw.sweep(now=NOW)).customers == 0
    assert e.calls == []


def test_an_unreachable_billing_starts_no_clock():
    """An outage that answered 'gone' would write a lapse date for every establishment in the
    platform, and nothing would look wrong until the grace expired."""
    sw, _ = sweeper([row("t1", NOW - DAY)], subs=None)
    run(sw.sweep(now=NOW))
    assert run(sw.lapsed.since("t1")) == 0


def test_an_establishment_inside_its_grace_is_untouched():
    """The load-bearing test. He left last month; his customers are recent; nothing may be
    deleted — his history waiting for him is why he comes back at all."""
    sw, e = sweeper([row("t1", NOW - DAY)], subs=False)
    out = run(sw.sweep(now=NOW))
    assert out.customers == 0
    assert out.establishments_erased == 0
    assert e.calls == []
    assert run(sw.lapsed.since("t1")) == NOW      # the clock started, and only the clock


def test_an_establishment_past_its_grace_loses_everything_including_recent_customers():
    """Past the line it is not a customer-age question any more — the establishment itself is
    gone, so a visit last week is no more retainable than one from 2019."""
    sw, e = sweeper([row("t1", NOW - DAY)], subs=False)
    run(sw.sweep(now=NOW - 3 * YEAR))             # the night we first saw him gone
    out = run(sw.sweep(now=NOW))
    assert out.establishments_erased == 1
    assert out.customers == 1
    assert e.calls == [("t1", "0501234567")]


def test_a_shop_that_resubscribes_has_no_clock_at_all():
    sw, e = sweeper([row("t1", NOW - DAY)], subs=False)
    run(sw.sweep(now=NOW - 3 * YEAR))
    sw._subs = Subs(True)
    out = run(sw.sweep(now=NOW))
    assert out.customers == 0
    assert e.calls == []
    assert run(sw.lapsed.since("t1")) == 0


# ── a gone establishment's own Salla connection ─────────────────────────────────────────────────
class FakeSalla:
    def __init__(self) -> None:
        self.disconnected: list[str] = []

    async def disconnect(self, tenant: str) -> bool:
        self.disconnected.append(tenant)
        return True


def test_an_establishment_past_its_grace_also_loses_its_salla_connection():
    from app.core.retention import Sweeper

    salla = FakeSalla()
    sw, _ = sweeper([row("t1", NOW - DAY)], subs=False)
    sw._salla = salla
    run(sw.sweep(now=NOW - 3 * YEAR))              # the night we first saw him gone
    run(sw.sweep(now=NOW))                          # past the grace horizon
    assert salla.disconnected == ["t1"]


def test_an_establishment_inside_its_grace_keeps_its_salla_connection():
    salla = FakeSalla()
    sw, _ = sweeper([row("t1", NOW - DAY)], subs=False)
    sw._salla = salla
    run(sw.sweep(now=NOW))                           # only just gone, still inside the grace
    assert salla.disconnected == []


def test_no_salla_service_wired_at_all_is_a_harmless_default():
    """Every OTHER test in this file constructs a Sweeper with no `salla=` argument at all —
    this confirms that stays true after the parameter was added, not just for tests written
    after it (`salla=None` must never be required)."""
    sw, e = sweeper([row("t1", NOW - DAY)], subs=False)
    run(sw.sweep(now=NOW - 3 * YEAR))
    out = run(sw.sweep(now=NOW))
    assert out.establishments_erased == 1            # the sweep itself still worked


def test_one_establishment_leaving_does_not_touch_another():
    from app.core.models import CUSTOMERS
    from app.core.retention import Sweeper

    store = MemoryDataStore()
    run(store.put(CUSTOMERS, "t1|c1", dict(row("t1", NOW - DAY), id="c1")))
    run(store.put(CUSTOMERS, "t2|c2", dict(row("t2", NOW - DAY, phone="0559999999"), id="c2")))
    e = Eraser()

    class PerTenant:
        async def live(self, tenant):
            return tenant != "t1"

    sw = Sweeper(store=store, eraser=e, subscriptions=PerTenant())
    run(sw.sweep(now=NOW - 3 * YEAR))
    run(sw.sweep(now=NOW))
    assert e.calls == [("t1", "0501234567")]
