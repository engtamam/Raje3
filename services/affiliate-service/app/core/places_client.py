# =============================================================================
# affiliate-service — the Google Places calls, ported from places_scraper_v2.py's own
# `search_places`/`get_place_details`. Stdlib urllib only (same choice as core/onboarding.py's
# `Http`) — `requests` is not a dependency this template carries, and adding one for two GET
# calls is not worth the extra permissive-license surface to vet.
# =============================================================================
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

_NEARBY_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"
_DETAILS_FIELDS = ("name,formatted_phone_number,formatted_address,"
                   "opening_hours,website,url,rating,user_ratings_total,"
                   "vicinity,address_components")


class PlacesClient:
    def __init__(self, *, api_key: str, timeout: int = 10) -> None:
        self._key = api_key
        self._timeout = timeout

    def _get(self, url: str, params: dict[str, str]) -> dict:
        full = f"{url}?{urllib.parse.urlencode(params)}"
        try:
            with urllib.request.urlopen(full, timeout=self._timeout) as resp:  # nosec B310
                return json.loads(resp.read() or b"{}")
        except urllib.error.URLError:
            return {}
        except Exception:                                                     # noqa: BLE001
            return {}

    def search(self, *, lat: float, lng: float, radius_m: int, keyword: str,
              page_token: str = "") -> dict:
        params = {"location": f"{lat},{lng}", "radius": str(radius_m),
                  "keyword": keyword, "key": self._key, "language": "ar"}
        if page_token:
            params["pagetoken"] = page_token
        return self._get(_NEARBY_URL, params)

    def details(self, place_id: str) -> dict:
        params = {"place_id": place_id, "fields": _DETAILS_FIELDS,
                  "key": self._key, "language": "ar"}
        return self._get(_DETAILS_URL, params).get("result", {})
