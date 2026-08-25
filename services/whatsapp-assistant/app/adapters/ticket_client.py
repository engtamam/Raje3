"""TicketClient — opens a human-escalation ticket in platform's ticket-service.

# ESCALATED: ticket-service has no /internal/* ticket-creation route — its internal tier
(platform/services/ticket-service/app/api/internal.py) only carries backup/erase/notification-
drain, the exact same shape services/reminders and services/loyalty's internal tiers carry. Ticket
creation lives on the v1 tier instead (`POST /api/v1/tickets`, app/api/v1/tickets.py there), behind
a real capability-bearing Bearer token (tickets.self / tickets.manage / platform.tickets) verified
by ticket-service's own TokenVerifier — never X-Internal-Token. So this client cannot reuse the
X-Internal-Token peer shape `core/customer_lookup.py` / `core/points.py` use against operations and
loyalty's internal tiers.

Instead it mints its own short-lived HS256 service token — the SAME posture
services/operations/app/adapters/settlements.py already takes against billing-service's admin
tier (a machine credential minted for exactly one cross-service call, because the peer's internal
tier does not cover it), except HS256 needs no round trip: it is signed locally with
TICKET_SERVICE_JWT_SECRET, which must be the SAME shared secret ticket-service's own
TOKEN_HS256_SECRET holds (class of INTERNAL_SERVICE_TOKEN / PII_SALT — a fleet-wide shared value,
not this service's own). The narrowest real fix is an `/internal/tickets` route on ticket-service
accepting X-Internal-Token like every other peer call this service makes; that is platform/, and
out of scope here — tracked in this comment the way settlements.py tracks its own equivalent gap.

PII AT THIS BOUNDARY (documented per the design point that asked for the reasoning, not just the
code): the ticket body carries the conversation's ROLLING SUMMARY, never the raw transcript — the
same "never a second transcript" rule `core/conversation.py` already applies to what the LLM sees.
The customer's real phone number DOES go in `metadata.contact`, and that is a deliberate boundary
decision, not an oversight: a human agent assigned this ticket needs a real way to call the
customer back, and ticket-service is reached only by staff already authenticated with a
capability-gated Bearer token — the same class of "trusted internal surface that legitimately
handles real PII" `DirectCloudApiSender` already treats a WhatsApp send destination as (see
app/adapters/whatsapp_sender/direct.py). It is NOT the LLM prompt, which per `core/conversation.py`
::opaque_reference never sees a real name or number at all. Withholding the number here would only
mean the human agent who inherits this conversation cannot do the one thing they were escalated in
to do.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

import jwt


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

    def __init__(self, *, url: str, path: str, secret: str, issuer: str, audience: str,
                ttl_seconds: int, ticket_type: str, capability: str, timeout: int = 8) -> None:
        self._url = url.rstrip("/") + path
        self._secret = secret
        self._issuer = issuer
        self._audience = audience
        self._ttl = max(1, ttl_seconds)
        self._type = ticket_type
        self._capability = capability
        self._timeout = timeout

    def _mint(self, tenant: str) -> str:
        # Minted PER CALL, per tenant — the claim ticket-service reads its tenant scope from
        # (`Principal.tenant`) varies by call, so this cannot be cached across tenants the way
        # settlements.py caches its single-tenant admin credential. Cheap: a local HMAC sign, no
        # network round trip, unlike an OAuth client-credentials exchange.
        now = int(time.time())
        claims: dict[str, Any] = {
            "sub": "whatsapp-assistant", "tenant": tenant, "caps": [self._capability],
            "iat": now, "exp": now + self._ttl,
        }
        if self._issuer:
            claims["iss"] = self._issuer
        if self._audience:
            claims["aud"] = self._audience
        return jwt.encode(claims, self._secret, algorithm="HS256")

    async def open_ticket(self, *, tenant: str, subject: str, body: str, ref_id: str,
                          contact: str = "", priority: str = "normal") -> dict[str, Any]:
        token = self._mint(tenant)
        metadata: dict[str, Any] = {"channel": "whatsapp"}
        if contact:
            metadata["contact"] = contact
        payload = {
            "type": self._type,
            "subject": subject[:512],
            "body": body[:20_000],
            "ref": {"kind": "whatsapp_conversation", "id": ref_id[:256]},
            "priority": priority,
            "metadata": metadata,
        }
        req = urllib.request.Request(
            self._url, data=json.dumps(payload).encode(), method="POST",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                if not 200 <= resp.status < 300:
                    raise TicketOpenFailed(f"ticket-service returned {resp.status}")
                return json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as exc:
            raise TicketOpenFailed(f"ticket-service returned {exc.code}") from exc
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise TicketOpenFailed(f"ticket-service unreachable: {exc}") from exc


def build(settings: Any) -> Any:
    if not settings.TICKET_SERVICE_URL or not settings.TICKET_SERVICE_JWT_SECRET:
        return NullTicketClient()
    return HttpTicketClient(
        url=settings.TICKET_SERVICE_URL, path=settings.TICKET_SERVICE_TICKETS_PATH,
        secret=settings.TICKET_SERVICE_JWT_SECRET, issuer=settings.TICKET_SERVICE_JWT_ISSUER,
        audience=settings.TICKET_SERVICE_JWT_AUDIENCE,
        ttl_seconds=settings.TICKET_SERVICE_JWT_TTL_SECONDS,
        ticket_type=settings.TICKET_SERVICE_TICKET_TYPE,
        capability=settings.TICKET_SERVICE_CAPABILITY,
        timeout=settings.PEER_TIMEOUT_SECONDS)
