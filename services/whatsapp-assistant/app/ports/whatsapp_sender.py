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

from app.ports.catalog_provider import CatalogCard


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

    # A real media-card carousel — see app/adapters/whatsapp_sender/carousel.py's own module
    # docstring for the two-step (fetch photo, upload as a Meta media id) send this requires, and
    # app/ports/catalog_provider.py for where `cards` comes from. Same business-initiated-template
    # posture as send_template: a carousel is ALWAYS an approved template on WhatsApp's platform,
    # never a free-form session message, whatever window the conversation is inside.
    async def send_carousel(self, *, tenant: str, to: str, template_name: str, language: str,
                            cards: list[CatalogCard], idempotency_key: str) -> str: ...

    # ONE card, photo + text + a single quick-reply button — the INVITE shape, not a carousel of
    # one (Meta's carousel component needs 2+ cards). Session-message posture like send_interactive
    # (no template, inside the 24h window), with a media header (platform v0.22.9) instead of
    # send_interactive's text-only header — see carousel.py's own docstring on why it lives beside
    # send_carousel rather than as a third adapter class.
    async def send_single_card(self, *, tenant: str, to: str, card: CatalogCard,
                               idempotency_key: str) -> str: ...
