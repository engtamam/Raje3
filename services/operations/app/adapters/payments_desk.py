"""What orders.py asks of `payments-service`: mint a hosted pay-link under the TENANT's own
merchant gateway (never ours — see that service's own module docstring on `MERCHANT_*` credentials),
and ask it later whether that link was actually paid.

AN EVENT FROM PAYMENTS-SERVICE IS NEVER THE ONLY WAY WE LEARN AN ORDER WAS PAID. Its own
`ports/event_bus.py` says so in its own words: "AT-MOST-ONCE. BEST EFFORT... An event is a HINT
that makes a reconciliation faster. It is NEVER the only way a fact can be learned." So this desk
exposes `reconcile()` — a direct, pollable read of the gateway's own current status — as the
real source of truth a sweep (or a route the WhatsApp assistant calls right after a customer taps
"I paid") can always fall back to, exactly as that port's own docstring requires of every consumer.

SAME IDIOM AS `bookings_desk.py` BESIDE THIS FILE — blocking urllib off the event loop via
`run_in_threadpool`, `X-Internal-Token` (our OWN fleet's shared internal credential, the legitimate
use of it — see `api/v1/till.py`'s own docstring for the DIFFERENT, no-longer-allowed case this is
not: handing that token to an outside party), `None` on an unreachable peer vs a tagged `_status`
dict on a real refusal, so a caller can tell "try again" apart from "this really is refused"."""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from starlette.concurrency import run_in_threadpool

CURRENCY = "SAR"


class PaymentsDesk:
    def __init__(self, *, base_url: str, token: str, timeout: int = 5) -> None:
        self._base = (base_url or "").rstrip("/")
        self._token = token
        self._timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self._base)

    def _post(self, path: str, body: dict[str, Any] | None,
             query: dict[str, Any] | None = None) -> dict[str, Any] | None:
        url = f"{self._base}{path}"
        if query:
            url += "?" + "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in query.items())
        req = urllib.request.Request(
            url, method="POST", data=json.dumps(body or {}).encode(),
            headers={"X-Internal-Token": self._token, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:    # nosec B310
                payload = json.loads(resp.read() or b"{}")
                return {"_status": resp.status, **(payload if isinstance(payload, dict) else {})}
        except urllib.error.HTTPError as exc:
            try:
                payload = json.loads(exc.read() or b"{}")
            except Exception:                                                   # noqa: BLE001
                payload = {}
            return {"_status": exc.code,
                    **(payload if isinstance(payload, dict) else {"ok": False})}
        except Exception:                                                       # noqa: BLE001
            return None

    def _get(self, path: str, query: dict[str, Any]) -> dict[str, Any] | None:
        q = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in query.items())
        req = urllib.request.Request(
            f"{self._base}{path}?{q}", method="GET",
            headers={"X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:    # nosec B310
                if not 200 <= resp.status < 300:
                    return None
                return json.loads(resp.read() or b"{}")
        except Exception:                                                       # noqa: BLE001
            return None

    async def create_request(self, *, tenant: str, reference: str, amount_minor: int,
                             metadata: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """Mint (or re-use — `reference` is the idempotency key on payments-service's own side,
        same as our own `Order.id`) a hosted pay-link under this tenant's own merchant gateway.
        `None` only when the peer could not be reached at all; a real refusal (no gateway
        configured, disabled, amount/currency rejected) comes back as a tagged `_status` dict so
        the caller can show the real reason rather than a generic "try again"."""
        if not self.configured:
            return None
        return await run_in_threadpool(
            self._post, "/internal/payments/requests",
            {"tenant": tenant, "reference": reference, "amount_minor": amount_minor,
             "currency": CURRENCY, "metadata": metadata or {}})

    async def get_request(self, *, tenant: str, request_id: str) -> dict[str, Any] | None:
        """A cheap read of the LAST KNOWN status (whatever a prior webhook or reconcile left
        behind) — no call to the gateway itself. Use `reconcile` instead when the caller actually
        needs the gateway's current truth, not a cached fact."""
        if not self.configured:
            return None
        return await run_in_threadpool(
            self._get, f"/internal/payments/requests/{request_id}", {"tenant": tenant})

    async def reconcile(self, *, tenant: str, request_id: str) -> dict[str, Any] | None:
        """Pull the gateway's own CURRENT status for a request — the real source of truth, never
        dependent on a webhook or an event having arrived (see module docstring). `None` means the
        peer could not be reached; a real "not found" comes back as a tagged `_status` dict."""
        if not self.configured:
            return None
        return await run_in_threadpool(
            self._post, f"/internal/payments/requests/{request_id}/reconcile", None,
            {"tenant": tenant})


def build_payments_desk(settings) -> PaymentsDesk:
    return PaymentsDesk(base_url=settings.PAYMENTS_SERVICE_URL, token=settings.INTERNAL_SERVICE_TOKEN)
