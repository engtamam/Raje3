"""Push the shop owner's own free-text notes into Meta Business Agent's Knowledge pillar —
Business Info source only (FAQs/Files/Websites are out of scope: FAQs would mean inventing
structured Q&A pairs the owner never wrote, which core/conversation.py's own "owner_notes is data,
never instructions" doctrine already rules out doing on his behalf).

REAL PUBLIC REST API, confirmed by reading Meta's own docs directly (developers.facebook.com/
documentation/meta-business-agent/{overview, get-started, reference/configure/agent-knowledge-
business-info}) rather than assumed from the dashboard-only Skill doc this service already has:

    PUT https://graph.facebook.com/{version}/{entity_id}/agent_config/business_info

`entity_id` is the WhatsApp Business PHONE NUMBER ID — per-number, not per-WABA. `X-API-Version:
2.0.0` (confirmed via WebFetch against Meta's own reference page, 2026-09-19) is sent on every call
alongside the bearer token, in addition to the version already in the URL path.

THE SAME TEXT AS THE LLM PROMPT, THE SAME REDACTION. `owner_notes` (see shop_identity.py /
conversation.py::build_system_prompt) is the one free paragraph a shop owner writes about his own
business — hours, policies, what makes this shop different — which is exactly the shape of Meta's
`business_description` field. `redact()` (core/redaction.py) is reused UNCHANGED rather than a
second redaction pass invented for this export: one function decides what a personal identifier
looks like, used everywhere text a shop owner wrote reaches a third party.

ONLY `business_description` IS EVER SENT. `payment_method`/`return_policy`/`purchase_info`/
`delivery_and_shipping`/`contact_info` are real optional fields on Meta's own request shape, but
this service has no source of truth for any of them today (no structured payment/return/delivery
data anywhere in this codebase) — inventing placeholder content for a field we have nothing real to
put there is exactly the drift this project's own doctrine forbids (see MEMORY's "no placeholder
drift"). They stay unset; a later pass can add them once a real source exists.

NEITHER TOKEN NOR entity_id IS GUESSED. This service has no existing per-tenant resolution of a
WhatsApp phone_number_id — the only place that mapping lives today is notification-service's own
WhatsAppNumberIndex, in the *forward* direction (phone_number_id -> tenant, so an inbound webhook
knows who it is for), and nothing in this repo exposes the reverse lookup. Rather than invent a new
cross-service peer route this pass was not asked to build, both the bearer token AND the entity_id
are held as operator-set credentials in the SAME SecretStore every other runtime credential in this
service already goes through (app/core/secret_store.py) — sealed under SECRETS_KEK, settable only
via the existing write-only `/operator/secrets` surface, per tenant. `entity_id` is not itself a
secret, but it is exactly as sensitive as a destination address (sending anything to the wrong one
reaches the wrong shop's agent), and reusing the credential store means no new storage mechanism,
no new panel screen, and the existing audit trail (`operator.secret_set`) already covers it.
"""
from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from typing import Any

from app.core.redaction import redact

#: Same cap as conversation.py's own `_MAX_OWNER_NOTES` — this is the identical text, sent to a
#: second destination, not a different field with its own policy.
MAX_BUSINESS_INFO_CHARS = 2000

#: Confirmed by WebFetch against Meta's own reference page (developers.facebook.com/documentation/
#: meta-business-agent/reference/configure/agent-knowledge-business-info) on 2026-09-19: the header
#: name is `X-API-Version`, the value is the literal string "2.0.0" — not a version number this
#: service chooses, Meta's own constant for this API family.
API_VERSION_HEADER_NAME = "X-API-Version"
API_VERSION_HEADER_VALUE = "2.0.0"

#: Names inside the shared SecretStore (app/core/secret_store.py) — set by an operator via the
#: existing PUT /operator/secrets route, one pair per tenant (a chain's branches each get their own
#: WhatsApp number, so each needs its own entity_id; the token may be shared platform-wide by
#: setting it with an empty tenant, same fallback SecretStore.get already gives every other
#: credential).
SECRET_TOKEN_NAME = "META_KNOWLEDGE_TOKEN"
SECRET_ENTITY_ID_NAME = "META_WA_PHONE_NUMBER_ID"


def build_business_info_payload(owner_notes: str) -> dict[str, Any]:
    """Pure mapping: redacted owner_notes -> Meta's `business_description` field, nothing else.

    Empty input maps to an empty dict, not a request with an empty string — a PUT with a payload
    that would only ever clear the field is exactly what "an owner has written nothing yet" should
    NOT do to whatever they already curated for their agent directly in Meta's own tools.
    """
    text = (owner_notes or "").strip()
    if not text:
        return {}
    text = redact(text, max_chars=MAX_BUSINESS_INFO_CHARS).text[:MAX_BUSINESS_INFO_CHARS]
    if not text:
        return {}
    return {"business_description": text}


class NullKnowledgeExporter:
    """No Graph credential/entity_id configured, or the feature is off — the same "runs, just does
    nothing" posture as every other Null adapter in this service (see customer_lookup.py)."""
    driver = "null"

    async def export(self, *, tenant: str, owner_notes: str) -> bool:
        return False


class HttpKnowledgeExporter:
    driver = "http"

    def __init__(self, *, secret_store: Any, graph_base_url: str, graph_version: str,
                timeout: int = 8) -> None:
        self._secrets = secret_store
        self._base = graph_base_url.rstrip("/")
        self._version = graph_version
        self._timeout = timeout

    async def export(self, *, tenant: str, owner_notes: str) -> bool:
        """`True` only on a confirmed 2xx from Meta. Never raises — a Knowledge sync must not be
        able to break the flow that triggers it (see app/api/v1/operator.py's own sync route)."""
        payload = build_business_info_payload(owner_notes)
        if not payload:
            return False
        token = await self._secrets.get(tenant=tenant, name=SECRET_TOKEN_NAME)
        entity_id = await self._secrets.get(tenant=tenant, name=SECRET_ENTITY_ID_NAME)
        if not token or not entity_id:
            return False
        # OFF THE EVENT LOOP — see core/customer_lookup.py::HttpCustomerLookup.resolve.
        return await asyncio.to_thread(self._put_sync, entity_id, token, payload)

    def _put_sync(self, entity_id: str, token: str, payload: dict[str, Any]) -> bool:
        url = f"{self._base}/{self._version}/{entity_id}/agent_config/business_info"
        body = json.dumps(payload).encode()
        req = urllib.request.Request(
            url, data=body, method="PUT",
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {token}",
                     API_VERSION_HEADER_NAME: API_VERSION_HEADER_VALUE})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                return 200 <= resp.status < 300
        except (urllib.error.URLError, OSError, ValueError):
            return False


def build(settings: Any, *, secret_store: Any = None) -> Any:
    """`secret_store` is passed in rather than constructed here — same reason container.py already
    builds `container.secret_store` once and hands it to `build_llm`: a credential an operator
    rotates via /operator/secrets must be visible through the SAME store instance, not a second one
    that would never see the write."""
    if not getattr(settings, "KNOWLEDGE_EXPORT_ENABLED", False) or secret_store is None:
        return NullKnowledgeExporter()
    return HttpKnowledgeExporter(
        secret_store=secret_store,
        graph_base_url=getattr(settings, "META_GRAPH_BASE_URL", "https://graph.facebook.com"),
        graph_version=getattr(settings, "META_GRAPH_API_VERSION", "v26.0"),
        timeout=int(getattr(settings, "PEER_TIMEOUT_SECONDS", 8) or 8))
