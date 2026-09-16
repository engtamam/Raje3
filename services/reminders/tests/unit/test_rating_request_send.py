"""kind='rating_request' at actual send time — the piece that ties phases 1-3 together: the
rating_cta slot reflects the shop's OWN configured points, a ref is remembered
(`RatingRequestStore`) so the customer's answer on the hosted rating page can resolve back to
this exact visit, and the sender receives it as the template's URL-button parameter.
"""
from __future__ import annotations

import asyncio
from datetime import datetime

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core import engagement as E
from app.core import gate as G
from app.core.models import Schedule, as_row
from app.core.rating_cta import NO_POINTS
from app.core.rating_request import RatingRequestStore
from app.core.rating_settings import RatingSettingsStore
from app.core.stores import ScheduleStore
from app.core.tick import Tick

ECFG = E.EngagementConfig()


def run(c):
    return asyncio.run(c)


def at(hour, day=15):
    return int(datetime(2026, 6, day, hour, tzinfo=G.RIYADH).timestamp())


class FakeSender:
    def __init__(self) -> None:
        self.calls = []

    async def send(self, **kw):
        self.calls.append(kw)
        return "dlv_1"


LIB = [{"name": "svc_visit_confirmation_rating_masculine", "type": "svc_visit_confirmation_rating",
       "tone": "masculine", "class": "service", "variables": [1, 2, 3, 4],
       "fills": ["system", "system", "rating_cta", "invite"], "active": True, "deferral": "drop"}]


def _schedule(**over) -> Schedule:
    fields = dict(tenant="t1", subject_ref="sub_a", service_id="", kind="rating_request",
                 due_at=at(9), cls="service", template_type="svc_visit_confirmation_rating",
                 visit_id="vis_1")
    fields.update(over)
    return Schedule(**fields)


def _seed(st, row: Schedule) -> None:
    run(ScheduleStore(st).upsert(row.tenant, row.key, as_row(row)))


def _run_tick(st, sender):
    tick = Tick(store=st, sender=sender, limits=G.Limits(), eng_cfg=ECFG,
               public_base_url="https://my.raje3.sa")
    run(tick.run("t1", now=at(10), library=LIB, service_names={}, establishment="مغسلة النخيل",
                customer_names={"sub_a": "أحمد"}))


def test_the_rating_ref_is_sent_as_the_url_button_param_and_deterministic_on_the_visit_id():
    st = MemoryDataStore()
    _seed(st, _schedule())
    sender = FakeSender()
    _run_tick(st, sender)
    assert sender.calls[0]["url_button_param"] == "rate:vis_1"


def test_the_rating_ref_is_remembered_before_the_send(monkeypatch):
    st = MemoryDataStore()
    _seed(st, _schedule())
    _run_tick(st, FakeSender())
    pending = run(RatingRequestStore(st).resolve("rate:vis_1"))
    assert pending is not None
    assert pending.tenant == "t1"
    assert pending.subject_ref == "sub_a"
    assert pending.visit_id == "vis_1"


def test_rating_cta_names_the_shops_configured_points():
    st = MemoryDataStore()
    run(RatingSettingsStore(st).set("t1", points=7))
    _seed(st, _schedule())
    sender = FakeSender()
    _run_tick(st, sender)
    assert sender.calls[0]["variables"][2] == "شاركنا رأيك بزيارتك واكسب 7 نقطة"


def test_rating_cta_is_the_neutral_sentence_when_no_points_configured():
    st = MemoryDataStore()
    _seed(st, _schedule())
    sender = FakeSender()
    _run_tick(st, sender)
    assert sender.calls[0]["variables"][2] == NO_POINTS


def test_an_ordinary_kind_never_gets_a_url_button_param_or_touches_rating_request_store():
    st = MemoryDataStore()
    lib = [{"name": "svc_visit_confirmation_masculine", "type": "svc_visit_confirmation",
           "tone": "masculine", "class": "service", "variables": [1, 2, 3],
           "fills": ["system", "system", "invite"], "active": True, "deferral": "drop"}]
    row = Schedule(tenant="t1", subject_ref="sub_a", service_id="", kind="visit_confirmation",
                  due_at=at(9), cls="service", template_type="svc_visit_confirmation",
                  visit_id="vis_2")
    _seed(st, row)
    sender = FakeSender()
    tick = Tick(store=st, sender=sender, limits=G.Limits(), eng_cfg=ECFG,
               public_base_url="https://my.raje3.sa")
    run(tick.run("t1", now=at(10), library=lib, service_names={}, establishment="مغسلة النخيل",
                customer_names={"sub_a": "أحمد"}))
    assert sender.calls[0]["url_button_param"] == ""
    assert run(RatingRequestStore(st).resolve("rate:vis_2")) is None
