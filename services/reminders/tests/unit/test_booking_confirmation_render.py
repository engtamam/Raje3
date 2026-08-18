"""`svc_booking_confirmation` at render time — the one slot this template does NOT share with
`svc_visit_confirmation`'s shape: slot 3 is the appointment's day and hour, never the raw
`service_id` a booking schedule repurposes to hold `booking_id` (see Scheduler.on_booking).
"""
from __future__ import annotations

import asyncio
from datetime import datetime

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core import engagement as E
from app.core import gate as G
from app.core.models import Schedule, as_row
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


LIB = [{"name": "svc_booking_confirmation_brief", "type": "svc_booking_confirmation",
        "tone": "brief", "class": "service", "variables": [1, 2, 3, 4],
        "fills": ["system", "system", "system", "invite"], "active": True, "deferral": "drop"}]


def test_slot_3_is_the_appointment_time_not_the_booking_id():
    st = MemoryDataStore()
    row = Schedule(tenant="t1", subject_ref="sub_a", service_id="bkg_1",
                   kind="booking_confirmation", due_at=at(9), cls="service",
                   template_type="svc_booking_confirmation", appt_time="الأحد 9:00 مساءً",
                   booking_id="bkg_1")
    run(ScheduleStore(st).upsert(row.tenant, row.key, as_row(row)))

    sender = FakeSender()
    tick = Tick(store=st, sender=sender, limits=G.Limits(), eng_cfg=ECFG,
               public_base_url="https://my.example.sa")
    run(tick.run("t1", now=at(10), library=LIB, service_names={}, establishment="ورشة النخبة",
                customer_names={"sub_a": "أحمد"}))

    assert len(sender.calls) == 1
    variables = sender.calls[0]["variables"]
    assert variables[2] == "الأحد 9:00 مساءً", (
        f"slot 3 must be the appointment time, got {variables[2]!r} — a booking_id leaking into "
        f"a customer-facing message")
