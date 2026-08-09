"""The shop's WhatsApp ceiling — read from Meta, never invented.

WHAT THIS REPLACES. Everything that needed the ceiling — the engine's reserve, the campaign spread,
the sentence that tells an owner where he stands — ran on a number configured in a values file. That
number was a guess about somebody else's system, and it was wrong from the moment Meta moved the
tier, which it does within about six hours of the conditions being met.

base-services v0.14.1 added the read after we escalated it:
`GET /internal/whatsapp/messaging-limit?tenant=` returns the live figure with a short cache.

────────────────────────────────────────────────────────────────────────────────────────────────
UNKNOWN IS A REAL ANSWER, AND IT IS NOT ZERO

The peer answers `unsupported` for a driver that cannot reach Meta, and reports `limit: 0` for
unknown. It refuses to fabricate a ceiling, which is the right call and one we have to honour
rather than paper over: a fabricated ceiling is worse than a known-unknown, because everything
downstream then plans confidently against fiction.

So `known()` is False and the callers fall back to their own behaviour — the sender keeps sending
and Meta enforces its own limit at the door. What we lose without the number is planning: a
reserve we cannot size and a campaign estimate we cannot show. What we must not lose is the
sending itself. A shop whose reminders stopped because WE could not read a number is our outage
wearing their ceiling.

────────────────────────────────────────────────────────────────────────────────────────────────
IT IS A PORTFOLIO CEILING, NOT A NUMBER'S

Meta caps at the portfolio level, shared across a WABA's phone numbers. So it is per TENANT here,
and a shop with two numbers does not get twice the allowance — which is exactly the assumption
somebody would otherwise make the first time an establishment adds a second line.

────────────────────────────────────────────────────────────────────────────────────────────────
AND THE QUALITY RATING PREDICTS THE DROP

GREEN / YELLOW / RED, from Meta. A tier falls after quality does, so YELLOW is the warning that
arrives before the ceiling moves — the only advance notice available, and worth carrying even
though nothing consumes it yet.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# What the peer answers with when it cannot reach Meta at all.
UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class Ceiling:
    """One establishment's business-initiated allowance, as Meta reports it."""

    limit: int = 0            # unique customers per rolling 24h; -1 unlimited, 0 unknown
    tier: str = ""            # Meta's raw code, kept verbatim so an unmapped tier is never lost
    quality: str = ""         # GREEN | YELLOW | RED | NA | UNKNOWN
    error: str = ""

    def known(self) -> bool:
        """Whether we may plan against it.

        UNLIMITED IS KNOWN. `-1` is a real answer — the largest tier — and treating it as unknown
        would make the biggest establishments the ones we plan worst for.
        """
        return self.limit != 0

    def unlimited(self) -> bool:
        return self.limit < 0

    def remaining(self, reached_today: int) -> int:
        """How many NEW people may still be started with today. -1 when there is no ceiling.

        `reached_today` is the unique-customer count from core/reach.py, because the ceiling counts
        people and not messages.
        """
        if self.unlimited():
            return -1
        if not self.known():
            return -1                    # unknown behaves as unbounded HERE — see the docstring
        return max(0, self.limit - max(0, reached_today))


class NullCeiling:
    """Answers unknown, always. Tests and any deployment without the peer configured."""

    driver = "null"

    async def read(self, tenant: str) -> Ceiling:
        return Ceiling()


class HttpCeiling:
    """notification-service's internal read. Cached by the peer, so this does not cache again.

    NOT CACHED HERE ON PURPOSE. The peer already holds it briefly and knows when its own read is
    stale; a second cache on our side would be a second staleness with a different clock, and the
    tier moves in hours.
    """

    driver = "http"

    def __init__(self, *, notify_url: str, path: str, token: str, timeout: int = 8) -> None:
        self._url = notify_url.rstrip("/") + path
        self._token = token
        self._timeout = timeout

    async def read(self, tenant: str) -> Ceiling:
        import json
        import urllib.error
        import urllib.parse
        import urllib.request

        query = urllib.parse.urlencode({"tenant": tenant})
        req = urllib.request.Request(f"{self._url}?{query}",
                                     headers={"X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                out: dict[str, Any] = json.loads(resp.read() or b"{}")
        except (urllib.error.HTTPError, urllib.error.URLError, OSError) as exc:
            # UNREACHABLE IS UNKNOWN, not zero. Planning stops; sending does not.
            return Ceiling(error=str(exc)[:120])

        if not out.get("ok"):
            return Ceiling(error=str(out.get("error") or UNSUPPORTED))
        return Ceiling(limit=int(out.get("limit") or 0),
                       tier=str(out.get("tier") or ""),
                       quality=str(out.get("quality_rating") or ""))


def build_ceiling(settings) -> Any:
    driver = (getattr(settings, "CEILING_DRIVER", "") or "null").lower()
    if driver == "null":
        return NullCeiling()
    return HttpCeiling(
        notify_url=settings.NOTIFICATION_SERVICE_URL,
        path=settings.NOTIFICATION_MESSAGING_LIMIT_PATH,
        token=settings.INTERNAL_SERVICE_TOKEN,
        timeout=settings.PEER_TIMEOUT_SECONDS)
