"""WhatsAppSender adapters. build() wires both halves — see app/ports/whatsapp_sender.py."""
from __future__ import annotations

from typing import Any

from app.adapters.whatsapp_sender.carousel import CarouselSender, NullCarouselSender
from app.adapters.whatsapp_sender.direct import InteractiveNotifySender, NullDirectSender
from app.adapters.whatsapp_sender.template import NullTemplateSender, TemplateSender


class SendFailed(Exception):
    """Transient: the caller may retry with the same idempotency_key."""


class CompositeSender:
    """Routes to the template sender, the interactive sender, or the carousel sender depending on
    the call made.

    Not a "driver" in the allowlist sense — every half is always built, because a conversation
    genuinely needs each shape at some point in its lifetime (an interactive proposal now, a
    re-engagement template days later, a catalog carousel whenever the AI decides one is worth
    showing). All three now go through notification-service (TemplateSender via /internal/notify,
    InteractiveNotifySender via /internal/notify/whatsapp/interactive, CarouselSender via
    /internal/notify/whatsapp/carousel + the media-upload routes) — this service holds no WhatsApp
    send credential itself.
    """
    driver = "composite"

    def __init__(self, *, template: Any, direct: Any, carousel: Any) -> None:
        self._template = template
        self._direct = direct
        self._carousel = carousel

    async def send_template(self, **kwargs) -> str:
        return await self._template.send_template(**kwargs)

    async def send_interactive(self, **kwargs) -> str:
        return await self._direct.send_interactive(**kwargs)

    async def send_list(self, **kwargs) -> str:
        return await self._direct.send_list(**kwargs)

    async def send_carousel(self, **kwargs) -> str:
        return await self._carousel.send_carousel(**kwargs)

    async def send_single_card(self, **kwargs) -> str:
        return await self._carousel.send_single_card(**kwargs)


def build(settings: Any, *, secret_store: Any = None) -> CompositeSender:
    if settings.NOTIFICATION_SERVICE_URL:
        template: Any = TemplateSender(
            notify_url=settings.NOTIFICATION_SERVICE_URL,
            notify_path=settings.NOTIFICATION_SEND_PATH,
            token=settings.INTERNAL_SERVICE_TOKEN,
            timeout=settings.PEER_TIMEOUT_SECONDS)
        direct: Any = InteractiveNotifySender(
            notify_url=settings.NOTIFICATION_SERVICE_URL,
            notify_path=settings.NOTIFICATION_INTERACTIVE_SEND_PATH,
            token=settings.INTERNAL_SERVICE_TOKEN,
            timeout=settings.PEER_TIMEOUT_SECONDS)
        carousel: Any = CarouselSender(
            notify_url=settings.NOTIFICATION_SERVICE_URL,
            carousel_path=settings.NOTIFICATION_CAROUSEL_SEND_PATH,
            media_upload_path=settings.NOTIFICATION_MEDIA_UPLOAD_ID_PATH,
            interactive_path=settings.NOTIFICATION_INTERACTIVE_SEND_PATH,
            token=settings.INTERNAL_SERVICE_TOKEN,
            timeout=settings.PEER_TIMEOUT_SECONDS)
    else:
        template = NullTemplateSender()
        direct = NullDirectSender()
        carousel = NullCarouselSender()

    return CompositeSender(template=template, direct=direct, carousel=carousel)
