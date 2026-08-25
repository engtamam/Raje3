"""WhatsAppSender port — two adapters for two message shapes /internal/notify cannot both cover.

notification-service's `/internal/notify` (see services/reminders/app/adapters/message_sender for
the exact HTTP client / header / idempotency-key pattern this imitates) is TEMPLATE-ONLY: an
approved Meta template plus positional variables. There is no field, and no code path, for an
interactive button/list message.

This assistant needs BOTH shapes:

  TemplateSender        an approved template, for an async/re-engagement send OUTSIDE the 24h
                        customer-service window — identical shape to reminders' HttpSender, so
                        this reuses that exact request contract against the same endpoint.

  DirectCloudApiSender  an interactive button/list message, INSIDE the 24h window that opened when
                        the customer messaged us. Meta's Cloud API allows free-form interactive
                        messages in that window without a pre-approved template; notification-
                        service has no route for that shape, so this adapter calls Meta's Graph API
                        directly, using a per-tenant WhatsApp access token sealed in this service's
                        own SecretStore (app/core/secret_store.py — same operator-credential
                        convention as every other service).

# ESCALATED: platform's /internal/notify should eventually grow interactive-message support so
# DirectCloudApiSender can retire and every outbound WhatsApp send in the platform goes through one
# audited, rate-limited, ceiling-aware peer instead of two. See deploy/services/whatsapp-assistant.
# values.yaml for the same note in operator-facing form.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class WhatsAppSender(Protocol):
    driver: str

    async def send_template(self, *, tenant: str, to: str, template_name: str,
                             variables: list[str], idempotency_key: str) -> str: ...

    async def send_interactive(self, *, tenant: str, to: str, body: str,
                                buttons: list[dict[str, str]], idempotency_key: str) -> str: ...
