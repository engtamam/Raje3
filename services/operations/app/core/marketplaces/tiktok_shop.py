"""TikTok Shop — a shop's own TikTok Shop store, linked to its Raje3 account. Infrastructure
only, the same scope `salla.py`'s own module docstring draws for itself: OAuth install/callback,
a verified webhook intake, and enough of the signed API to fetch what a webhook payload alone does
not carry (an order's phone, lines and total). What gets recorded as a visit is `api/v1/tiktok.py`'s
own concern, not this module's.

EVERY ENDPOINT/FIELD/ALGORITHM BELOW IS FROM TIKTOK'S OWN OFFICIAL DOCS
(partner.tiktokshop.com/docv2), READ LIVE via a real browser for this module 2026-09-16 — never
guessed (their JS-rendered docs defeat a plain fetch, so the pages were opened and read one by one):
  * OAuth authorize domains, by market and role — https://partner.tiktokshop.com/docv2/page/
    authorization-overview-202407 (`Authorization overview`)
  * Token exchange/refresh — same page, `Get Access Token API` / `Get Refresh Token API`
  * Request signing (HMAC-SHA256, the exact canonical-string algorithm) — https://
    partner.tiktokshop.com/docv2/page/sign-your-api-request
  * Webhook signature (`Authorization` header, HMAC-SHA256 of `app_key + raw_body`, NOT a bearer
    token) and the full event_type list — https://partner.tiktokshop.com/docv2/page/
    tts-webhooks-overview
  * `Get Order Detail` response shape (`/order/202507/orders`) — https://partner.tiktokshop.com/
    docv2/page/get-order-detail-202507

CREDENTIALS COME FROM secrets-admin, NEVER FROM HERE — same posture as `salla.py`'s own note.

ONE REAL GOTCHA WORTH NAMING BECAUSE THE DOCS SAY SO THEMSELVES: the token endpoint's
`grant_type` value is the literal string `"authorized_code"` — not the standard OAuth
`"authorization_code"`. The docs explicitly warn not to "fix" this typo; `_TOKEN_GRANT_TYPE`
below is that exact string, kept as a named constant so nobody "corrects" it later.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any

# Read live 2026-09-16 from `authorization-overview-202407` — Rest-of-World bases (the docs give a
# separate `.us.` pair for the US market; KSA and every other ROW tenant use these). Only the
# SELLER row is used here — Creator/Partner authorization are different products this app does
# not offer.
AUTHORIZE_URL_ROW = "https://services.tiktokshop.com/open/authorize"
TOKEN_URL = "https://auth.tiktok-shops.com/api/v2/token/get"
REFRESH_URL = "https://auth.tiktok-shops.com/api/v2/token/refresh"
API_BASE = "https://open-api.tiktokglobalshop.com"

#: See the module docstring's own note — this is TikTok's own documented value, not a typo of
#: ours to "fix" to the standard OAuth spelling.
_TOKEN_GRANT_TYPE = "authorized_code"

#: `x-tts-access-token`, never `Authorization: Bearer` — confirmed live against `Get Order
#: Detail`'s own request-header table. TikTok Shop's signed-request scheme is unrelated to
#: standard bearer auth; see `sign_request` below for the actual signature this service must add.
ACCESS_TOKEN_HEADER = "x-tts-access-token"

#: `Authorization` — TikTok's webhook signature header (see `verify_webhook_signature`). Not a
#: bearer token: the raw hex HMAC digest itself, with no scheme prefix.
WEBHOOK_SIGNATURE_HEADER = "authorization"

#: THE ONLY TOPIC THIS APP EVER SUBSCRIBES A SHOP TO, at connect time — the single source of
#: truth `api/v1/tiktok.py`'s webhook route imports, exactly like `WEBHOOK_EVENT` in `salla.py`.
#: `ORDER_STATUS_CHANGE` is the topic that fires for both a brand-new order and every later status
#: change (confirmed live, `tts-webhooks-overview`'s own quick-reference table).
WEBHOOK_TOPIC = "ORDER_STATUS_CHANGE"

#: Shop-connection-lifecycle topics (same page) — a shop revoking access, or its authorization
#: nearing its own expiry. The docs' own recommended-listener table says explicitly to subscribe
#: to BOTH together whenever an app needs to hold long-lived shop access, which this one does.
SELLER_DEAUTHORIZATION_TOPIC = "SELLER_DEAUTHORIZATION"
UPCOMING_AUTHORIZATION_EXPIRATION_TOPIC = "UPCOMING_AUTHORIZATION_EXPIRATION"

PLATFORM = "_platform"
TIKTOK_SHOP_CONNECTIONS = "tiktok_shop_connections"
TIKTOK_SHOP_EVENTS = "tiktok_shop_events"


class TikTokShopConfigError(Exception):
    """The three credentials are not set yet — same posture as `SallaConfigError`."""


@dataclass
class TikTokShopConnection:
    tenant: str
    #: TikTok's own shop id — what a webhook's `shop_id` field is matched against, never our own
    #: tenant id (a shop authorizing us has no reason to know it).
    shop_id: str
    seller_name: str
    access_token: str
    refresh_token: str
    #: unix seconds — ABSOLUTE timestamps, not a duration. TikTok's own `token/get` response
    #: names these fields `access_token_expire_in`/`refresh_token_expire_in` but documents them as
    #: "Unix timestamp" (confirmed live) — a duration-shaped name for an absolute value. Read them
    #: as absolute here throughout; `save_connection`/`update_tokens` never add `time.time()` to
    #: them the way `salla.py`'s own `expires_at = int(time.time()) + int(tokens.get("expires"))`
    #: does for Salla's genuinely relative field.
    access_token_expires_at: int
    refresh_token_expires_at: int
    scope: str
    connected_at: int
    updated_at: int

    def public(self) -> dict[str, Any]:
        """NEVER THE TOKENS — same discipline as `SallaConnection.public()`."""
        row = asdict(self)
        row.pop("access_token", None)
        row.pop("refresh_token", None)
        return row


@dataclass
class TikTokShopEvent:
    id: str
    shop_id: str
    event_type: str
    #: "" until a connection for this shop is found — same "reported, never silently dropped"
    #: posture as `SallaEvent.tenant`.
    tenant: str
    received_at: int
    verified: bool


def verify_webhook_signature(app_key: str, app_secret: str, raw_body: bytes,
                             signature: str) -> bool:
    """`Authorization: HMAC-SHA256(app_key + raw_body, app_secret)`, hex, timing-safe — read live
    from `tts-webhooks-overview`'s own reproducible example. `app_secret` is the HMAC KEY;
    `app_key + raw_body` is the message — the OPPOSITE key/message pairing from `sign_request`
    below (keyed by `app_secret` over a canonical string that itself embeds no `app_key`); the two
    are unrelated schemes that happen to share an algorithm.

    NO TIMESTAMP IN THE SIGNATURE ITSELF. Replay protection here is `tts_notification_id`-based
    dedupe in the caller (`TikTokShopService.seen_notification`), never a timestamp tolerance
    window — see [[task-tiktok-app-phases]] memory for why this is a real, deliberate mismatch
    with `platform/services/webhook-service`'s own generic `InboundService` (which DOES assume the
    signature covers a timestamp), and why this module verifies locally rather than routing
    through it.
    """
    if not app_key or not app_secret or not signature:
        return False
    mac = hmac.new(app_secret.encode("utf-8"), app_key.encode("utf-8") + raw_body,
                   hashlib.sha256).hexdigest()
    return hmac.compare_digest(mac, signature)


def sign_request(*, method: str, path: str, query: dict[str, str], body: bytes,
                 content_type: str, app_secret: str) -> str:
    """TikTok Shop's own request-signing algorithm, read live 2026-09-16 from `sign-your-api-
    request`'s own Go/Java/Node.js/Python code samples — reproduced here in Python, not translated
    by guesswork from a different language's sample.

    ALGORITHM, VERBATIM FROM THE DOCS:
      1. every query param EXCEPT `sign` and `access_token`
      2. sorted alphabetically by key
      3. concatenated as `{key}{value}{key}{value}...` (no separator)
      4. the REQUEST PATH prepended
      5. the RAW request body appended, UNLESS `content_type` is `multipart/form-data`
      6. wrapped `app_secret + input + app_secret`
      7. HMAC-SHA256 of that wrapped string, keyed by `app_secret`, hex-encoded

    `method` IS ACCEPTED BUT UNUSED — TikTok's own algorithm never reads the HTTP method, only the
    path, query and body; kept as a parameter so a caller's intent reads correctly at the call
    site rather than the method being silently irrelevant with no explanation.
    """
    keys = sorted(k for k in query if k not in ("sign", "access_token"))
    concatenated = "".join(f"{k}{query[k]}" for k in keys)
    input_str = path + concatenated
    if (content_type or "").strip().lower() != "multipart/form-data":
        input_str += body.decode("utf-8", errors="replace")
    wrapped = app_secret + input_str + app_secret
    return hmac.new(app_secret.encode("utf-8"), wrapped.encode("utf-8"),
                    hashlib.sha256).hexdigest()


def _post_form(url: str, body: dict[str, str], *, timeout: float) -> dict[str, Any] | None:
    """`token/get` and `token/refresh` are plain GET-with-query-params per the docs' own sample
    request, not a POST body — `_get_json`-shaped, kept as its own function only so the two OAuth
    calls in `TikTokShopClient` read as what they are rather than sharing a generically-named
    helper with the signed API caller below."""
    query = urllib.parse.urlencode(body)
    req = urllib.request.Request(f"{url}?{query}", headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:      # nosec B310 - fixed host
            return json.loads(resp.read() or b"{}")
    except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
        return None


class TikTokShopClient:
    """The OAuth + signed-API half — thin, synchronous (see `api/v1/tiktok.py` for the
    `run_in_threadpool` wrapping, same posture as `SallaClient`'s own callers)."""

    def __init__(self, *, app_key: str, app_secret: str, service_id: str,
                timeout: float = 8.0) -> None:
        self._key = app_key
        self._secret = app_secret
        self._service_id = service_id
        self._timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self._key and self._secret and self._service_id)

    @property
    def app_key(self) -> str:
        return self._key

    def authorize_url(self, state: str) -> str:
        """THE SELLER (ROW) AUTHORIZATION LINK ONLY — Creator and Partner authorization are a
        different product this app does not offer, and each uses its own distinct domain (read
        live from the same overview page).

        `state` IS APPENDED even though the docs' own domain table shows only `service_id` in the
        URL template for the Seller row — the SAME page's own worked example of the redirect back
        (`{redirect_url}?code=...&state={state}`) explicitly documents `state` arriving at the
        callback, which is only possible if it round-trips through this same link. Not guessed:
        the table is abbreviated to the market-distinguishing part, the flow narrative is the
        complete contract.
        """
        if not self.configured:
            raise TikTokShopConfigError("TikTok Shop is not configured yet")
        query = urllib.parse.urlencode({"service_id": self._service_id, "state": state})
        return f"{AUTHORIZE_URL_ROW}?{query}"

    def exchange_code(self, auth_code: str) -> dict[str, Any] | None:
        if not self.configured:
            return None
        out = _post_form(TOKEN_URL, {
            "app_key": self._key, "app_secret": self._secret, "auth_code": auth_code,
            "grant_type": _TOKEN_GRANT_TYPE,
        }, timeout=self._timeout)
        return (out or {}).get("data") if out and out.get("code") == 0 else None

    def refresh(self, refresh_token: str) -> dict[str, Any] | None:
        if not self.configured:
            return None
        out = _post_form(REFRESH_URL, {
            "app_key": self._key, "app_secret": self._secret, "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }, timeout=self._timeout)
        return (out or {}).get("data") if out and out.get("code") == 0 else None

    def get_order_detail(self, *, access_token: str, shop_cipher: str,
                         order_id: str) -> dict[str, Any] | None:
        """`GET /order/202507/orders` — Phase 1/2's own signed call, because a webhook's
        `ORDER_STATUS_CHANGE` payload carries just `order_id`/`order_status`/`update_time`
        (confirmed live, the reproducible signing example on `tts-webhooks-overview`), never the
        phone or the line items `record_visit` needs — those only exist on this call's own
        response.
        """
        if not self.configured:
            return None
        path = "/order/202507/orders"
        query = {"app_key": self._key, "timestamp": str(int(time.time())),
                "shop_cipher": shop_cipher, "ids": order_id}
        sign = sign_request(method="GET", path=path, query=query, body=b"",
                            content_type="application/json", app_secret=self._secret)
        full_query = {**query, "sign": sign}
        url = f"{API_BASE}{path}?{urllib.parse.urlencode(full_query)}"
        req = urllib.request.Request(url, headers={
            "content-type": "application/json", ACCESS_TOKEN_HEADER: access_token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:  # nosec B310
                out = json.loads(resp.read() or b"{}")
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
            return None
        if out.get("code") != 0:
            return None
        orders = ((out.get("data") or {}).get("orders")) or []
        return orders[0] if orders else None

    def get_conversation_messages(self, *, access_token: str, shop_cipher: str,
                                  conversation_id: str,
                                  page_size: int = 10) -> list[dict[str, Any]]:
        """`GET /customer_service/202309/conversations/{conversation_id}/messages` — Phase 3's
        own read: a `NEW_MESSAGE` webhook's own `data` shape was never confirmed live (only its
        trigger SCENARIO was — "a new message is sent" — `tts-webhooks-overview`'s own table),
        so — same "fetch the real thing, never trust an unverified webhook body" discipline
        `_fetch_and_record_order` already applies to `ORDER_STATUS_CHANGE` — the webhook route
        only ever reads `conversation_id` out of the payload defensively and calls this for
        everything else. Confirmed live against
        `get-conversation-messages-202309`'s own response sample — each message carries `id`,
        `type`, `content` (a JSON-serialised STRING, e.g. `'{"content": "hi"}'`), `create_time`,
        `sender.role` (`"BUYER"` for the customer's own messages), and `plaintext`.

        `sort_order=DESC` (the endpoint's own default) is relied on — index 0 is the newest
        message, which is what a reply is actually responding to.
        """
        if not self.configured:
            return []
        path = f"/customer_service/202309/conversations/{conversation_id}/messages"
        query = {"app_key": self._key, "timestamp": str(int(time.time())),
                "shop_cipher": shop_cipher, "page_size": str(page_size),
                "need_plaintext": "true"}
        sign = sign_request(method="GET", path=path, query=query, body=b"",
                            content_type="application/json", app_secret=self._secret)
        full_query = {**query, "sign": sign}
        url = f"{API_BASE}{path}?{urllib.parse.urlencode(full_query)}"
        req = urllib.request.Request(url, headers={
            "content-type": "application/json", ACCESS_TOKEN_HEADER: access_token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:  # nosec B310
                out = json.loads(resp.read() or b"{}")
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
            return []
        if out.get("code") != 0:
            return []
        return list((out.get("data") or {}).get("messages") or [])

    def send_message(self, *, access_token: str, shop_cipher: str, conversation_id: str,
                     text: str) -> bool:
        """`POST /customer_service/202606/conversations/{conversation_id}/messages` — confirmed
        live against `send-message-202606`: `content` is itself a JSON-SERIALISED STRING (double-
        encoded — `'{"content": "..."}'`, not a bare string), `type` is one of a fixed enum
        (`TEXT` is the only one this client ever sends), and `sender_role` distinguishes an
        automated reply (`"SYSTEM"`) from one a real human agent typed (`"CUSTOMER_SERVICE"`) — a
        distinction TikTok's own UI likely surfaces to the buyer, so this is never spoofed as a
        human's own reply.
        """
        if not self.configured or not text.strip():
            return False
        path = f"/customer_service/202606/conversations/{conversation_id}/messages"
        query = {"app_key": self._key, "timestamp": str(int(time.time())),
                "shop_cipher": shop_cipher}
        body_obj = {"type": "TEXT", "content": json.dumps({"content": text[:2000]}),
                   "sender_role": "SYSTEM"}
        body = json.dumps(body_obj).encode("utf-8")
        sign = sign_request(method="POST", path=path, query=query, body=body,
                            content_type="application/json", app_secret=self._secret)
        full_query = {**query, "sign": sign}
        url = f"{API_BASE}{path}?{urllib.parse.urlencode(full_query)}"
        req = urllib.request.Request(url, data=body, method="POST", headers={
            "content-type": "application/json", ACCESS_TOKEN_HEADER: access_token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:  # nosec B310
                out = json.loads(resp.read() or b"{}")
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
            return False
        return out.get("code") == 0


class TikTokShopService:
    """Storage for a shop's TikTok Shop connection, and the webhook intake log — same shape and
    scope as `SallaService`."""

    def __init__(self, *, store: Any, client: TikTokShopClient) -> None:
        self._s = store
        self._client = client

    @property
    def client(self) -> TikTokShopClient:
        return self._client

    async def connection_for(self, tenant: str) -> TikTokShopConnection | None:
        row = await self._s.get(TIKTOK_SHOP_CONNECTIONS, tenant)
        if not row:
            return None
        return TikTokShopConnection(**{k: v for k, v in row.items() if k != "tenant_key"})

    async def connection_for_shop(self, shop_id: str) -> TikTokShopConnection | None:
        """Which of OUR tenants owns this TikTok shop — asked by the webhook route, which knows
        only the `shop_id` TikTok sent."""
        rows, _ = await self._s.find(
            TIKTOK_SHOP_CONNECTIONS, {"shop_id": str(shop_id)}, limit=1,
            sort=("connected_at", "desc"))
        if not rows:
            return None
        row = rows[0]
        return TikTokShopConnection(**{k: v for k, v in row.items() if k != "tenant_key"})

    async def disconnect(self, tenant: str) -> bool:
        return await self._s.delete(TIKTOK_SHOP_CONNECTIONS, tenant)

    async def save_connection(self, *, tenant: str, shop_id: str, seller_name: str,
                              access_token: str, refresh_token: str,
                              access_token_expires_at: int, refresh_token_expires_at: int,
                              scope: str) -> TikTokShopConnection:
        now = int(time.time())
        existing = await self.connection_for(tenant)
        row = TikTokShopConnection(
            tenant=tenant, shop_id=str(shop_id), seller_name=seller_name,
            access_token=access_token, refresh_token=refresh_token,
            access_token_expires_at=access_token_expires_at,
            refresh_token_expires_at=refresh_token_expires_at, scope=scope,
            connected_at=existing.connected_at if existing else now, updated_at=now)
        await self._s.put(TIKTOK_SHOP_CONNECTIONS, tenant, {"tenant_key": tenant, **asdict(row)})
        return row

    async def update_tokens(self, tenant: str, *, access_token: str, refresh_token: str,
                            access_token_expires_at: int,
                            refresh_token_expires_at: int) -> TikTokShopConnection | None:
        existing = await self.connection_for(tenant)
        if existing is None:
            return None
        row = TikTokShopConnection(
            tenant=tenant, shop_id=existing.shop_id, seller_name=existing.seller_name,
            access_token=access_token, refresh_token=refresh_token,
            access_token_expires_at=access_token_expires_at,
            refresh_token_expires_at=refresh_token_expires_at, scope=existing.scope,
            connected_at=existing.connected_at, updated_at=int(time.time()))
        await self._s.put(TIKTOK_SHOP_CONNECTIONS, tenant, {"tenant_key": tenant, **asdict(row)})
        return row

    async def connections_expiring_before(self, cutoff: int,
                                          *, limit: int = 500) -> list[TikTokShopConnection]:
        """Same shape as `SallaService.connections_expiring_before` — a plain scan, never `find()`
        (equality-only), because "before a cutoff" cannot be expressed that way."""
        rows = await self._s.scan_all(TIKTOK_SHOP_CONNECTIONS, limit=limit)
        out = []
        for row in rows:
            if int(row.get("access_token_expires_at") or 0) < cutoff:
                out.append(TikTokShopConnection(
                    **{k: v for k, v in row.items() if k != "tenant_key"}))
        return out

    async def seen_notification(self, tts_notification_id: str) -> bool:
        """`True` when this exact webhook delivery was already processed — TikTok's own docs say
        plainly it makes "at least once" delivery and a listener must be idempotent
        (`tts-webhooks-overview`). Keyed on `tts_notification_id` alone, never a body hash — the
        same reasoning `salla.py`'s own dedupe-by-event-id note gives, and TikTok's docs name this
        exact field for exactly this purpose."""
        return await self._s.get(TIKTOK_SHOP_EVENTS, f"{PLATFORM}|seen|{tts_notification_id}") \
            is not None

    async def record_event(self, *, tts_notification_id: str, shop_id: str, event_type: str,
                           tenant: str, verified: bool) -> TikTokShopEvent:
        row = TikTokShopEvent(id=tts_notification_id, shop_id=str(shop_id),
                              event_type=event_type, tenant=tenant,
                              received_at=int(time.time()), verified=verified)
        await self._s.put(TIKTOK_SHOP_EVENTS, f"{PLATFORM}|seen|{tts_notification_id}",
                          {"tenant": PLATFORM, **asdict(row)})
        return row

    async def record_message_category(self, *, tenant: str, category: str, source: str = "dm",
                                      conversation_id: str = "") -> None:
        """One durable row per tagged message — «أكثر شكوى تتكرر» reads these back with a plain
        COUNT-by-category, the exact same "aggregate over real rows, invent nothing" shape
        `record_visit`'s own `rating_issue_step_ids` counting already uses (operations/core/
        operations.py). `category` may be a `tiktok_categories.KNOWN_SLUGS` member OR a novel
        slug the model proposed — this store does not judge which; a slug outside the known set
        simply never appears on an owner's report until a human decides to add it (the "adaptive
        taxonomy" design agreed 2026-09-16 — see [[task-tiktok-app-phases]] memory).

        `source` — `"dm"` or `"comment"` — travels as its own field, never folded into the
        category name itself (the same unified-taxonomy decision).
        """
        import uuid

        if not tenant or not category:
            return
        row_id = f"tkcat_{uuid.uuid4().hex}"
        await self._s.put("tiktok_message_categories", f"{tenant}|{row_id}", {
            "tenant": tenant, "id": row_id, "category": category, "source": source,
            "conversation_id": conversation_id, "created": int(time.time())})
