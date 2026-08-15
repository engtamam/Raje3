"""Where a service's cycle comes from — and the order that decides it.

THE DEFECT, FOUND ON THE CLUSTER. A real car wash's catalogue says «غسيل خارجي» every 10 days and
«غسيل شامل» every 21. Its visit scheduled ONE reminder, 83 days out — 90 (our platform default)
minus a 7-day lead — and both learned rules were seeded at `interval_days: 90.0`.

Nothing failed. The settings tree answered our default because the owner had never hand-edited a
service, and the catalogue that holds his real cycles was read by nobody. Every shop that never
edits a service — every new shop — reminded its customers three months late.

THE ORDER THIS PINS:
    1. what the owner set explicitly (service, then its group, then his shop-wide setting)
    2. his catalogue — the number seeded from his sector and shown to him in «خدماتي»
    3. our platform default, and only when nobody else has an answer
"""
from __future__ import annotations

import asyncio

import pytest


def run(c):
    return asyncio.run(c)


class FakeCatalogue:
    def __init__(self, cycles=None, *, boom=False):
        self._cycles = cycles or {}
        self._boom = boom
        self.calls = 0

    async def cycles(self, tenant):
        self.calls += 1
        if self._boom:
            raise RuntimeError("operations is restarting")
        return dict(self._cycles)


class FakeStore:
    """Enough datastore for SettingsStore.load and the rules read."""

    def __init__(self, rows=None):
        self.rows = rows or {}

    async def get(self, coll, key):
        return self.rows.get((coll, key))

    async def put(self, coll, key, row):
        self.rows[(coll, key)] = row
        return row

    async def find(self, coll, where, **kw):
        return [], None


class C:
    def __init__(self, store, catalogue):
        self.datastore = store
        self.catalogue = catalogue


async def resolve(store, catalogue, tenant="t1"):
    from app.api.internal import _service_config
    return await _service_config(C(store, catalogue), tenant)


def test_the_catalogue_answers_where_the_owner_has_not(monkeypatch):
    """The whole defect: a 10-day wash was being reminded at 90."""
    cat = FakeCatalogue({"svc_wash": 10.0, "svc_full": 21.0})
    got = run(resolve(FakeStore(), cat))

    assert got["svc_wash"]["cycle_days"] == 10.0
    assert got["svc_full"]["cycle_days"] == 21.0
    # AND THE SERVICES ARRIVE AT ALL. The config used to be built only from services the tree or a
    # live rule already knew, so a shop that configured nothing produced an EMPTY map — every
    # service falling through to the default.
    assert set(got) >= {"svc_wash", "svc_full"}


def test_what_the_owner_set_himself_beats_his_catalogue():
    """He changed «غسيل خارجي» to 14 days on his own screen. That is a decision, not a default —
    and a catalogue value that overrode it would silently undo what he did."""
    store = FakeStore({("reminder_settings", "t1|settings"): {
        "id": "t1", "tenant": "t1",
        "services": {"svc_wash": {"interval_days": 14}},
        "groups": {}, "service_group": {}, "general": {}}})
    got = run(resolve(store, FakeCatalogue({"svc_wash": 10.0})))
    assert got["svc_wash"]["cycle_days"] == 14


def test_a_shop_wide_setting_also_beats_the_catalogue():
    """«ذكّرهم كل 30 يوماً» applies to everything he did not single out — the tree's `general`
    level is his too, and only our own default may be replaced."""
    store = FakeStore({("reminder_settings", "t1|settings"): {
        "id": "t1", "tenant": "t1", "services": {}, "groups": {}, "service_group": {},
        "general": {"interval_days": 30}}})
    got = run(resolve(store, FakeCatalogue({"svc_wash": 10.0})))
    assert got["svc_wash"]["cycle_days"] == 30


def test_an_unreachable_catalogue_falls_back_rather_than_refusing():
    """operations restarting must not stop a tick, and must not produce a zero cycle — zero means
    «no natural cycle» to the scheduler, which would cancel the reminder outright."""
    got = run(resolve(FakeStore(), FakeCatalogue(boom=True)))
    assert got == {} or all(v["cycle_days"] > 0 for v in got.values())


def test_a_service_with_no_cycle_stays_without_one():
    """A puncture repair has no natural cycle. Reading the catalogue must not invent one for it."""
    got = run(resolve(FakeStore(), FakeCatalogue({"svc_patch": 0.0, "svc_wash": 10.0})))
    assert "svc_patch" not in got
    assert got["svc_wash"]["cycle_days"] == 10.0


def test_an_interval_nobody_learned_follows_the_corrected_cycle():
    """A rule born while the engine still defaulted to 90 must not keep 90 for ever.

    The row on the cluster was created before the catalogue was read, so it holds `interval_days:
    90.0` for a service whose shop says 10 — the guess outliving the correction. Until there is a
    real observation, the configured cycle owns the number.
    """
    import time

    from app.core.scheduling import Scheduler

    class Rules:
        def __init__(self, row):
            self.row = row
            self.saved = None

        async def get(self, key):
            return self.row

        async def upsert(self, tenant, key, row):
            self.saved = row
            return row

    now = int(time.time())
    # Never learned: created with the old default, no observations, and no earlier visit.
    stale = {"interval_days": 90.0, "observations": 0, "last_visit_at": 0}
    s = Scheduler.__new__(Scheduler)
    s._rules = Rules(stale)
    s._default = 90.0
    from app.core.adaptive import AdaptiveConfig
    s._cfg = AdaptiveConfig()

    interval, learned, anomaly = run(
        s._learn("t1", "sub_1", "svc_wash", occurred=now, svc={"cycle_days": 10}))
    assert interval == 10, "the corrected cycle must win over a guess nobody ever confirmed"

    # And a rule that HAS learned keeps what it learned — the customer's own rhythm outranks any
    # configured number, which is the whole point of learning it.
    learned_row = {"interval_days": 30.0, "observations": 4, "last_visit_at": 0}
    s._rules = Rules(learned_row)
    interval, _, _ = run(
        s._learn("t1", "sub_1", "svc_wash", occurred=now, svc={"cycle_days": 10}))
    assert interval == 30
