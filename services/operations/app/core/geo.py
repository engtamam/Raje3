"""Distance, and turning whatever a customer actually sends into a real coordinate.

HAVERSINE, DELIBERATELY NOT VINCENTY. Vincenty accounts for the Earth's ellipsoidal shape and is
the right tool past hundreds of kilometres — a delivery radius tops out at 100km (this module's own
`MAX_RADIUS_KM`), where the two formulas disagree by single-digit METRES, nowhere near the size of
a city block. The spherical law of cosines is the other classic option and is cheaper still, but is
ill-conditioned for exactly the short distances this module exists for (catastrophic cancellation
in the arccos near 0° — see the formula's own well-known numerical-stability problem); Haversine
avoids that failure mode and is the correct choice for this specific range, not merely the
convenient one.

TWO SOURCES OF COORDINATES, ONE RESULT SHAPE. A customer sharing WhatsApp's own native "send
location" feature already hands `whatsapp-assistant/app/core/inbound_parse.py` a real `(lat, lng)`
float pair directly — nothing in THIS module is involved for that path at all. What lands here is
the other case: a pasted Google Maps LINK (a branch's own owner setting its address, or a customer
who pasted a link instead of using the location button). `parse_google_maps_link` and
`resolve_google_maps_link` below are a straight Python port of `apps/console/src/googleMapsLink.ts`
— same patterns, same short-link limitation, same reasoning — kept in sync by hand on purpose
(the same "two copies, documented" posture `messages_model.dart`/`Messages.tsx` already take for
the goal↔template maps) because the frontend has no reason to call into a Python module and this
backend has no reason to import TypeScript.

`_resolve_short_link`'s ONE-REDIRECT-HOP, GOOGLE-HOSTS-ONLY SHAPE IS NOT NEW — it already shipped as
`api/v1/staff.py::_resolve_maps_short_link` for the owner's own branch-location paste. That
function now call THROUGH this module's copy instead of keeping a second implementation of the
same SSRF-sensitive logic — see this module's own `resolve_short_link`.
"""
from __future__ import annotations

import math
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.models import Branch

EARTH_RADIUS_KM = 6371.0088  # IUGG mean Earth radius — the standard constant for Haversine

MIN_RADIUS_KM = 0
MAX_RADIUS_KM = 100
DEFAULT_RADIUS_KM = 10


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in kilometres between two WGS-84 points. Accurate to within metres at
    delivery-radius scale (see module docstring on why Haversine, not Vincenty, is the right
    choice here — not merely the simplest one)."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    # `2 * atan2(sqrt(a), sqrt(1-a))`, NOT `2 * asin(sqrt(a))` — mathematically identical, but
    # `atan2` stays numerically well-behaved as `a` approaches 1 (antipodal points), where `asin`'s
    # derivative blows up. Irrelevant at delivery-radius scale, free to get right regardless.
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_KM * c


def within_radius_km(center_lat: float, center_lng: float, point_lat: float, point_lng: float,
                     radius_km: float) -> bool:
    return haversine_km(center_lat, center_lng, point_lat, point_lng) <= radius_km


def nearest_branch_for_point(branches: list["Branch"], *, lat: float, lng: float
                             ) -> "Branch | None":
    """WhatsApp Direct Ordering's own branch resolution (Step 4): among this tenant's active
    branches that can actually deliver to this exact point, the nearest one -- `None` when nobody
    can, which the caller reads as "outside every branch's delivery range" and refuses the order
    on, never guesses a branch for.

    THREE REASONS A BRANCH IS SKIPPED, NONE OF THEM "FARTHER THAN SOME OTHER ONE":
      * `not active` -- a closed branch is not a real delivery option today, same posture every
        other active-only read in this service already takes.
      * `lat == lng == 0.0` -- `Branch.lat`/`lng`'s own docstring: this is the UNSET sentinel
        (an owner who has never pinned a real address on the map), not a real point off the coast
        of west Africa. Haversine against it would return a real-looking, meaningless distance.
      * `delivery_radius_km <= 0` -- a deliberate "pickup only" choice (the same field's own
        docstring), never a branch this flow may silently assign a delivery to.

    TIE-BROKEN BY `id`, DETERMINISTICALLY -- two branches at the exact same distance (adjacent
    branches sharing a building, say) must not resolve to a different one on every call; sorting
    the id as the second key makes repeat calls for the identical point always agree.
    """
    candidates: list[tuple[float, str, "Branch"]] = []
    for b in branches:
        if not b.active:
            continue
        if b.lat == 0.0 and b.lng == 0.0:
            continue
        if b.delivery_radius_km <= 0:
            continue
        distance = haversine_km(b.lat, b.lng, lat, lng)
        if distance <= b.delivery_radius_km:
            candidates.append((distance, b.id, b))
    if not candidates:
        return None
    candidates.sort(key=lambda t: (t[0], t[1]))
    return candidates[0][2]


