"""core/marketplaces/salla.py — signature verification and connection storage, no network."""
from __future__ import annotations

import asyncio
import hashlib
import hmac

from app.adapters.datastore.memory import MemoryDataStore
from app.core.marketplaces.salla import (
    SallaClient,
    SallaService,
    verify_signature,
)


def run(coro):
    return asyncio.run(coro)


# ── signature verification ──────────────────────────────────────────────────────────────────────
def test_a_correctly_signed_body_verifies():
    secret = "wh_secret_123"
    body = b'{"event":"order.created","merchant":42}'
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_signature(secret, body, sig) is True


def test_a_wrong_signature_is_refused():
    secret = "wh_secret_123"
    body = b'{"event":"order.created","merchant":42}'
    assert verify_signature(secret, body, "0" * 64) is False


def test_a_signature_computed_over_different_bytes_is_refused():
    """The classic re-serialisation bug — if the caller hashed a re-encoded JSON string instead
    of the exact bytes Salla sent, verification must fail, not silently pass."""
    secret = "wh_secret_123"
    original = b'{"event": "order.created", "merchant": 42}'
    reencoded = b'{"event":"order.created","merchant":42}'
    sig_over_original = hmac.new(secret.encode(), original, hashlib.sha256).hexdigest()
    assert verify_signature(secret, reencoded, sig_over_original) is False


def test_no_secret_configured_always_refuses():
    """An empty SALLA_WEBHOOK_SECRET (not configured yet) must never verify ANY signature — the
    alternative (empty secret => hmac of b'' => a real, guessable hash) would let a caller who
    knows the integration is unconfigured forge a "verified" event."""
    body = b'{"event":"order.created"}'
    sig = hmac.new(b"", body, hashlib.sha256).hexdigest()
    assert verify_signature("", body, sig) is False


def test_no_signature_header_always_refuses():
    assert verify_signature("secret", b"{}", "") is False


# ── SallaClient — configured-ness and URL shape, no network ────────────────────────────────────
def test_client_is_not_configured_with_a_missing_piece():
    assert SallaClient(client_id="", client_secret="s", redirect_uri="https://x/cb").configured is False
    assert SallaClient(client_id="i", client_secret="", redirect_uri="https://x/cb").configured is False
    assert SallaClient(client_id="i", client_secret="s", redirect_uri="").configured is False


def test_client_is_configured_with_all_three():
    assert SallaClient(client_id="i", client_secret="s", redirect_uri="https://x/cb").configured is True


def test_authorize_url_carries_every_required_param():
    c = SallaClient(client_id="my_client", client_secret="s", redirect_uri="https://x/cb")
    url = c.authorize_url("the-state-value")
    assert url.startswith("https://accounts.salla.sa/oauth2/auth?")
    assert "client_id=my_client" in url
    assert "response_type=code" in url
    assert "state=the-state-value" in url
    assert "redirect_uri=https" in url


def test_authorize_url_refuses_when_unconfigured():
    import pytest
    from app.core.marketplaces.salla import SallaConfigError

    c = SallaClient(client_id="", client_secret="", redirect_uri="")
    with pytest.raises(SallaConfigError):
        c.authorize_url("state")


# ── SallaService — storage ──────────────────────────────────────────────────────────────────────
def test_a_new_connection_can_be_saved_and_read_back():
    svc = SallaService(store=MemoryDataStore(), client=SallaClient(
        client_id="i", client_secret="s", redirect_uri="https://x/cb"))
    run(svc.save_connection(tenant="tnt_1", merchant_id="42", store_name="متجري",
                            access_token="at", refresh_token="rt", expires_at=999999, scope="x"))
    conn = run(svc.connection_for("tnt_1"))
    assert conn is not None
    assert conn.merchant_id == "42"
    assert conn.store_name == "متجري"


def test_public_never_carries_either_token():
    svc = SallaService(store=MemoryDataStore(), client=SallaClient(
        client_id="i", client_secret="s", redirect_uri="https://x/cb"))
    run(svc.save_connection(tenant="tnt_1", merchant_id="42", store_name="متجري",
                            access_token="super-secret-at", refresh_token="super-secret-rt",
                            expires_at=999999, scope="x"))
    conn = run(svc.connection_for("tnt_1"))
    public = conn.public()
    assert "access_token" not in public
    assert "refresh_token" not in public
    assert "super-secret-at" not in str(public)
    assert "super-secret-rt" not in str(public)


def test_no_connection_reads_as_none_not_an_error():
    svc = SallaService(store=MemoryDataStore(), client=SallaClient(
        client_id="i", client_secret="s", redirect_uri="https://x/cb"))
    assert run(svc.connection_for("tnt_nobody")) is None


