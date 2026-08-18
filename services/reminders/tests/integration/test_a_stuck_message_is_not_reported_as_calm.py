"""«هل كل شيء يعمل؟» must not answer «2 في الانتظار» about a message that is failing.

WHAT CHANGED UNDER THE NUMBER. `pending` used to mean one thing: a reminder booked for later. It
now holds two — that, and a message whose pass threw, which goes back to `pending` an hour out with
its `attempts` raised. A number Meta refuses, a template rejected for this shop alone, a peer that
is down: all of them sit in `pending` looking exactly like next Tuesday's reminder.

So the screen NAMED after «is everything working» counted a shop whose every message was failing as
a shop with a calm queue. It already refuses to render an unknown ceiling as a zero and an
unreadable establishment name as calm; this is the same rule one field further along.

THROUGH THE ROUTE, NOT AROUND IT. A test that recomputed the split itself would pass with the
endpoint untouched — it would be asserting its own arithmetic. This drives `/today` and reads what
the console reads.
"""
from __future__ import annotations

import os

import pytest

from app.config import get_settings

from app.core.models import Schedule, as_row
from app.core.stores import ScheduleStore

from test_auth_rbac import _auth, _make_app, _token


@pytest.fixture
def app_client():
    """A fresh app per test — AND THE ENVIRONMENT PUT BACK AFTERWARDS.

    `_make_app` writes into `os.environ` and clears the settings cache, which is what makes it
    useful and what makes it leak: without this restore, the next test file in the run reads this
    file's settings. It cost a green suite once already — `test_ports_hardening` failed in the
    full run and passed alone, which is the signature of exactly this and of nothing else.
    """
    saved = dict(os.environ)
    try:
        yield _make_app()
    finally:
        os.environ.clear()
        os.environ.update(saved)
        get_settings.cache_clear()


def _seed(client, subject: str, *, attempts: int = 0, drop_field: bool = False) -> None:
    """Put one pending schedule into the app's own datastore."""
    import asyncio

    store = ScheduleStore(client.app.state.container.datastore)
    s = Schedule(tenant="t1", subject_ref=subject, service_id="oil", kind="reminder",
                 due_at=1_781_000_000, cls="service", template_type="svc_service_reminder",
                 attempts=attempts)
    row = as_row(s)
    if drop_field:
        # A ROW WRITTEN BEFORE THE FIELD EXISTED. Reading a missing key as «stuck» would move
        # every schedule in the fleet into the warning column on the day this ships.
        row.pop("attempts", None)
    asyncio.new_event_loop().run_until_complete(store.upsert("t1", s.key, row))


def _today(client) -> dict:
    r = client.get("/api/v1/reminders/today",
                   headers=_auth(_token(caps=["reminders.read"], tenant="t1")))
    assert r.status_code == 200, r.text
    return r.json()["messages"]


def test_a_calm_queue_is_all_waiting(app_client):
    _seed(app_client, "sub_a")
    _seed(app_client, "sub_b")
    msgs = _today(app_client)
    assert msgs["waiting"] == 2
    assert msgs["retrying"] == 0
    # NOTHING IS SAID WHEN NOTHING IS WRONG. A warning that is always on screen is furniture.
    assert msgs["retrying_reason"] == ""


def test_a_message_that_has_thrown_is_not_counted_as_waiting(app_client):
    _seed(app_client, "sub_a")
    _seed(app_client, "sub_b", attempts=11)
    msgs = _today(app_client)
    # THE WHOLE DEFECT IN ONE ASSERTION: this used to read 2, and the shop with a failing message
    # saw the same screen as the shop with none.
    assert msgs["waiting"] == 1
    assert msgs["retrying"] == 1
    assert "تحاول الخروج ولا تنجح" in msgs["retrying_reason"]


def test_a_shop_whose_every_message_is_failing_reports_none_as_waiting(app_client):
    for i in range(5):
        _seed(app_client, f"sub_{i}", attempts=3)
    msgs = _today(app_client)
    assert msgs["waiting"] == 0
    assert msgs["retrying"] == 5


def test_a_row_written_before_the_field_existed_is_calm_not_stuck(app_client):
    _seed(app_client, "sub_old", drop_field=True)
    msgs = _today(app_client)
    assert msgs["waiting"] == 1
    assert msgs["retrying"] == 0
