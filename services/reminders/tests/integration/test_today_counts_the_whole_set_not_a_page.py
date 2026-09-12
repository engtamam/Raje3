"""reminders-r2-002 (QA audit round 2, 2026-09-12): `/reminders/today` derived its `waiting`/
`retrying`/`sent_today` counts from a single `limit=200` read of `pending`/`sent` and treated that
page as the total — the same "page treated as a count" bug class already found and fixed elsewhere
this session. A shop with more than 200 rows pending had this screen answer for its first 200 and
call that the whole picture; a busy establishment is exactly the one that most needs an honest
count.

Fixed by paging (`app.api.v1.owner._counted`) until exhausted, capped at `_COUNT_CAP` for safety
and reporting `messages.truncated` when that cap is hit rather than silently returning a partial
count as if it were complete.

THROUGH THE ROUTE, NOT AROUND IT, same as the neighbouring stuck/calm test this file sits beside.
"""
from __future__ import annotations

import asyncio
import os

import pytest

from app.config import get_settings
from app.core.models import Schedule, as_row
from app.core.stores import ScheduleStore

from test_auth_rbac import _auth, _make_app, _token


@pytest.fixture
def app_client():
    saved = dict(os.environ)
    try:
        yield _make_app()
    finally:
        os.environ.clear()
        os.environ.update(saved)
        get_settings.cache_clear()


def _seed_many(client, n: int, *, prefix: str = "sub") -> None:
    store = ScheduleStore(client.app.state.container.datastore)

    async def _put_all():
        for i in range(n):
            s = Schedule(tenant="t1", subject_ref=f"{prefix}_{i}", service_id="oil",
                         kind="reminder", due_at=1_781_000_000 + i, cls="service",
                         template_type="svc_service_reminder")
            await store.upsert("t1", s.key, as_row(s))

    asyncio.new_event_loop().run_until_complete(_put_all())


def _today(client) -> dict:
    r = client.get("/api/v1/reminders/today",
                   headers=_auth(_token(caps=["reminders.read"], tenant="t1")))
    assert r.status_code == 200, r.text
    return r.json()


def test_more_than_a_page_of_pending_rows_is_still_counted_honestly(app_client):
    """THE WHOLE DEFECT IN ONE ASSERTION: a `limit=200` read used to make this say 200 no matter
    how many rows were actually pending. 250 is chosen deliberately over the old page size."""
    _seed_many(app_client, 250)
    msgs = _today(app_client)["messages"]
    assert msgs["waiting"] == 250, "a page was mistaken for the whole pending set"
    assert msgs["truncated"] is False, "well under the safety cap — this must not read as cut off"


def test_a_calm_small_queue_reports_no_truncation(app_client):
    _seed_many(app_client, 3)
    msgs = _today(app_client)["messages"]
    assert msgs["waiting"] == 3
    assert msgs["truncated"] is False
