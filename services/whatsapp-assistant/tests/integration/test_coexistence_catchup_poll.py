"""CoexistencePoller — the durable catch-up sweep against notification-service's
GET /internal/whatsapp/coexistence/echoes (platform v0.18.56).

THE GUARANTEE THIS FILE EXISTS TO PROVE: an echo the sweep reads makes the owner "active" for that
customer via owner_presence, the cursor only advances after that write lands, and a feed that could
not be reached ({}) never gets read as "no echoes" — see the module docstring for why.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from app.adapters.datastore.memory import MemoryDataStore
from app.core.coexistence_poll import CoexistencePoller
from app.core.owner_presence import is_owner_active


def run(c):
    return asyncio.run(c)


@dataclass
class _Settings:
    COEXISTENCE_HUMAN_COOLDOWN_SECONDS: int = 1800


@dataclass
class _Container:
    datastore: MemoryDataStore
    coexistence_feed: object = None


class _FakeFeed:
    """Paginates a fixed list of echo rows, one page per call, cursor = row index."""
    configured = True

    def __init__(self, rows: list[dict]):
        self._rows = rows
        self.calls: list[str] = []

    async def echoes(self, *, after: str = ""):
        self.calls.append(after)
        start = int(after or 0)
        page = self._rows[start:start + 1]
        if not page:
            return {"messages": [], "cursor": after}
        return {"messages": page, "cursor": str(start + 1)}


class _UnreachableFeed:
    configured = True

    async def echoes(self, *, after: str = ""):
        return {}


class _OffFeed:
    configured = False

    async def echoes(self, *, after: str = ""):
        return {}


def _container(feed) -> _Container:
    return _Container(datastore=MemoryDataStore(), coexistence_feed=feed)


def test_configured_off_reports_it_rather_than_zeros_that_read_as_caught_up():
    c = _container(_OffFeed())
    result = run(CoexistencePoller(container=c, settings=_Settings(), logger=_NullLog()).run(now=1000))
    assert result == {"read": 0, "noted": 0, "pages": 0, "configured": False}


def test_an_unreachable_feed_holds_the_watermark_still():
    c = _container(_UnreachableFeed())
    result = run(CoexistencePoller(container=c, settings=_Settings(), logger=_NullLog()).run(now=1000))
    assert result["unreadable"] is True
    assert run(c.datastore.get("wa_coexistence_watermarks", "echo_poll")) is None


def test_an_echo_makes_the_owner_active_for_that_customer():
    feed = _FakeFeed([{"tenant": "t1", "contact": "+9665", "wamid": "wamid_1"}])
    c = _container(feed)
    result = run(CoexistencePoller(container=c, settings=_Settings(), logger=_NullLog()).run(now=1000))
    assert result["read"] == 1 and result["noted"] == 1
    assert run(is_owner_active(c, tenant="t1", contact="+9665", now=1000)) is True
    assert run(is_owner_active(c, tenant="t1", contact="+9665", now=1000 + 1800)) is False


def test_a_row_missing_tenant_or_contact_is_read_but_never_noted():
    feed = _FakeFeed([{"tenant": "", "contact": "+9665", "wamid": "wamid_1"},
                      {"tenant": "t1", "contact": "", "wamid": "wamid_2"}])
    c = _container(feed)
    result = run(CoexistencePoller(container=c, settings=_Settings(), logger=_NullLog()).run(now=1000))
    assert result["read"] == 2 and result["noted"] == 0


def test_zero_cooldown_polls_but_notes_nothing_never_silences_forever():
    feed = _FakeFeed([{"tenant": "t1", "contact": "+9665", "wamid": "wamid_1"}])
    c = _container(feed)
    settings = _Settings(COEXISTENCE_HUMAN_COOLDOWN_SECONDS=0)
    result = run(CoexistencePoller(container=c, settings=settings, logger=_NullLog()).run(now=1000))
    assert result["noted"] == 0
    assert run(is_owner_active(c, tenant="t1", contact="+9665", now=1000)) is False


def test_the_cursor_advances_across_pages_and_a_second_run_resumes_from_it():
    feed = _FakeFeed([{"tenant": "t1", "contact": "+9665", "wamid": "w1"},
                      {"tenant": "t1", "contact": "+9666", "wamid": "w2"}])
    c = _container(feed)
    poller = CoexistencePoller(container=c, settings=_Settings(), logger=_NullLog())
    first = run(poller.run(now=1000))
    assert first["read"] == 2 and first["pages"] == 2
    assert feed.calls == ["", "1", "2"]

    # A second run against the same (now-exhausted) feed reads nothing new — the cursor held.
    second = run(poller.run(now=2000))
    assert second["read"] == 0
    assert feed.calls[-1] == "2"


class _NullLog:
    def info(self, *a, **kw):
        pass

    def warning(self, *a, **kw):
        pass
