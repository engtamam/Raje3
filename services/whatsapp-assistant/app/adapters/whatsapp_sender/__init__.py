"""WhatsAppSender adapters. build() wires both halves — see app/ports/whatsapp_sender.py."""
from __future__ import annotations

from typing import Any

from app.adapters.whatsapp_sender.direct import DirectCloudApiSender, NullDirectSender
from app.adapters.whatsapp_sender.template import NullTemplateSender, TemplateSender


class SendFailed(Exception):
    """Transient: the caller may retry with the same idempotency_key."""


class CompositeSender:
    """Routes to the template sender or the direct Cloud API sender depending on the call made.

    Not a "driver" in the allowlist sense — both halves are always built, because a conversation
    genuinely needs both shapes in its lifetime (an interactive proposal now, a re-engagement
    template days later once the 24h window has closed).
    """
    driver = "composite"

    def __init__(self, *, template: Any, direct: Any) -> None:
        self._template = template
        self._direct = direct

    async def send_template(self, **kwargs) -> str:
        return await self._template.send_template(**kwargs)

    async def send_interactive(self, **kwargs) -> str:
        return await self._direct.send_interactive(**kwargs)


def build(settings: Any, *, secret_store: Any = None) -> CompositeSender:
    if settings.NOTIFICATION_SERVICE_URL:
        template: Any = TemplateSender(
            notify_url=settings.NOTIFICATION_SERVICE_URL,
            notify_path=settings.NOTIFICATION_SEND_PATH,
            token=settings.INTERNAL_SERVICE_TOKEN,
            timeout=settings.PEER_TIMEOUT_SECONDS)
    else:
        template = NullTemplateSender()

    if secret_store is not None:
        direct: Any = DirectCloudApiSender(
            secret_store=secret_store,
            api_base=settings.META_GRAPH_API_BASE,
            api_version=settings.META_GRAPH_API_VERSION,
            timeout=settings.PEER_TIMEOUT_SECONDS)
    else:
        direct = NullDirectSender()

    return CompositeSender(template=template, direct=direct)
