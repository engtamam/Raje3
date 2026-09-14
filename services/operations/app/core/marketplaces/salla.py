"""Salla — a shop's own Salla store, linked to its Raje3 account. Infrastructure only: OAuth
install/callback and a verified webhook intake. What a linked store's real orders eventually
TRIGGER (a shop-to-shop alliance grant, `core/coupons.py`) is a deliberately separate, later
product decision (owner's own words, 2026-09-15: "نجهز البنية التحتية وخلاص") — this module makes
the connection real and the webhook intake safe to receive, and stops there.

EVERY ENDPOINT/FIELD NAME BELOW IS FROM SALLA'S OWN OFFICIAL DOCS (docs.salla.dev), READ LIVE for
this module — never guessed:
  * OAuth2 authorize/token/refresh — https://docs.salla.dev/421118m0
  * Webhook signature (`X-Salla-Signature`, HMAC-SHA256 over the raw body under the app's own
    Webhook Secret, set once in the Partners Portal) — https://docs.salla.dev/841782f0
  * `order.created` payload shape (`event`, `merchant`, `data.id`, `data.customer`, ...) —
    https://docs.salla.dev/433804m0

CREDENTIALS COME FROM secrets-admin, NEVER FROM HERE — `Settings.SALLA_CLIENT_ID/_SECRET/
_WEBHOOK_SECRET` are read at call time, same posture as `PAYMENT_PUBLISHABLE_KEY`'s own comment:
empty means "not configured yet", answered as a real, named state rather than a crash.
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

AUTHORIZE_URL = "https://accounts.salla.sa/oauth2/auth"
TOKEN_URL = "https://accounts.salla.sa/oauth2/token"
USERINFO_URL = "https://accounts.salla.sa/oauth2/user/info"
#: The Merchant REST API — a different host from the OAuth ones above (accounts.salla.sa issues
#: and refreshes tokens; api.salla.dev is where they are actually SPENT). Read live from
#: docs.salla.dev/5394134e0 for the one endpoint this module calls on it.
MERCHANT_API_BASE = "https://api.salla.dev/admin/v2"
WEBHOOK_SUBSCRIBE_URL = f"{MERCHANT_API_BASE}/webhooks/subscribe"

#: `offline_access` is what makes Salla hand back a `refresh_token` at all — without it the
#: connection dies with the access token in two weeks and the shop owner has to reinstall.
#: `webhooks.read_write` is what lets THIS app register its own webhook subscription
#: programmatically (`register_webhook` below) instead of a human configuring it by hand in the
#: Partners Portal for every merchant that ever installs — required for `webhooks.subscribe`
#: (docs.salla.dev/5394134e0's own security requirement).
DEFAULT_SCOPE = "offline_access webhooks.read_write"

#: THE ONE EVENT THIS APP EVER SUBSCRIBES A MERCHANT TO — the single source of truth for it.
#: `api/v1/salla.py`'s own webhook route imports THIS constant to decide what it acts on, so the
#: event we register with Salla and the event we actually process can never drift apart.
WEBHOOK_EVENT = "order.status.updated"

#: `X-Salla-Signature` — see the module docstring's own link. Read case-sensitively-safe by
#: Starlette's own header lookup (headers are case-insensitive there already).
SIGNATURE_HEADER = "x-salla-signature"

PLATFORM = "_platform"
SALLA_CONNECTIONS = "salla_connections"
SALLA_EVENTS = "salla_events"


class SallaConfigError(Exception):
    """The three credentials are not set yet — answered as a state, never raised past this
    module's own callers (`api/v1/salla.py` turns it into a named refusal, not a 500)."""


@dataclass
class SallaConnection:
    tenant: str
    merchant_id: str
    store_name: str
    access_token: str
    refresh_token: str
    #: unix seconds
    expires_at: int
    scope: str
    connected_at: int
    updated_at: int
    #: Salla's own id for the webhook subscription `register_webhook` created — "" when
    #: registration was never attempted (an old connection, from before this existed) or failed
    #: (support can tell "connected but never actually listening" apart from a normal connection
    #: by this being empty). Default "" keeps reading an OLD stored row (written before this field
    #: existed) working unchanged — the dataclass fills it in rather than the row needing one.
    webhook_id: str = ""

    def public(self) -> dict[str, Any]:
        """NEVER THE TOKENS — same discipline as `CouponAttempt.public()`/secrets-admin's own
        write-only posture: a screen that shows "connected, as شعارة (store name), since (date)"
        never needs the bearer token that would let it act as that store."""
        row = asdict(self)
        row.pop("access_token", None)
        row.pop("refresh_token", None)
        return row


@dataclass
class SallaEvent:
    id: str
    merchant_id: str
    event: str
    #: "" until a connection for this merchant is found — a webhook can arrive for a merchant we
    #: have not (yet, or ever) linked, and that is reported, not silently dropped.
    tenant: str
    received_at: int
    verified: bool


