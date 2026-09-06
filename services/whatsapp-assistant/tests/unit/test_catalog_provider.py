"""CatalogProvider — the port shape, NullCatalogProvider's zero-infra default, and
PlatformCatalogProvider's composition of service_catalog/package_catalog + absence-disciplined
image_url resolution."""
from __future__ import annotations

import asyncio

from app.core.catalog_provider import NullCatalogProvider, PlatformCatalogProvider, build
from app.ports.catalog_provider import CatalogCard, CatalogProvider


def run(c):
    return asyncio.run(c)


class FakeCatalog:
    def __init__(self, rows):
        self._rows = rows

    async def list_active(self, tenant):
        return self._rows


def test_null_provider_conforms_to_the_port_and_returns_nothing():
    provider = NullCatalogProvider()
    assert isinstance(provider, CatalogProvider)
    assert provider.driver == "null"
    assert run(provider.list_cards(tenant="t1")) == []


def test_platform_provider_conforms_to_the_port():
    provider = PlatformCatalogProvider(
        service_catalog=FakeCatalog([]), package_catalog=FakeCatalog([]),
        image_url_base="http://operations:8000/internal/operations/catalogue/{}/{}/image")
    assert isinstance(provider, CatalogProvider)
    assert provider.driver == "platform"


def test_services_and_packages_both_become_cards_with_the_right_kind():
    provider = PlatformCatalogProvider(
        service_catalog=FakeCatalog([{"id": "srv_1", "name": "قص شعر", "price_minor": 5000,
                                      "has_image": False}]),
        package_catalog=FakeCatalog([{"id": "pkg_1", "name": "باقة", "price_minor": 12000,
                                      "has_image": False}]),
        image_url_base="http://operations:8000/internal/operations/catalogue/{}/{}/image")
    cards = run(provider.list_cards(tenant="t1"))
    assert cards == [
        CatalogCard(id="srv_1", kind="service", name="قص شعر", price_minor=5000),
        CatalogCard(id="pkg_1", kind="package", name="باقة", price_minor=12000),
    ]


def test_an_item_with_no_photo_carries_no_image_url_never_a_placeholder():
    provider = PlatformCatalogProvider(
        service_catalog=FakeCatalog([{"id": "srv_1", "name": "قص شعر", "price_minor": 5000,
                                      "has_image": False}]),
        package_catalog=FakeCatalog([]),
        image_url_base="http://operations:8000/internal/operations/catalogue/{}/{}/image")
    card = run(provider.list_cards(tenant="t1"))[0]
    assert card.image_url == ""


def test_an_item_with_a_photo_gets_a_real_resolved_url():
    provider = PlatformCatalogProvider(
        service_catalog=FakeCatalog([{"id": "srv_1", "name": "قص شعر", "price_minor": 5000,
                                      "has_image": True}]),
        package_catalog=FakeCatalog([]),
        image_url_base="http://operations:8000/internal/operations/catalogue/{}/{}/image")
    card = run(provider.list_cards(tenant="t1"))[0]
    assert card.image_url == "http://operations:8000/internal/operations/catalogue/service/srv_1/image"


def test_limit_is_respected_across_services_and_packages_combined():
    provider = PlatformCatalogProvider(
        service_catalog=FakeCatalog([
            {"id": "srv_1", "name": "a", "price_minor": 100, "has_image": False},
            {"id": "srv_2", "name": "b", "price_minor": 100, "has_image": False},
        ]),
        package_catalog=FakeCatalog([
            {"id": "pkg_1", "name": "c", "price_minor": 100, "has_image": False},
        ]),
        image_url_base="http://operations:8000/internal/operations/catalogue/{}/{}/image")
    cards = run(provider.list_cards(tenant="t1", limit=2))
    assert len(cards) == 2


def test_build_wires_the_operations_url_and_path_into_one_template():
    class _Settings:
        OPERATIONS_SERVICE_URL = "http://operations:8000"
        OPERATIONS_CATALOGUE_IMAGE_PATH = "/internal/operations/catalogue/{}/{}/image"

    provider = build(_Settings(), service_catalog=FakeCatalog([
        {"id": "srv_1", "name": "a", "price_minor": 100, "has_image": True}]),
        package_catalog=FakeCatalog([]))
    card = run(provider.list_cards(tenant="t1"))[0]
    assert card.image_url == "http://operations:8000/internal/operations/catalogue/service/srv_1/image"
