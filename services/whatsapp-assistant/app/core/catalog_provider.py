"""CatalogProvider adapters — see app/ports/catalog_provider.py's own docstring for the port and
why it exists ahead of any real consumer.

PlatformCatalogProvider IS A THIN COMPOSITION, NOT A NEW HTTP CLIENT. It reuses
core/service_catalog.py and core/package_catalog.py exactly as core/context_builder.py already
does — the same peer reads, the same fields, adding only the image_url resolution neither of those
modules had a reason to do on their own (context_builder's text prompt has no use for a URL).
"""
from __future__ import annotations

from typing import Any

from app.ports.catalog_provider import CatalogCard


class NullCatalogProvider:
    """No operations peer configured (dev/test default). Never blocks a caller — the same
    zero-infra posture as every other optional peer in this service."""
    driver = "null"

    async def list_cards(self, *, tenant: str, limit: int = 10) -> list[CatalogCard]:
        return []


class PlatformCatalogProvider:
    """Our own platform's services + packages, images included — for a shop that IS subscribed."""
    driver = "platform"

    def __init__(self, *, service_catalog: Any, package_catalog: Any, image_url_base: str) -> None:
        self._services = service_catalog
        self._packages = package_catalog
        # A template with two `{}` placeholders (kind, item_id) — filled in per card below, never
        # re-derived per call from settings, so a test can pass one directly.
        self._image_url_template = image_url_base

    def _image_url(self, *, kind: str, item_id: str, has_image: bool) -> str:
        if not has_image:
            return ""
        return self._image_url_template.format(kind, item_id)

    async def list_cards(self, *, tenant: str, limit: int = 10) -> list[CatalogCard]:
        services = await self._services.list_active(tenant)
        packages = await self._packages.list_active(tenant)
        cards: list[CatalogCard] = []
        for s in services:
            cards.append(CatalogCard(
                id=str(s["id"]), kind="service", name=str(s.get("name", "")),
                price_minor=int(s.get("price_minor") or 0),
                image_url=self._image_url(kind="service", item_id=str(s["id"]),
                                          has_image=bool(s.get("has_image")))))
        for p in packages:
            cards.append(CatalogCard(
                id=str(p["id"]), kind="package", name=str(p.get("name", "")),
                price_minor=int(p.get("price_minor") or 0),
                image_url=self._image_url(kind="package", item_id=str(p["id"]),
                                          has_image=bool(p.get("has_image")))))
        return cards[:limit] if limit else cards


def build(settings: Any, *, service_catalog: Any, package_catalog: Any) -> PlatformCatalogProvider:
    """Unconditional — app/container.py's own if/elif on CATALOG_PROVIDER_DRIVER picks whether to
    call this at all, the same shape booking.py::build/booking_assignment.py::build already use
    (each module builds ITS OWN provider; container.py is the one place that chooses)."""
    template = (settings.OPERATIONS_SERVICE_URL.rstrip("/")
               + settings.OPERATIONS_CATALOGUE_IMAGE_PATH)
    return PlatformCatalogProvider(
        service_catalog=service_catalog, package_catalog=package_catalog,
        image_url_base=template)