def verify_signature(secret: str, raw_body: bytes, signature: str) -> bool:
    """HMAC-SHA256 of the RAW request body, under the app's own Webhook Secret — exactly Salla's
    own documented check (docs.salla.dev/841782f0), timing-safe.

    THE RAW BYTES, NOT A RE-SERIALISED `json.dumps(...)`. Any re-encoding (key order, whitespace,
    unicode escaping) produces a different byte string than what Salla actually signed, so the
    signature would fail to verify on every single call — the raw body must be read BEFORE any
    JSON parsing happens, which is why the route below reads `request.body()` first.
    """
    if not secret or not signature:
        return False
    mac = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(mac, signature)


def _post_form(url: str, body: dict[str, str], *, timeout: float) -> dict[str, Any] | None:
    """One OAuth2 token-endpoint call. Salla's own docs show the token exchange as a standard
    `application/x-www-form-urlencoded` POST (the OAuth2 RFC's own default shape) — never JSON.
    `None` on any failure; the caller decides how to report it, same posture as every other
    outbound peer client in this service (see `adapters/internal_http.py`'s own module note on why
    that judgment is never centralised)."""
    data = urllib.parse.urlencode(body).encode("ascii")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:      # nosec B310 - fixed host
            return json.loads(resp.read() or b"{}")
    except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
        return None


def _get_json(url: str, *, token: str, timeout: float) -> dict[str, Any] | None:
    req = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:      # nosec B310 - fixed host
            return json.loads(resp.read() or b"{}")
    except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
        return None


def _post_json_bearer(url: str, body: dict[str, Any], *, token: str,
                      timeout: float) -> dict[str, Any] | None:
    """A Merchant-API call — JSON body, `Authorization: Bearer <merchant's own access token>`,
    distinct from `_post_form` above (the OAuth token endpoint, which is form-encoded and signed
    with the APP's client_id/secret, never a merchant's own token)."""
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json",
                "Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:      # nosec B310 - fixed host
            return json.loads(resp.read() or b"{}")
    except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
        return None


class SallaClient:
    """The OAuth half — thin, synchronous (see `api/v1/salla.py` for the `run_in_threadpool`
    wrapping, same posture as `core/licence.py`'s own outbound call)."""

    def __init__(self, *, client_id: str, client_secret: str, redirect_uri: str,
                timeout: float = 8.0) -> None:
        self._id = client_id
        self._secret = client_secret
        self._redirect_uri = redirect_uri
        self._timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self._id and self._secret and self._redirect_uri)

    def authorize_url(self, state: str, *, scope: str = DEFAULT_SCOPE) -> str:
        if not self.configured:
            raise SallaConfigError("Salla is not configured yet")
        query = urllib.parse.urlencode({
            "client_id": self._id, "response_type": "code",
            "redirect_uri": self._redirect_uri, "scope": scope, "state": state,
        })
        return f"{AUTHORIZE_URL}?{query}"

    def exchange_code(self, code: str) -> dict[str, Any] | None:
        if not self.configured:
            return None
        return _post_form(TOKEN_URL, {
            "grant_type": "authorization_code", "client_id": self._id,
            "client_secret": self._secret, "code": code, "redirect_uri": self._redirect_uri,
        }, timeout=self._timeout)

    def refresh(self, refresh_token: str) -> dict[str, Any] | None:
        if not self.configured:
            return None
        return _post_form(TOKEN_URL, {
            "grant_type": "refresh_token", "client_id": self._id,
            "client_secret": self._secret, "refresh_token": refresh_token,
        }, timeout=self._timeout)

    def user_info(self, access_token: str) -> dict[str, Any] | None:
        return _get_json(USERINFO_URL, token=access_token, timeout=self._timeout)

    def register_webhook(self, access_token: str, *, event: str, url: str,
                         name: str = "") -> dict[str, Any] | None:
        """`POST /webhooks/subscribe` on the Merchant API (docs.salla.dev/5394134e0), under the
        MERCHANT's own access token — this is why `DEFAULT_SCOPE` carries `webhooks.read_write`.
        Called once, automatically, right after a fresh connect (`api/v1/salla.py`'s own
        `salla_callback`) — the whole point of this method existing is that an owner never opens
        the Partners Portal himself to wire this up.

        `None` on any failure, same posture as every other call in this class — the caller
        (`salla_callback`) treats a failed registration as "connected, but not yet listening" and
        logs it rather than failing the whole connect: the OAuth link is real either way, and a
        registration retry is cheap to add later without re-running the consent screen."""
        body: dict[str, Any] = {"event": event, "url": url}
        if name:
            body["name"] = name
        return _post_json_bearer(WEBHOOK_SUBSCRIBE_URL, body, token=access_token,
                                 timeout=self._timeout)


