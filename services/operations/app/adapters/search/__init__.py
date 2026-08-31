"""Indexing customers so the field screen can find them.

A PORT WITH DRIVERS, like every other outbound dependency, and for the usual reason: the `null`
driver is what lets the whole service be tested without a search-service in the room, and the
`http` driver is what talks to the real one. Neither is chosen in code — `SEARCH_DRIVER` decides.

WHAT WE LEARNED ABOUT THE PEER, and why the keypad is built the way it is (measured on a running
cluster, recorded in deploy/services/search-service.values.yaml):

  POST /api/v1/search          matches WHOLE TOKENS. A phone matches only in full: `966501234567`
                               hits, `96650` does not. Typo tolerance is edit-distance 1 and does
                               not bridge a truncation.
  GET  /api/v1/search/suggest  matches a PREFIX, and its parameter is `prefix`, not `q`.

So the keypad calls SUGGEST. Wiring it to search would let an operator type five correct digits,
see nothing, and tell a customer standing in front of him that he is not registered.

The index request takes `fields`, not `doc`. Sending `doc` returns 201 and indexes an EMPTY
document — the unknown key is dropped, the write looks successful, and every later search returns
nothing.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any
from app.adapters import internal_http


class NullSearch:
    """Indexes nothing, and says so.

    Correct for tests and for a local run. NOT correct in production, where it would mean a screen
    that silently cannot find anybody — which is why the boot guard in config.py refuses it there.
    """
    driver = "null"

    async def index(self, *, index: str, doc_id: str, tenant: str,
                    fields: dict[str, Any]) -> bool:
        return False

    async def suggest(self, *, index: str, tenant: str, prefix: str) -> list[str] | None:
        # None, NOT []. An empty list is «nobody matched» and None is «I could not ask» — and the
        # caller draws a different sentence for each. See the route in api/v1/field.py.
        return None

    async def query(self, *, index: str, tenant: str, text: str,
                    size: int) -> list[dict[str, Any]] | None:
        return None


class HttpSearch:
    """The real one. stdlib urllib, matching the other internal clients — no extra runtime
    dependency and a leaner image."""
    driver = "http"

    def __init__(self, *, url: str, token: str, path: str, timeout: int = 5,
                 suggest_path: str = "/api/v1/search/suggest",
                 query_path: str = "/api/v1/search") -> None:
        self._url = url.rstrip("/")
        self._token = token
        self._path = path
        self._suggest_path = suggest_path
        self._query_path = query_path
        self._timeout = timeout

    async def index(self, *, index: str, doc_id: str, tenant: str,
                    fields: dict[str, Any]) -> bool:
        body = json.dumps({
            "index": index,
            "id": doc_id,
            "tenant": tenant,
            # `fields`, NOT `doc`. See the module docstring — the wrong key returns 201 and
            # indexes nothing.
            "fields": fields,
        }).encode()
        try:
            # Built in adapters/internal_http.py, the one place this service attaches the token.
            status, _ = internal_http.send(
                f"{self._url}{self._path}", timeout=self._timeout, method="POST", body=body,
                content_type=internal_http.JSON, token=self._token)
            return 200 <= status < 300
        except (urllib.error.HTTPError, urllib.error.URLError, OSError):
            # Never raises. This runs after the operator has been answered, and a search hiccup
            # must not surface as a failed visit. The caller records the failure (core/seams.py).
            return False

    def _get(self, path: str) -> Any:
        req = urllib.request.Request(
            f"{self._url}{path}", method="GET",
            headers={"X-Internal-Token": self._token})
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:  # nosec B310
            return json.loads(resp.read() or b"{}")

    def _post(self, path: str, body: dict[str, Any]) -> Any:
        req = urllib.request.Request(
            f"{self._url}{path}", data=json.dumps(body).encode(), method="POST",
            headers={"Content-Type": "application/json", "X-Internal-Token": self._token})
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:  # nosec B310
            return json.loads(resp.read() or b"{}")

    async def suggest(self, *, index: str, tenant: str, prefix: str) -> list[str] | None:
        """The prefix half, spoken to the peer in ITS shape — `prefix`, never `q` (ط-3).

        THE READING SIDE EXISTS SO THE BROWSER STOPS DOING IT. The console called the platform's
        search routes itself: `/suggest` answers phone NUMBERS, which are personal data on their
        own, and `POST /search` answers PEOPLE. Neither knows what a branch is, so a supervisor in
        Jeddah typed four digits and read Riyadh's customers by name, number and plate — and it
        walked around every narrowing already built into this file, because the keypad never asked
        us at all. A filter chosen by the browser is decoration; the narrowing has to happen on a
        route the browser cannot talk past.
        """
        q = urllib.parse.urlencode({"index": index, "tenant": tenant, "prefix": prefix})
        try:
            out = self._get(f"{self._suggest_path}?{q}")
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
            # A READ THAT DID NOT HAPPEN IS NOT AN EMPTY SHOP. `None` travels all the way to the
            # screen, which says «تعذّر البحث» rather than «لا يوجد عميل» — the one wrong answer
            # this screen must never give to a man standing at the counter.
            return None
        terms = out.get("suggestions") if isinstance(out, dict) else None
        return [t for t in (terms or []) if isinstance(t, str) and t]

    async def query(self, *, index: str, tenant: str, text: str,
                    size: int) -> list[dict[str, Any]] | None:
        """Whole-token search: the peer matches complete tokens, so the terms come from `suggest`."""
        try:
            out = self._post(self._query_path, {"index": index, "tenant": tenant, "text": text,
                                                "size": size, "highlight": False})
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
            return None
        hits = out.get("hits") if isinstance(out, dict) else None
        return [h for h in (hits or []) if isinstance(h, dict)]


_DRIVERS = {"null": NullSearch, "http": HttpSearch}


def build_search(settings) -> Any:
    driver = settings.SEARCH_DRIVER
    if driver not in _DRIVERS:
        # Fail fast and name the options. An unknown driver silently falling back to null would be
        # a service that indexes nothing and reports nothing.
        raise ValueError(f"unknown SEARCH_DRIVER {driver!r} — one of {sorted(_DRIVERS)}")
    if driver == "null":
        return NullSearch()
    return HttpSearch(url=settings.SEARCH_SERVICE_URL, token=settings.INTERNAL_SERVICE_TOKEN,
                      path=settings.SEARCH_INDEX_PATH, timeout=settings.SEARCH_TIMEOUT_SECONDS,
                      suggest_path=settings.SEARCH_SUGGEST_PATH,
                      query_path=settings.SEARCH_QUERY_PATH)
