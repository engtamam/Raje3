"""§6's BYOK Google Places key — the properties worth a test:

  * a manager's own key resolves before any platform-wide default
  * a platform-wide default (tenant="") is used when he has set none
  * with neither, the deploy-time env fallback applies
  * `info()` never returns his own key's plaintext, and never reports a platform default as his
"""
from __future__ import annotations

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.leads import LeadSourcingKeys
from app.core.secret_store import SecretStore

KEK = "k" * 32


def build(store, *, fallback: str = "") -> LeadSourcingKeys:
    secret_store = SecretStore(store, KEK)
    return LeadSourcingKeys(secret_store=secret_store, fallback_api_key=fallback)


@pytest.mark.anyio
async def test_a_managers_own_key_resolves():
    store = MemoryDataStore()
    keys = build(store)
    await keys.set_key("mgr-1", value="AIzaOwnKey123", actor_ref="mgr-1")
    assert await keys.resolve("mgr-1") == "AIzaOwnKey123"


@pytest.mark.anyio
async def test_with_no_key_of_his_own_the_platform_wide_default_applies():
    store = MemoryDataStore()
    secret_store = SecretStore(store, KEK)
    await secret_store.set(tenant="", name="leads_places_api_key", value="AIzaPlatformDefault")
    keys = LeadSourcingKeys(secret_store=secret_store)

    assert await keys.resolve("mgr-with-no-key") == "AIzaPlatformDefault"


@pytest.mark.anyio
async def test_with_neither_the_env_fallback_applies():
    store = MemoryDataStore()
    keys = build(store, fallback="AIzaEnvFallback")
    assert await keys.resolve("mgr-with-nothing") == "AIzaEnvFallback"


@pytest.mark.anyio
async def test_a_managers_own_key_wins_over_the_platform_default():
    store = MemoryDataStore()
    secret_store = SecretStore(store, KEK)
    await secret_store.set(tenant="", name="leads_places_api_key", value="AIzaPlatformDefault")
    keys = LeadSourcingKeys(secret_store=secret_store)
    await keys.set_key("mgr-1", value="AIzaOwnKey", actor_ref="mgr-1")

    assert await keys.resolve("mgr-1") == "AIzaOwnKey"


@pytest.mark.anyio
async def test_info_reports_a_hint_never_the_value():
    store = MemoryDataStore()
    keys = build(store)
    await keys.set_key("mgr-1", value="AIzaSuperSecretValue", actor_ref="mgr-1")
    info = await keys.info("mgr-1")
    assert info is not None
    assert "AIzaSuperSecretValue" not in info.hint
    assert info.hint.endswith("alue")


@pytest.mark.anyio
async def test_info_is_none_when_he_set_nothing_even_if_a_platform_default_exists():
    store = MemoryDataStore()
    secret_store = SecretStore(store, KEK)
    await secret_store.set(tenant="", name="leads_places_api_key", value="AIzaPlatformDefault")
    keys = LeadSourcingKeys(secret_store=secret_store)

    assert await keys.info("mgr-with-no-key") is None


@pytest.mark.anyio
async def test_clearing_his_key_falls_back_again():
    store = MemoryDataStore()
    keys = build(store, fallback="AIzaEnvFallback")
    await keys.set_key("mgr-1", value="AIzaOwnKey", actor_ref="mgr-1")
    assert await keys.resolve("mgr-1") == "AIzaOwnKey"

    cleared = await keys.clear_key("mgr-1")
    assert cleared is True
    assert await keys.resolve("mgr-1") == "AIzaEnvFallback"