class SallaService:
    """Storage for a shop's Salla connection, and the webhook intake log. No business action
    lives here yet — see the module docstring."""

    def __init__(self, *, store: Any, client: SallaClient) -> None:
        self._s = store
        self._client = client

    @property
    def client(self) -> SallaClient:
        return self._client

    async def connection_for(self, tenant: str) -> SallaConnection | None:
        row = await self._s.get(SALLA_CONNECTIONS, tenant)
        if not row:
            return None
        return SallaConnection(**{k: v for k, v in row.items() if k != "tenant_key"})

    async def disconnect(self, tenant: str) -> bool:
        """Remove this tenant's Salla connection entirely — the owner's own undo. `True` when a
        connection actually existed and was removed, `False` when there was nothing to remove
        (never an error either way; a second click, or a stale page, is answered the same as the
        first). NOTHING ELSE IS TOUCHED: past alliance grants this connection ever triggered stay
        exactly as they are (core/coupons.py's own CouponGrant rows) — disconnecting stops FUTURE
        orders from doing anything, it does not undo history."""
        return await self._s.delete(SALLA_CONNECTIONS, tenant)

    async def connection_for_merchant(self, merchant_id: str) -> SallaConnection | None:
        """Which of OUR tenants owns this Salla store — asked by the webhook route, which knows
        only the merchant id Salla sent, never our own tenant id."""
        rows, _ = await self._s.find(
            SALLA_CONNECTIONS, {"merchant_id": str(merchant_id)}, limit=1,
            sort=("connected_at", "desc"))
        if not rows:
            return None
        row = rows[0]
        return SallaConnection(**{k: v for k, v in row.items() if k != "tenant_key"})

    async def save_connection(self, *, tenant: str, merchant_id: str, store_name: str,
                              access_token: str, refresh_token: str, expires_at: int,
                              scope: str, webhook_id: str = "") -> SallaConnection:
        now = int(time.time())
        existing = await self.connection_for(tenant)
        row = SallaConnection(
            tenant=tenant, merchant_id=str(merchant_id), store_name=store_name,
            access_token=access_token, refresh_token=refresh_token, expires_at=expires_at,
            scope=scope, connected_at=existing.connected_at if existing else now,
            updated_at=now,
            # A RECONNECT KEEPS THE OLD `webhook_id` IF THE CALLER DID NOT PASS A NEW ONE — the
            # subscription on Salla's own side almost certainly still exists from before; only a
            # freshly-registered id (this connect's own `register_webhook` call) overwrites it.
            webhook_id=webhook_id or (existing.webhook_id if existing else ""))
        await self._s.put(SALLA_CONNECTIONS, tenant, {"tenant_key": tenant, **asdict(row)})
        return row

    async def update_tokens(self, tenant: str, *, access_token: str, refresh_token: str,
                            expires_at: int) -> SallaConnection | None:
        """A refresh's own write — ONLY the three token fields change, everything else (which
        Salla store, when it was first connected, its webhook subscription id) stays exactly as
        it was. `None` when the connection was removed between the scan that found it due and
        this write actually landing (an owner disconnecting mid-sweep) — the caller treats that
        as nothing left to refresh, not a failure."""
        existing = await self.connection_for(tenant)
        if existing is None:
            return None
        row = SallaConnection(
            tenant=tenant, merchant_id=existing.merchant_id, store_name=existing.store_name,
            access_token=access_token, refresh_token=refresh_token, expires_at=expires_at,
            scope=existing.scope, connected_at=existing.connected_at,
            updated_at=int(time.time()), webhook_id=existing.webhook_id)
        await self._s.put(SALLA_CONNECTIONS, tenant, {"tenant_key": tenant, **asdict(row)})
        return row

    async def connections_expiring_before(self, cutoff: int, *, limit: int = 500) -> list[SallaConnection]:
        """Every live connection whose access token goes stale before `cutoff` — read by the
        daily refresh-scan (see api/internal.py's own `salla_refresh_scan`). A plain
        `scan_all` + filter, not `find()` (equality-only, cannot express "before"): the expected
        row count is one per tenant that ever connected Salla, nowhere near a hot-path scale."""
        rows = await self._s.scan_all(SALLA_CONNECTIONS, limit=limit)
        out = []
        for row in rows:
            if int(row.get("expires_at") or 0) < cutoff:
                out.append(SallaConnection(**{k: v for k, v in row.items() if k != "tenant_key"}))
        return out

    async def record_event(self, *, merchant_id: str, event: str, tenant: str,
                           verified: bool) -> SallaEvent:
        """A durable, minimal receipt that a webhook arrived — the future business action reads
        off this log rather than off Salla's own delivery, which retries and can duplicate."""
        import uuid

        row = SallaEvent(id=f"sevt_{uuid.uuid4().hex}", merchant_id=str(merchant_id),
                         event=event, tenant=tenant, received_at=int(time.time()),
                         verified=verified)
        await self._s.put(SALLA_EVENTS, f"{PLATFORM}|{row.id}", {"tenant": PLATFORM, **asdict(row)})
        return row