def test_reconnecting_the_same_tenant_keeps_the_original_connected_at():
    svc = SallaService(store=MemoryDataStore(), client=SallaClient(
        client_id="i", client_secret="s", redirect_uri="https://x/cb"))
    first = run(svc.save_connection(tenant="tnt_1", merchant_id="42", store_name="م",
                                    access_token="at1", refresh_token="rt1",
                                    expires_at=100, scope="x"))
    second = run(svc.save_connection(tenant="tnt_1", merchant_id="42", store_name="م",
                                     access_token="at2", refresh_token="rt2",
                                     expires_at=200, scope="x"))
    assert second.connected_at == first.connected_at
    assert second.access_token == "at2"


def test_connection_for_merchant_finds_the_right_tenant_by_merchant_id():
    svc = SallaService(store=MemoryDataStore(), client=SallaClient(
        client_id="i", client_secret="s", redirect_uri="https://x/cb"))
    run(svc.save_connection(tenant="tnt_a", merchant_id="111", store_name="أ",
                            access_token="a", refresh_token="a", expires_at=1, scope=""))
    run(svc.save_connection(tenant="tnt_b", merchant_id="222", store_name="ب",
                            access_token="b", refresh_token="b", expires_at=1, scope=""))
    found = run(svc.connection_for_merchant("222"))
    assert found is not None and found.tenant == "tnt_b"


def test_connection_for_merchant_is_none_for_an_unknown_merchant():
    svc = SallaService(store=MemoryDataStore(), client=SallaClient(
        client_id="i", client_secret="s", redirect_uri="https://x/cb"))
    assert run(svc.connection_for_merchant("does-not-exist")) is None


def test_update_tokens_changes_only_the_tokens():
    svc = SallaService(store=MemoryDataStore(), client=SallaClient(
        client_id="i", client_secret="s", redirect_uri="https://x/cb"))
    run(svc.save_connection(tenant="tnt_1", merchant_id="42", store_name="متجري",
                            access_token="at1", refresh_token="rt1", expires_at=100, scope="x"))
    updated = run(svc.update_tokens(
        "tnt_1", access_token="at2", refresh_token="rt2", expires_at=200))
    assert updated is not None
    assert updated.access_token == "at2" and updated.refresh_token == "rt2"
    assert updated.expires_at == 200
    assert updated.merchant_id == "42" and updated.store_name == "متجري"


def test_update_tokens_on_an_unknown_tenant_returns_none():
    svc = SallaService(store=MemoryDataStore(), client=SallaClient(
        client_id="i", client_secret="s", redirect_uri="https://x/cb"))
    assert run(svc.update_tokens(
        "tnt_ghost", access_token="a", refresh_token="r", expires_at=1)) is None


def test_connections_expiring_before_finds_only_the_soon_ones():
    svc = SallaService(store=MemoryDataStore(), client=SallaClient(
        client_id="i", client_secret="s", redirect_uri="https://x/cb"))
    run(svc.save_connection(tenant="tnt_soon", merchant_id="1", store_name="أ",
                            access_token="a", refresh_token="a", expires_at=100, scope=""))
    run(svc.save_connection(tenant="tnt_later", merchant_id="2", store_name="ب",
                            access_token="b", refresh_token="b", expires_at=100000, scope=""))
    due = run(svc.connections_expiring_before(1000))
    assert [c.tenant for c in due] == ["tnt_soon"]


def test_disconnect_removes_the_connection_and_returns_true():
    svc = SallaService(store=MemoryDataStore(), client=SallaClient(
        client_id="i", client_secret="s", redirect_uri="https://x/cb"))
    run(svc.save_connection(tenant="tnt_1", merchant_id="42", store_name="متجري",
                            access_token="at", refresh_token="rt", expires_at=1, scope=""))
    assert run(svc.disconnect("tnt_1")) is True
    assert run(svc.connection_for("tnt_1")) is None


def test_disconnect_on_an_already_disconnected_tenant_returns_false_not_an_error():
    svc = SallaService(store=MemoryDataStore(), client=SallaClient(
        client_id="i", client_secret="s", redirect_uri="https://x/cb"))
    assert run(svc.disconnect("tnt_ghost")) is False


def test_disconnect_never_touches_a_different_tenants_connection():
    svc = SallaService(store=MemoryDataStore(), client=SallaClient(
        client_id="i", client_secret="s", redirect_uri="https://x/cb"))
    run(svc.save_connection(tenant="tnt_a", merchant_id="1", store_name="أ",
                            access_token="a", refresh_token="a", expires_at=1, scope=""))
    run(svc.save_connection(tenant="tnt_b", merchant_id="2", store_name="ب",
                            access_token="b", refresh_token="b", expires_at=1, scope=""))
    run(svc.disconnect("tnt_a"))
    assert run(svc.connection_for("tnt_a")) is None
    assert run(svc.connection_for("tnt_b")) is not None


def test_record_event_stores_verified_status_and_tenant():
    svc = SallaService(store=MemoryDataStore(), client=SallaClient(
        client_id="i", client_secret="s", redirect_uri="https://x/cb"))
    ev = run(svc.record_event(merchant_id="42", event="order.created", tenant="tnt_1",
                              verified=True))
    assert ev.verified is True
    assert ev.tenant == "tnt_1"
    assert ev.event == "order.created"
