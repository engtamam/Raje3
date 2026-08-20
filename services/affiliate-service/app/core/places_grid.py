# =============================================================================
# affiliate-service — the Grid algorithm, ported from places_scraper_v2.py verbatim (Tamam's own
# "مجرَّب على أرض الواقع" script) — pure math, zero I/O, so it is testable without a single HTTP
# call and without touching the rest of the search-job machinery in core/lead_sourcing.py.
# =============================================================================
from __future__ import annotations

import math


def generate_grid(lat: float, lng: float, w_km: float, h_km: float,
                  step_km: float) -> list[tuple[float, float]]:
    """Every grid point covering a w_km × h_km box centred on (lat, lng), step_km apart —
    identical to places_scraper_v2.py's own `generate_grid`. The caller (core/lead_sourcing.py)
    passes `step_km = radius_km * 1.5`, the script's own deliberate overlap for full coverage."""
    points: list[tuple[float, float]] = []
    lat_step = step_km / 111.0
    lng_step = step_km / (111.0 * math.cos(math.radians(lat)))
    lat_range = h_km / 111.0
    lng_range = w_km / (111.0 * math.cos(math.radians(lat)))
    cur_lat = lat - lat_range / 2
    while cur_lat <= lat + lat_range / 2:
        cur_lng = lng - lng_range / 2
        while cur_lng <= lng + lng_range / 2:
            points.append((round(cur_lat, 6), round(cur_lng, 6)))
            cur_lng += lng_step
        cur_lat += lat_step
    return points


def split_offsets(radius_km: float) -> list[tuple[float, float]]:
    """The 4 sub-point offsets places_scraper_v2.py's own `fetch_with_autosplit` uses when a
    point returns the max page size (more places than one query can see) — a quadrant split
    around the original point, same 0.4×radius/111 formula."""
    offset = radius_km * 0.4 / 111.0
    return [(offset, offset), (offset, -offset), (-offset, offset), (-offset, -offset)]


def matches_indicators(name: str, indicators: list[str]) -> bool:
    """places_scraper_v2.py's own `is_female_place`, generalised: the manager supplies HIS OWN
    indicator words at search time (spec §12 — this service stays generic, so "نسائي"/"ladies"
    are search parameters here, never hardcoded defaults) rather than one fixed list. An empty
    `indicators` list means no filter — everything matches."""
    if not indicators:
        return True
    lowered = name.lower()
    return any(ind.lower() in lowered for ind in indicators)
