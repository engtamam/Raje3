"""`Service.duration_minutes` — the field docs/خطة-تنفيذ-الحجوزات.md §0 added for bookings.

0 IS NOT CONFIGURED, NEVER A GUESSED LENGTH. `cycle_days` already refuses to default to 30 for
this exact reason (a puncture repair must not get a reminder invented for it); duration_minutes
is the same defect family — a shop that has not set it must not have a length silently invented
for its services, because bookings would then compute a real slot out of a number nobody chose.

THIS FILE PROVES THE ROUND-TRIP, NOTHING MORE. Whether bookings actually refuses to schedule
against a zero duration is bookings' own test, once that service exists — this only proves the
catalogue carries the value honestly: unset stays 0, set stays set, `public()` never drops it.
"""
from __future__ import annotations

from app.core.models import Service as _Service


def test_an_unset_duration_is_zero_not_a_guess():
    s = _Service(id="srv_cut", tenant="t1", name="قص شعر")
    assert s.duration_minutes == 0


def test_a_set_duration_round_trips_through_public():
    s = _Service(id="srv_cut", tenant="t1", name="قص شعر", duration_minutes=30)
    assert s.public()["duration_minutes"] == 30


def test_an_unset_duration_appears_in_public_as_zero_not_absent():
    # A field silently absent from public() is indistinguishable from one that was dropped — the
    # console must be able to tell "not configured" (0, present) from "field doesn't exist yet".
    s = _Service(id="srv_cut", tenant="t1", name="قص شعر")
    assert "duration_minutes" in s.public()
    assert s.public()["duration_minutes"] == 0
