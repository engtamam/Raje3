"""أ-5 · the service NAME, from the answer it always arrived in.

THE CHAIN. Operations' catalogue feed has always answered `{"id", "name", "cycle_days", …}`. This
service's adapter read the number and dropped the word on the next line. `_service_config` then
built an entry per service with no `name` in it, and the tick — which renders EVERY message from
that config, `service_names={k: v.get("name", k) …}` — fell through to its own fallback. The
fallback WAS the behaviour: «تذكير بخصوص svc_7f3a…», to every customer of every shop, for every
service.

Nothing failed. The message sent, the ledger recorded it, and the only witness was a customer
reading a database key in a WhatsApp message from his mechanic.
"""
from __future__ import annotations

import asyncio
import json


class _Feed:
    """The catalogue endpoint, answering the way it really does."""

    def __init__(self, rows):
        self.rows = rows
        self.calls = 0


def _adapter(feed, monkeypatch):
    from app.core import rendering as R

    cat = R.ShopCatalogue(url="http://ops.invalid", path="/internal/services", token="t" * 40)

    class _Resp:
        def __init__(self, payload):
            self._payload = payload

        def read(self):
            return json.dumps(self._payload).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def _open(req, timeout=0):
        feed.calls += 1
        return _Resp({"services": feed.rows})

    monkeypatch.setattr("urllib.request.urlopen", _open)
    return cat


def test_the_name_survives_the_adapter(monkeypatch):
    feed = _Feed([{"id": "svc_7f3a", "name": "غسيل خارجي", "cycle_days": 10},
                  {"id": "svc_punc", "name": "تصليح بنشر", "cycle_days": 0}])
    cat = _adapter(feed, monkeypatch)

    assert asyncio.run(cat.names("t1")) == {"svc_7f3a": "غسيل خارجي", "svc_punc": "تصليح بنشر"}


def test_a_service_with_no_rhythm_still_has_a_name_and_still_has_no_cycle(monkeypatch):
    """The two answers are filtered differently on purpose: zero means «no natural cycle» to the
    scheduler and must keep meaning that, while a puncture repair is still a thing with a name."""
    feed = _Feed([{"id": "svc_punc", "name": "تصليح بنشر", "cycle_days": 0}])
    cat = _adapter(feed, monkeypatch)

    assert asyncio.run(cat.cycles("t1")) == {}
    assert asyncio.run(cat.names("t1")) == {"svc_punc": "تصليح بنشر"}


def test_both_answers_come_from_ONE_read(monkeypatch):
    """A second round trip per tenant per tick, for a field already in the first response, is the
    kind of cost that gets a cache added and then gets the cache wrong."""
    feed = _Feed([{"id": "svc_7f3a", "name": "غسيل خارجي", "cycle_days": 10}])
    cat = _adapter(feed, monkeypatch)

    asyncio.run(cat.cycles("t1"))
    asyncio.run(cat.names("t1"))

    assert feed.calls == 1


def test_the_config_the_tick_renders_from_carries_the_name(monkeypatch):
    """THE SECOND LINK, and the one that made the first invisible. `_service_config` builds the
    entry the tick reads its words out of; it had a cycle, a lead, a follow-up and a switch, and
    no name — so the adapter could have carried the word all along and nothing would have used it.
    """
    from app.api import internal as I

    class _Cat:
        async def cycles(self, tenant):
            return {"svc_7f3a": 10.0}

        async def names(self, tenant):
            return {"svc_7f3a": "غسيل خارجي"}

    class _Store:
        async def find(self, *a, **kw):
            return [], None

        async def get(self, *a, **kw):
            return None

    class _C:
        catalogue = _Cat()
        datastore = _Store()

    cfg = asyncio.run(I._service_config(_C(), "t1"))

    assert cfg["svc_7f3a"]["name"] == "غسيل خارجي"
    # AND HIS CYCLE STILL WINS over our default — the fix beside this one must not be undone.
    assert cfg["svc_7f3a"]["cycle_days"] == 10.0


def test_a_service_the_catalogue_does_not_list_is_named_EMPTY_not_keyed(monkeypatch):
    """Putting `sid` here would push our primary key one step closer to a customer's screen, and
    would make «we have no name for this» indistinguishable from a name that happens to look like
    an identifier. The reader decides what to do with blank; this layer does not decide for it."""
    from app.api import internal as I

    class _Cat:
        async def cycles(self, tenant):
            return {}

        async def names(self, tenant):
            return {}

    class _Store:
        async def find(self, *a, **kw):
            return [{"tenant": "t1", "service_id": "svc_gone"}], None

        async def get(self, *a, **kw):
            return None

    class _C:
        catalogue = _Cat()
        datastore = _Store()

    cfg = asyncio.run(I._service_config(_C(), "t1"))
    assert cfg["svc_gone"]["name"] == ""


def test_a_failure_fetching_the_WORDS_does_not_discard_the_CYCLES():
    """The two reads share a source and must not share a fate.

    Written because the first version of this fix put both in one `try`: an adapter that could not
    answer `names` — an older one, or a peer that fell over between the calls — threw away cycles
    that had already arrived, and every service in the shop fell back to the platform's 90 days.
    That is the defect the catalogue read exists to close, reintroduced by the fix beside it.
    Losing a name costs a worse sentence; losing a cycle costs the schedule.
    """
    from app.api import internal as I

    class _Cat:
        async def cycles(self, tenant):
            return {"svc_7f3a": 10.0}

        async def names(self, tenant):
            raise RuntimeError("operations is down")

    class _Store:
        async def find(self, *a, **kw):
            return [], None

        async def get(self, *a, **kw):
            return None

    class _C:
        catalogue = _Cat()
        datastore = _Store()

    cfg = asyncio.run(I._service_config(_C(), "t1"))
    assert cfg["svc_7f3a"]["cycle_days"] == 10.0
    assert cfg["svc_7f3a"]["name"] == ""
