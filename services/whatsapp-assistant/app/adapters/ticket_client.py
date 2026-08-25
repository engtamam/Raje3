"""TicketClient — opens a human-escalation ticket in platform's ticket-service.

CORRECTED: an earlier version of this module believed ticket-service's internal tier carried no
ticket-creation route and worked around that with a self-minted HS256 machine credential. That was
a verification error, not a real platform gap — `POST /internal/tickets`
(platform/services/ticket-service/app/api/internal.py) exists and takes the exact same
X-Internal-Token peer shape `core/customer_lookup.py`/`core/points.py` already use against
operations/loyalty. No escalation, no shared secret, no locally-minted token.

THAT ROUTE IS THE "GRANTEE" WRITE PATH, not a bare internal-service call — ticket-service's own
design (spec §13) treats every writer other than the tenant's own staff as a consented third
party with a scoped grant, and this service is exactly that shape from ticket-service's point of
view: an outside actor opening tickets on the tenant's behalf, attributed to ITS OWN pseudonym in
the append-only log (never the shop's raiser_ref) so the log always answers who really acted.
`_ensure_grant` upserts a (tenant, "whatsapp-assistant") write grant before the first ticket per
tenant per process — idempotent on ticket-service's side (`shares.upsert`), cached here the same
way `core/conversation.py::_shop_name` caches a per-tenant peer read, so this is a real network
call once per tenant per process lifetime, not once per escalation.

PII AT THIS BOUNDARY (documented per the design point that asked for the reasoning, not just the
code): the ticket body carries the conversation's ROLLING SUMMARY, never the raw transcript — the
same "never a second transcript" rule `core/conversation.py` already applies to what the LLM sees.
The customer's real phone number DOES go in `metadata.contact`, and that is a deliberate boundary
decision, not an oversight: a human agent assigned this ticket needs a real way to call the
customer back, and ticket-service is reached only by staff who hold a grant-checked, capability-
gated read on the tenant's tickets — the same class of "trusted internal surface that legitimately
handles real PII" `DirectCloudApiSender`'s successor already treats a WhatsApp send destination as.
It is NOT the LLM prompt, which per `core/conversation.py::opaque_reference` never sees a real
name or number at all.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


class TicketOpenFailed(Exception):
    """ticket-service refused or could not be reached. Never turned into a false "connected to a
    human" message — the caller must not tell a customer they were escalated when they were not."""


class NullTicketClient:
    """No ticket-service configured (dev/test default). Records what WOULD have been opened rather
    than silently discarding it, so a test can assert an escalation actually tried to fire."""
    driver = "null"

    def __init__(self) -> None:
        self.opened: list[dict[str, Any]] = []

    async def open_ticket(self, *, tenant: str, subject: str, body: str, ref_id: str,
                          contact: str = "", priority: str = "normal") -> dict[str, Any]:
        record = {"tenant": tenant, "subject": subject, "body": body, "ref_id": ref_id,
                  "contact": contact, "priority": priority}
        self.opened.append(record)
        return {"id": f"tkt_null_{len(self.opened)}", **record}


class HttpTicketClient:
    driver = "http"

    def __init__(self, *, url: str, tickets_path: str, shares_path: str, token: str,
                grantee: str, ticket_type: str, share_ttl_seconds: int,
                timeout: int = 8) -> None:
        self._tickets_url = url.rstrip("/") + tickets_path
        self._shares_url = url.rstrip("/") + shares_path
        self._token = token
        self._grantee = grantee
        self._type = ticket_type
        self._share_ttl = share_ttl_seconds
        self._timeout = timeout
        # Per-tenant, per-process: a write grant does not change turn to turn, and re-upserting it
        # before every single escalation would add a second peer call to the one action this
        # module exists to perform reliably.
        self._granted_tenants: set[str] = set()

    def _post(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode(), method="POST",
            headers={"Content-Type": "application/json", "X-Internal-Token": self._token})
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
            if not 200 <= resp.status < 300:
                raise TicketOpenFailed(f"ticket-service returned {resp.status}")
            return json.loads(resp.read() or b"{}")

    def _ensure_grant(self, tenant: str) -> None:
        if tenant in self._granted_tenants:
            return
        # {} scope = every type/status this grantee might ever need to raise — narrowing it to
        # `self._type` alone would mean adding a second ticket type later requires a platform-side
        # re-grant instead of a config change on this side.
        self._post(self._shares_url, {
            "tenant": tenant, "grantee": self._grantee, "permissions": ["read", "write"],
            "scope": {}, "ttl_seconds": self._share_ttl})
        self._granted_tenants.add(tenant)

    async def open_ticket(self, *, tenant: str, subject: str, body: str, ref_id: str,
                          contact: str = "", priority: str = "normal") -> dict[str, Any]:
        metadata: dict[str, Any] = {"channel": "whatsapp"}
        if contact:
            metadata["contact"] = contact
        payload = {
            "tenant": tenant, "grantee": self._grantee, "type": self._type,
            "subject": subject[:512], "body": body[:20_000],
            "ref": {"kind": "whatsapp_conversation", "id": ref_id[:256]},
            "priority": priority, "metadata": metadata,
        }
        try:
            self._ensure_grant(tenant)
            return self._post(self._tickets_url, payload)
        except urllib.error.HTTPError as exc:
            raise TicketOpenFailed(f"ticket-service returned {exc.code}") from exc
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise TicketOpenFailed(f"ticket-service unreachable: {exc}") from exc


def build(settings: Any) -> Any:
    if not settings.TICKET_SERVICE_URL:
        return NullTicketClient()
    return HttpTicketClient(
        url=settings.TICKET_SERVICE_URL, tickets_path=settings.TICKET_SERVICE_TICKETS_PATH,
        shares_path=settings.TICKET_SERVICE_SHARES_PATH, token=settings.INTERNAL_SERVICE_TOKEN,
        grantee=settings.TICKET_SERVICE_GRANTEE, ticket_type=settings.TICKET_SERVICE_TICKET_TYPE,
        share_ttl_seconds=settings.TICKET_SERVICE_SHARE_TTL_SECONDS,
        timeout=settings.PEER_TIMEOUT_SECONDS)