def clamp_radius_km(value: float) -> int:
    """A merchant-configured delivery radius, folded into the one range this product supports
    (0-100km, default 10 — see module constants). 0 is a real, valid choice (pickup-only, no
    delivery radius at all) — never silently rejected, only out-of-range values are folded in."""
    try:
        n = int(round(float(value)))
    except (TypeError, ValueError):
        return DEFAULT_RADIUS_KM
    return max(MIN_RADIUS_KM, min(MAX_RADIUS_KM, n))


# ── Google Maps links — a straight Python port of apps/console/src/googleMapsLink.ts ───────────

_SHORT_LINK_HOSTS = {"goo.gl", "maps.app.goo.gl"}

# Every shape Google's own share sheet and address bar actually produce, checked in the order a
# real link is most likely to match. Each capture group is (lat, lng) in that order — identical to
# googleMapsLink.ts's own PATTERNS, kept byte-for-byte equivalent on purpose.
_PATTERNS = (
    r"@(-?\d{1,3}\.\d+),(-?\d{1,3}\.\d+)",                 # .../@24.7136,46.6753,17z/...
    r"[?&]q=(-?\d{1,3}\.\d+),(-?\d{1,3}\.\d+)",            # ?q=24.7136,46.6753
    r"[?&]ll=(-?\d{1,3}\.\d+),(-?\d{1,3}\.\d+)",           # ?ll=24.7136,46.6753
    r"!3d(-?\d{1,3}\.\d+)!4d(-?\d{1,3}\.\d+)",             # !3d24.7136!4d46.6753
)

_COMPILED_PATTERNS = tuple(re.compile(p) for p in _PATTERNS)


def parse_google_maps_link(url: str) -> tuple[float, float] | None:
    """A pasted Google Maps link → (lat, lng), or `None` when the link carries no coordinates (or
    is a SHORT link — see `resolve_google_maps_link` for the one that also handles those)."""
    trimmed = (url or "").strip()
    if not trimmed:
        return None
    for pattern in _COMPILED_PATTERNS:
        m = pattern.search(trimmed)
        if not m:
            continue
        try:
            lat, lng = float(m.group(1)), float(m.group(2))
        except ValueError:
            continue
        if -90 <= lat <= 90 and -180 <= lng <= 180:
            return (lat, lng)
    return None


def is_short_google_maps_link(url: str) -> bool:
    try:
        host = (urllib.parse.urlparse((url or "").strip()).hostname or "").removeprefix("www.")
    except ValueError:
        return False
    return host in _SHORT_LINK_HOSTS


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Declines to follow — `urlopen` then raises `HTTPError` on the redirect status, which is the
    only way urllib hands back the `Location` header without actually fetching the page it points
    to. We want the coordinate hiding in the URL, never the page itself (same reasoning
    `api/v1/staff.py`'s own original copy of this class documented)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None


def resolve_short_link(url: str) -> str:
    """Follows ONE redirect hop of a Google Maps short link and returns where it landed, or `""`.

    RESTRICTED TO GOOGLE'S OWN SHORT-LINK HOSTS, NEVER AN ARBITRARY URL — an open "fetch whatever
    URL the caller names" function is a textbook SSRF door. `goo.gl`/`maps.app.goo.gl` are the only
    two hosts Google actually issues these short links from, and `https` is required: this will
    not follow a plaintext hop. BLOCKING I/O (urllib, same idiom `signup.py`'s own `Http` already
    uses) — callers on an event loop run this via `run_in_threadpool`/`asyncio.to_thread`, same as
    `api/v1/staff.py`'s own route already does.
    """
    parsed = urllib.parse.urlparse((url or "").strip())
    host = (parsed.hostname or "").removeprefix("www.")
    if parsed.scheme != "https" or host not in _SHORT_LINK_HOSTS:
        return ""
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        opener.open(url, timeout=5)
        return ""  # no redirect at all — nothing further to resolve
    except urllib.error.HTTPError as exc:
        if exc.code in (301, 302, 303, 307, 308):
            return exc.headers.get("Location") or ""
        return ""
    except OSError:
        return ""


def resolve_google_maps_link(url: str) -> tuple[float, float] | None:
    """The full pipeline: the cheap direct parse first, and only follow a redirect when the link is
    a short one. BLOCKING (see `resolve_short_link`'s own note) — a caller on an event loop must
    run this off it."""
    direct = parse_google_maps_link(url)
    if direct:
        return direct
    if not is_short_google_maps_link(url):
        return None
    resolved = resolve_short_link(url)
    return parse_google_maps_link(resolved) if resolved else None
