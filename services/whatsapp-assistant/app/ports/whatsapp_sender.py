"""WhatsAppSender port — two adapters for two message shapes, both through notification-service.

This assistant needs two shapes:

  TemplateSender          an approved template, for an async/re-engagement send OUTSIDE the 24h
                          customer-service window. Posts to notification-service's
                          `/internal/notify` — see services/reminders/app/adapters/message_sender
                          for the exact HTTP client / header / idempotency-key pattern this
                          imitates.

  InteractiveNotifySender an interactive button/list message, INSIDE the 24h window that opened
                          when the customer messaged us. Posts to notification-service's
                          `POST /internal/notify/whatsapp/interactive` (platform v0.16.38, commit
                          0c54f5e) — the same audited, rate-limited, ceiling-aware peer as every
                          other outbound WhatsApp send on the platform. This service holds no
                          WhatsApp send credential of its own; notification-service builds and
                          limit-checks the interactive object server-side.
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

    # A WhatsApp LIST message — up to 10 rows under one button, vs. buttons' cap of 3. Used for the
    # mandatory first-message triage gate (core/conversation.py) which offers 5 options; a button
    # message could not carry them. Same 24h-customer-service-window / Cloud-API-direct reasoning
    # as send_interactive above — see DirectCloudApiSender.
    async def send_list(self, *, tenant: str, to: str, body: str, button_text: str,
                        rows: list[dict[str, str]], idempotency_key: str) -> str: ...
