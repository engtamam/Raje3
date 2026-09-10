"""What the WhatsApp subscription-renewal Flow needs (platform v0.19.12's `LoyaltyEngine`,
registered a second time as "subscription_renewal") — the same `balance|rewards|redeem` contract
`HttpLoyaltyBackend` in notification-service calls, answered here from billing-service's real
subscription/invoice data instead of loyalty points.

THE FLOW SEEDS `customer` = THE INVOICE ID, not an end customer. This screen has no end customer —
it is sent to a SHOP OWNER about the shop's own renewal — and billing exposes no "list this
tenant's open invoices" read (only "read ONE invoice by id"). So the caller that TRIGGERS the send
(the renewal-detection poller, not built here) already knows the invoice id — it just renewed the
subscription(s) and holds the id from `run_cycle`'s own event/response — and seeds it as `customer`
at send time (`build_flow(..., data={"customer": invoice_id})`). Every op below just reads that one
invoice; `tenant` (passed separately by the Flow engine) is the IDOR guard billing itself enforces.

TWO DIFFERENT BILLING AUTH TIERS, on purpose:
  - reading the invoice: the INTERNAL tier (`GET /internal/billing/invoices/{id}?tenant=`, shared
    fleet secret) — platform v0.19.12, built for exactly this read.
  - creating the pay-link: `POST /api/v1/billing/invoices/{id}/pay-link` has NO internal-tier
    twin (it is gated `_SELF` = billing.self|billing.manage|platform.billing, a real principal).
    So this reuses the SAME `platform.billing` client-credentials grant `settlements.py` already
    holds (BILLING_CLIENT_ID/BILLING_CLIENT_SECRET/IDENTITY_SERVICE_URL) — no new secret.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from starlette.concurrency import run_in_threadpool


class RenewalUnavailable(Exception):
    """Could not answer — the Flow shows a retry snackbar (LoyaltyEngine's own ProviderUnavailable
    handling), never a fake balance or a fake success."""


class RenewalProvider:
    def __init__(self, *, billing_url: str, identity_url: str, internal_token: str,
                 client_id: str, client_secret: str, timeout: int = 8) -> None:
        self._billing = (billing_url or "").rstrip("/")
        self._identity = (identity_url or "").rstrip("/")
        self._internal_token = internal_token
        self._client_id = client_id
        self._client_secret = client_secret
        self._timeout = timeout
        self._token = ""
        self._token_until = 0.0

    @property
    def configured(self) -> bool:
        return bool(self._billing and self._identity and self._client_id and self._client_secret)

    # ── the platform.billing bearer, minted and cached — same shape as settlements.py's own ──────
    def _mint(self) -> str:
        now = time.time()
        if self._token and now < self._token_until:
            return self._token
        body = json.dumps({"grant_type": "client_credentials", "client_id": self._client_id,
                           "client_secret": self._client_secret}).encode()
        req = urllib.request.Request(
            self._identity + "/api/v1/oauth/token", data=body, method="POST",
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:        # nosec B310
            payload = json.loads(resp.read() or b"{}")
        self._token = str(payload.get("access_token") or "")
        self._token_until = now + max(0, int(payload.get("expires_in") or 0) - 60)
        return self._token

    def _invoice_sync(self, tenant: str, invoice_id: str) -> dict[str, Any]:
        q = urllib.parse.urlencode({"tenant": tenant})
        req = urllib.request.Request(
            f"{self._billing}/internal/billing/invoices/{urllib.parse.quote(invoice_id)}?{q}",
            headers={"X-Internal-Token": self._internal_token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:    # nosec B310
                return json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return {}
            raise RenewalUnavailable(f"billing returned {exc.code}") from exc
        except (urllib.error.URLError, OSError) as exc:
            raise RenewalUnavailable(f"billing unreachable: {exc}") from exc

    def _pay_link_sync(self, tenant: str, invoice_id: str) -> dict[str, Any]:
        token = self._mint()
        if not token:
            raise RenewalUnavailable("could not mint a platform.billing token")
        body = json.dumps({"tenant": tenant}).encode()
        req = urllib.request.Request(
            f"{self._billing}/api/v1/billing/invoices/{urllib.parse.quote(invoice_id)}/pay-link",
            data=body, method="POST",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:    # nosec B310
                return json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as exc:
            try:
                payload = json.loads(exc.read() or b"{}")
            except Exception:                                                   # noqa: BLE001
                payload = {}
            return {"_status": exc.code, **payload}
        except (urllib.error.URLError, OSError) as exc:
            raise RenewalUnavailable(f"billing unreachable: {exc}") from exc

    # ── the LoyaltyProvider-shaped contract ──────────────────────────────────────────────────────
    async def balance(self, *, tenant: str, customer: str) -> dict[str, Any]:
        """`customer` is the invoice id (see module docstring). -> {"label": "..."} — the amount
        due, shown next to the screen title."""
        inv = await run_in_threadpool(self._invoice_sync, tenant, customer)
        if not inv:
            return {"label": "لا توجد فاتورة تجديد مفتوحة حالياً"}
        due = int(inv.get("amount_due_minor", 0) or 0)
        currency = str(inv.get("currency") or "SAR")
        return {"label": f"المستحق: {due / 100:.2f} {currency}"}

    async def rewards(self, *, tenant: str, customer: str) -> list[dict[str, Any]]:
        """One "reward" per invoice line (one per renewed app on a consolidated invoice) PLUS the
        single renew-everything option is redundant with the invoice itself — Meta's Flow SELECT
        screen needs at least one option to submit, so this offers exactly one: "renew this
        invoice", titled with its total. Per-line detail (which apps) rides the description."""
        inv = await run_in_threadpool(self._invoice_sync, tenant, customer)
        if not inv:
            return []
        lines = inv.get("lines") or []
        names = "، ".join(str(li.get("description") or "") for li in lines if li.get("description"))
        due = int(inv.get("amount_due_minor", 0) or 0)
        currency = str(inv.get("currency") or "SAR")
        return [{"id": customer, "title": f"تجديد الاشتراك — {due / 100:.2f} {currency}",
                "description": names or "تجديد الاشتراك"}]

    async def redeem(self, *, tenant: str, customer: str, reward: str,
                     idempotency_key: str) -> dict[str, Any]:
        """`reward` is expected to equal `customer` (the one option `rewards()` ever offers) — a
        mismatch (a stale/tampered session) is refused rather than paying whichever invoice the
        session happens to hold. -> {"ok": True, "ref": pay_url} | {"ok": False, "reason": "..."}."""
        if reward != customer:
            return {"ok": False, "reason": "الجلسة انتهت — ابدأ من جديد."}
        out = await run_in_threadpool(self._pay_link_sync, tenant, customer)
        if out.get("_status"):
            reason = {404: "الفاتورة غير موجودة.", 409: "هذه الفاتورة سُدِّدت بالفعل."}.get(
                int(out["_status"]), "تعذّر إنشاء رابط الدفع الآن.")
            return {"ok": False, "reason": reason}
        pay_url = str(out.get("pay_url") or out.get("checkout_url") or "")
        if not pay_url:
            return {"ok": False, "reason": "تعذّر إنشاء رابط الدفع الآن."}
        return {"ok": True, "ref": pay_url}


class NullRenewalProvider:
    """No billing/identity credentials configured — every op refuses, never a fake renewal."""

    configured = False

    async def balance(self, *, tenant: str, customer: str) -> dict[str, Any]:
        raise RenewalUnavailable("renewal provider not configured")

    async def rewards(self, *, tenant: str, customer: str) -> list[dict[str, Any]]:
        raise RenewalUnavailable("renewal provider not configured")

    async def redeem(self, *, tenant: str, customer: str, reward: str,
                     idempotency_key: str) -> dict[str, Any]:
        raise RenewalUnavailable("renewal provider not configured")


def build_renewal_provider(settings) -> Any:
    p = RenewalProvider(
        billing_url=getattr(settings, "BILLING_SERVICE_URL", ""),
        identity_url=getattr(settings, "IDENTITY_SERVICE_URL", ""),
        internal_token=getattr(settings, "INTERNAL_SERVICE_TOKEN", ""),
        client_id=getattr(settings, "BILLING_CLIENT_ID", ""),
        client_secret=getattr(settings, "BILLING_CLIENT_SECRET", ""))
    return p if p.configured else NullRenewalProvider()
