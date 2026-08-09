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
import urllib.request
from typing import Any


class NullSearch:
    """Indexes nothing, and says so.

    Correct for tests and for a local run. NOT correct in production, where it would mean a screen
    that silently cannot find anybody — which is why the boot guard in config.py refuses it there.
    """
    driver = "null"

    async def index(self, *, index: str, doc_id: str, tenant: str,
                    fields: dict[str, Any]) -> bool:
        return False


class HttpSearch:
    """The real one. stdlib urllib, matching the other internal clients — no extra runtime
    dependency and a leaner image."""
    driver = "http"

    def __init__(self, *, url: str, token: str, path: str, timeout: int = 5) -> None:
        self._url = url.rstrip("/")
        self._token = token
        self._path = path
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
        req = urllib.request.Request(
            f"{self._url}{self._path}", data=body, method="POST",
            headers={"Content-Type": "application/json", "X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:  # nosec B310
                return 200 <= resp.status < 300
        except (urllib.error.HTTPError, urllib.error.URLError, OSError):
            # Never raises. This runs after the operator has been answered, and a search hiccup
            # must not surface as a failed visit. The caller records the failure (core/seams.py).
            return False


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
                      path=settings.SEARCH_INDEX_PATH, timeout=settings.SEARCH_TIMEOUT_SECONDS)
