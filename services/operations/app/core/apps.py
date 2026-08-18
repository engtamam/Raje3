"""What has this establishment actually bought — asked once, answered for the whole console.

THE DEFECT THIS CLOSES. Every screen that shows a paid surface had to decide for itself whether the
shop owned it, and none of them could: the console renders a lock from a CAPABILITY, which is about
the person's role. An owner holds `campaigns.manage` on every plan, so the lock never appeared for
the one person who would have paid to remove it. The only screen that knew better was «محلّي», and
only because the insights dashboard happened to return `entitlements` alongside its numbers — one
key, folded into an unrelated payload, for one screen.

ONE CALL, NOT ONE PER SCREEN. Five keys asked five times from five screens is five round trips to
billing on every navigation, and five different answers during a deploy. Asked here, together, the
console holds one list and every lock in the product is drawn from it.

────────────────────────────────────────────────────────────────────────────────────────────────
THIS IS A DISPLAY, AND IT ENFORCES NOTHING

Not a softness — a boundary. The gates are in the services that own the acts (campaigns' create and
tick, loyalty's earn and adjust, insights' dashboard), they are asked at the act, and they fail
closed. If this answer were tampered with, the buttons it draws would still be refused by the
service behind them.

WHICH IS WHY IT DOES NOT FAIL CLOSED. A billing outage here would paint «لم تشترِ» across apps the
shop pays for every month — the worst sentence in the product to show a paying customer, and it
would be shown to ALL of them at once. Instead the failure is reported as itself: `checked: false`,
no ownership claimed either way, and a screen that says «تعذّر التحقق» and offers to retry.
"""
from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any
# `is_base` lives with the subscribe rules because "carries the message meter" is a statement
# about the price list, not about this catalogue. Imported rather than repeated: two
# spellings of «this row is a base» is how the two drift apart.
from app.core.subscribe import is_base

# ── the apps we sell ──────────────────────────────────────────────────────────────────────────
#
# THE KEY IS THE AUTHORITY, NOT THE PLAN NAME (§16.4.1). «الذكية» is a commercial word marketing
# changes; `feature.campaigns` is what the code asks. This list is what the console renders and
# what `ci/check_entitlements.py` compares against the price list, so an app sold and not listed
# here is an app nobody can see they own.
#
# `screen` is where the lock is drawn.
#
# AND `feature.api` IS NOT HERE, DELIBERATELY. The programmatic link moved INTO the base: a till
# writing a visit is the same act the field screen performs, arriving through another door, and a
# shop with a till never uses manual entry anyway — so selling the door while the act is free was
# arbitrary. The KEY still exists and is still enforced at the till (operations/core/licence.py),
# because a shop whose subscription lapsed must not keep writing; it is simply granted by the base
# rather than bought. A row here would draw a buy button for something nobody can buy.
APPS: tuple[dict[str, Any], ...] = (
    {"key": "feature.campaigns", "name": "الحملات", "screen": "messages",
     "what": "ترسل عرضاً أو خبراً لمجموعة من عملائك، ويقيس النظام مَن رجع بسببه."},
    {"key": "feature.loyalty", "name": "برنامج النقاط", "screen": "points",
     "what": "نقاطٌ على كل زيارة، ومكافآت يستبدلها العميل من صفحته أو عند الصندوق."},
    {"key": "feature.insights.engine", "name": "فرصي", "screen": "local",
     "what": "يقول لك أين الفرصة: أي خدمتين تُطلبان معاً، ومن كان سيشتري أكثر، وأثر رسائلك."},
)

KEYS: tuple[str, ...] = tuple(a["key"] for a in APPS)

CANNOT_ASK = "تعذّر التحقق من اشتراكك الآن — حاول بعد قليل."


class NullApps:
    """Answers from what a test put in it. Production requires the http driver — a console that
    cannot read entitlements would draw every lock open, on every screen, for every shop."""

    driver = "null"

    def __init__(self, owned: set[str] | None = None) -> None:
        self.owned: set[str] = set(owned or set())
        # A test that wants the outage path sets this. It is not "owns nothing": the two are
        # different answers and the whole point of `checked` is that they never merge.
        self.reachable = True

    async def held(self, tenant: str) -> tuple[set[str], bool]:
        if not self.reachable:
            return set(), False
        return set(self.owned), True


