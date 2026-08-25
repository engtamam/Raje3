"""DirectCloudApiSender — Meta Graph API, direct, for interactive button/list messages.

WHY THIS EXISTS AT ALL: see app/ports/whatsapp_sender.py's module docstring. /internal/notify is
template-only; a booking proposal or a redeemable-offer choice needs an interactive message
(buttons or a list), which only exists inside the 24h "customer service window" Meta opens when a
customer messages a business — and only Meta's own Cloud API can send one.

PER-TENANT CREDENTIAL, SEALED. The token is never an env var: it is a shop's own WhatsApp Business
access token, set by an operator and sealed under SECRETS_KEK exactly like every other operator-
managed credential on this platform (app/core/secret_store.py — same class services/reminders and
services/loyalty both import unmodified). Key: `whatsapp_cloud_api_token:{tenant}`.

Never used to CONFIRM anything. This sender only ever renders what core/tools.py has already
server-side-validated; the button ids it sends are exactly the ids core/conversation.py's gate
checks on the way back in — see that module for why the model cannot make this call itself.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


class NullDirectSender:
    driver = "null"

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def send_interactive(self, *, tenant: str, to: str, body: str,
                               buttons: list[dict[str, str]], idempotency_key: str) -> str:
        self.sent.append({"tenant": tenant, "to": to, "body": body, "buttons": buttons,
                          "idempotency_key": idempotency_key})
        return f"dlv_{idempotency_key}" if idempotency_key else ""

    async def send_template(self, **kwargs) -> str:                    # pragma: no cover - unused half
        return ""


class DirectCloudApiSender:
    driver = "meta_cloud_api"
    _SECRET_PREFIX = "whatsapp_cloud_api_token"

    def __init__(self, *, secret_store: Any, api_base: str, api_version: str,
                timeout: int = 8) -> None:
        self._secrets = secret_store
        self._base = api_base.rstrip("/")
        self._version = api_version
        self._timeout = timeout

    async def _token_and_phone_id(self, tenant: str) -> tuple[str, str]:
        # Two credentials, one per tenant: the access token and the WhatsApp Business phone
        # number id it sends from. Stored as two names under the same tenant-scoped store rather
        # than one JSON blob, so the panel's existing "set one secret, see its hint" UI needs no
        # special case.
        token = await self._secrets.get(tenant=tenant, name=self._SECRET_PREFIX)
        phone_id = await self._secrets.get(tenant=tenant, name="whatsapp_cloud_api_phone_id")
        return token or "", phone_id or ""

    async def send_interactive(self, *, tenant: str, to: str, body: str,
                               buttons: list[dict[str, str]], idempotency_key: str) -> str:
        token, phone_id = await self._token_and_phone_id(tenant)
        if not token or not phone_id:
            raise Unconfigured(
                f"no WhatsApp Cloud API credentials sealed for tenant {tenant!r} — an operator "
                f"must set them before this shop's customers can be sent an interactive message")

        # Meta caps interactive button rows at 3 — anything beyond that must be a LIST message,
        # which this same call shapes differently. Capped here rather than trusting the caller,
        # because the caller is core/tools.py rendering whatever the model proposed.
        rows = buttons[:3]
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body},
                "action": {"buttons": [
                    {"type": "reply", "reply": {"id": b["id"], "title": b["title"][:20]}}
                    for b in rows
                ]},
            },
        }
        url = f"{self._base}/{self._version}/{phone_id}/messages"
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode(), method="POST",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                if not 200 <= resp.status < 300:
                    raise SendFailed(f"Meta Graph API returned {resp.status}")
                result = json.loads(resp.read() or b"{}")
        except urllib.error.URLError as exc:
            raise SendFailed(f"Meta Graph API unreachable: {exc}") from exc
        messages = result.get("messages") or [{}]
        return str(messages[0].get("id") or "")

    async def send_template(self, **kwargs) -> str:                    # pragma: no cover - unused half
        raise NotImplementedError("DirectCloudApiSender only sends interactive messages — "
                                  "template sends go through TemplateSender/notification-service")


class SendFailed(Exception):
    pass


class Unconfigured(Exception):
    """No per-tenant credential sealed. Permanent until an operator sets one — never retried."""