class HttpApps:
    """billing-service's entitlement check, asked once per key, concurrently."""

    driver = "http"

    def __init__(self, *, billing_url: str, check_path: str, token: str,
                 timeout: int = 8) -> None:
        self._url = billing_url.rstrip("/") + check_path
        self._token = token
        self._timeout = timeout

    def _ask(self, tenant: str, key: str) -> bool | None:
        """True, False, or None for «could not ask» — three answers, never two.

        Collapsing the third into False is precisely the bug this module exists to avoid: it turns
        an outage into a sentence telling a paying shop it has not paid.
        """
        query = urllib.parse.urlencode({"tenant": tenant, "key": key})
        req = urllib.request.Request(f"{self._url}?{query}",
                                     headers={"X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                out: dict[str, Any] = json.loads(resp.read() or b"{}")
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
            return None
        return bool(out.get("allowed"))

    async def held(self, tenant: str) -> tuple[set[str], bool]:
        """(the keys held, whether every key got a real answer).

        CONCURRENTLY, in threads: these are five blocking stdlib calls and the console waits on all
        of them. Sequentially this is five timeouts deep on the one screen an owner opens when he
        is already unhappy about money.
        """
        if not tenant:
            # No establishment on the token is not a shop, and asking would be asking about
            # everybody at once. Answered, not errored: `checked` is true because nothing failed.
            return set(), True
        answers = await asyncio.gather(
            *(asyncio.to_thread(self._ask, tenant, key) for key in KEYS))
        held = {key for key, ok in zip(KEYS, answers) if ok is True}
        return held, all(a is not None for a in answers)


def build_apps(settings: Any) -> Any:
    """`http` when billing is wired, `null` otherwise — and main.py refuses null in production."""
    url = getattr(settings, "BILLING_SERVICE_URL", "") or ""
    path = getattr(settings, "BILLING_CHECK_PATH", "") or ""
    if not url or not path:
        return NullApps()
    return HttpApps(billing_url=url, check_path=path,
                    token=getattr(settings, "INTERNAL_SERVICE_TOKEN", "") or "",
                    timeout=int(getattr(settings, "PEER_TIMEOUT_SECONDS", 8) or 8))


def renewals_by_key(rows: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    """Every live subscription this shop holds, keyed by the app it pays for — `""` for the base.

    THE DATE WAS ALREADY IN HAND AND WAS THROWN AWAY. `/apps` fetched the whole subscription list,
    kept the base's renewal date and dropped every other row on the floor. So a shop paying for
    three things saw one date and discovered the other two on its card statement — the same defect
    family as every other value this product computes and never says out loud.

    THE ROW NAMES ITS OWN APP. `limits_snapshot` is what the plan granted, so the entitlement key
    inside it IS the app; nothing here enumerates the price list, and an app added tomorrow is
    carried by this without being mentioned. A row granting no key we sell is skipped rather than
    guessed at — a capacity pack is not an app and has no card to sit on.
    """
    out: dict[str, dict[str, Any]] = {}
    for row in rows or ():
        limits = row.get("limits_snapshot") or {}
        seen = {"status": row.get("status", ""), "renews_at": row.get("current_period_end", 0),
                "plan_id": row.get("plan_id", "")}
        if is_base(limits):
            out.setdefault("", seen)
            continue
        for key in KEYS:
            if key in limits:
                out.setdefault(key, seen)
    return out


def public(held: set[str], checked: bool, base: dict[str, Any] | None = None,
           renewals: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """The shape the console renders.

    `owned` is only ever claimed when we ASKED and were answered. On a failed check every app is
    reported unknown rather than unowned, and the screen has a third state to draw.

    `base` IS THE SUBSCRIPTION ITSELF — its plan and when it renews. It arrives from billing's
    subscription list (v0.16.7) rather than from an entitlement flag, which is the difference
    between «عندك أساس» and «اشتراكك يتجدّد في 12 سبتمبر»: the second is the first thing an owner
    opening this screen wants to know, and until that route existed we could not say it.
    """
    return {
        "checked": checked,
        "message": "" if checked else CANNOT_ASK,
        # `renews_at` PER APP, not for the base alone. It is `None` — not zero and not absent —
        # when this shop does not hold the app or billing could not be read, because «لا أعرف»
        # and «لا يتجدّد» are two different sentences and a screen must be able to tell them apart.
        "apps": [{**a, "owned": (a["key"] in held) if checked else None,
                  "renews_at": ((renewals or {}).get(a["key"], {}).get("renews_at") or None)
                               if checked else None}
                 for a in APPS],
        # The flat list, for the screens that only need «هل أملك هذا».
        "keys": sorted(held) if checked else [],
        "base": base,
    }
