"""The TikTok webhook's own message path (Phase 3) — a `NEW_MESSAGE`-shaped event fetches the
real conversation, asks the tiktok-assistant connection for a reply, and sends it back through
TikTok's own signed Send Message call. `TikTokShopClient.get_conversation_messages`/`send_message`
and `HttpAssistantConnections.list/create/invoke` are all monkeypatched — no network, same
technique `test_tiktok_shop_api.py` uses for the order path.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os

import pytest
from fastapi.testclient import TestClient

APP_KEY = "test_app_key"
APP_SECRET = "test_app_secret"
TENANT = "tnt_tiktok_assist"
SALT = "s" * 32


def _make_app() -> TestClient:
    from app.config import get_settings

    os.environ.update({
        "ENV": "test", "INTERNAL_SERVICE_TOKEN": "t" * 40, "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": "h" * 40, "TOKEN_ISSUER": "iss", "TOKEN_AUDIENCE": "aud",
        "RATELIMIT_MAX": "1000", "PII_SALT": SALT, "PUBLIC_BASE_URL": "https://raje3.sa",
        "TIKTOK_SHOP_APP_KEY": APP_KEY, "TIKTOK_SHOP_APP_SECRET": APP_SECRET,
        "TIKTOK_SHOP_SERVICE_ID": "svc_123",
        "ASSISTANT_SERVICE_URL": "http://assistant-service:8000",
        "TIKTOK_ASSISTANT_MODEL_PROJECT": "proj-1",
        "TIKTOK_ASSISTANT_MODEL_CREDENTIAL": "cred",
    })
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture
def env_guard():
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
    from app.config import get_settings
    get_settings.cache_clear()


@pytest.fixture
def client(env_guard) -> TestClient:
    return _make_app()


def _connect(client: TestClient, *, tenant: str, shop_id: str) -> None:
    import asyncio
    asyncio.run(client.app.state.container.tiktok_shop.save_connection(
        tenant=tenant, shop_id=shop_id, seller_name="متجري", access_token="at",
        refresh_token="rt", access_token_expires_at=9999999999,
        refresh_token_expires_at=9999999999, scope="seller.customer_service"))


def _sign_webhook(app_key: str, app_secret: str, body: bytes) -> str:
    return hmac.new(app_secret.encode(), app_key.encode() + body, hashlib.sha256).hexdigest()


def _message_event_body(*, shop_id: str, conversation_id: str, notification_id: str) -> bytes:
    return json.dumps({
        "type": 9, "tts_notification_id": notification_id, "shop_id": shop_id,
        "timestamp": 1, "data": {"conversation_id": conversation_id},
    }).encode()


def _post_webhook(client: TestClient, body: bytes):
    sig = _sign_webhook(APP_KEY, APP_SECRET, body)
    return client.post("/api/v1/tiktok-shop/webhook", data=body,
                       headers={"Content-Type": "application/json", "Authorization": sig})


def _buyer_message(text: str) -> dict:
    return {"id": "m1", "type": "TEXT", "content": json.dumps({"content": text}),
           "create_time": 1, "sender": {"im_user_id": "buyer1", "role": "BUYER"},
           "plaintext": text}


class _FakeConnections:
    """A minimal fake of HttpAssistantConnections — records calls, answers a canned invoke
    result. Swapped onto `container.tiktok_assistant_connections` per test."""

    def __init__(self, invoke_result: dict | None = None) -> None:
        self._rows: dict[str, dict] = {}
        self.invoke_calls: list[dict] = []
        self._invoke_result = invoke_result or {"kind": "text", "text": "رد تجريبي"}

    def list(self, tenant: str) -> list[dict]:
        return [r for r in self._rows.values() if r.get("tenant") == tenant]

    def create(self, **body) -> dict:
        cid = f"conn_{len(self._rows) + 1}"
        row = {"id": cid, **body}
        self._rows[cid] = row
        return row

    def update(self, cid: str, **body) -> dict:
        self._rows[cid].update(body)
        return self._rows[cid]

    def invoke(self, cid: str, *, tenant: str, messages: list, max_tokens: int = 0) -> dict:
        self.invoke_calls.append({"cid": cid, "tenant": tenant, "messages": messages})
        return self._invoke_result


def _wire_fake_assistant(client: TestClient, invoke_result: dict | None = None) -> _FakeConnections:
    fake = _FakeConnections(invoke_result)
    client.app.state.container.tiktok_assistant_connections = fake
    return fake


def _wire_fake_shop_client(client: TestClient, *, messages: list[dict],
                          send_ok: bool = True) -> list[dict]:
    """Patches get_conversation_messages/send_message on the wired TikTokShopClient, and returns
    the list `send_message` calls append their (conversation_id, text) tuple to."""
    tt_client = client.app.state.container.tiktok_shop.client
    tt_client.get_conversation_messages = lambda **kw: messages
    sent: list[dict] = []

    def _send(*, access_token, shop_cipher, conversation_id, text):
        sent.append({"conversation_id": conversation_id, "text": text})
        return send_ok

    tt_client.send_message = _send
    return sent


def test_a_buyer_message_gets_a_real_reply_sent_back(client):
    _connect(client, tenant=TENANT, shop_id="shop_msg1")
    _wire_fake_assistant(client, {"kind": "text", "text": "أهلاً! طلبك بالطريق.\n[تصنيف: shipping_delay]"})
    sent = _wire_fake_shop_client(client, messages=[_buyer_message("وين طلبي؟")])

    body = _message_event_body(shop_id="shop_msg1", conversation_id="conv1",
                               notification_id="n-msg-1")
    r = _post_webhook(client, body)
    assert r.status_code == 200
    assert len(sent) == 1
    assert sent[0]["conversation_id"] == "conv1"
    assert sent[0]["text"] == "أهلاً! طلبك بالطريق."
    assert "[تصنيف:" not in sent[0]["text"]


def test_the_category_is_recorded_for_later_aggregation(client):
    _connect(client, tenant=TENANT, shop_id="shop_msg2")
    _wire_fake_assistant(client, {"kind": "text", "text": "رد\n[تصنيف: payment]"})
    _wire_fake_shop_client(client, messages=[_buyer_message("كيف أدفع؟")])

    body = _message_event_body(shop_id="shop_msg2", conversation_id="conv2",
                               notification_id="n-msg-2")
    _post_webhook(client, body)

    import asyncio
    rows, _ = asyncio.run(client.app.state.container.datastore.find(
        "tiktok_message_categories", {"tenant": TENANT, "category": "payment"}))
    assert len(rows) == 1
    assert rows[0]["source"] == "dm"
    assert rows[0]["conversation_id"] == "conv2"


def test_the_newest_message_being_our_own_reply_never_triggers_a_second_reply(client):
    """The infinite-loop guard — a webhook fired because OUR system-sent reply just landed in
    the same conversation must not be answered again."""
    _connect(client, tenant=TENANT, shop_id="shop_msg3")
    fake = _wire_fake_assistant(client)
    sent = _wire_fake_shop_client(client, messages=[
        {"id": "m2", "sender": {"role": "SYSTEM"}, "plaintext": "أهلاً! طلبك بالطريق."}])

    body = _message_event_body(shop_id="shop_msg3", conversation_id="conv3",
                               notification_id="n-msg-3")
    r = _post_webhook(client, body)
    assert r.status_code == 200
    assert sent == []
    assert fake.invoke_calls == []


def test_no_messages_at_all_is_a_harmless_noop(client):
    _connect(client, tenant=TENANT, shop_id="shop_msg4")
    fake = _wire_fake_assistant(client)
    sent = _wire_fake_shop_client(client, messages=[])

    body = _message_event_body(shop_id="shop_msg4", conversation_id="conv4",
                               notification_id="n-msg-4")
    r = _post_webhook(client, body)
    assert r.status_code == 200
    assert sent == []
    assert fake.invoke_calls == []


def test_a_blank_plaintext_message_is_not_answered(client):
    _connect(client, tenant=TENANT, shop_id="shop_msg5")
    _wire_fake_assistant(client)
    sent = _wire_fake_shop_client(client, messages=[
        {"id": "m3", "sender": {"role": "BUYER"}, "plaintext": "   "}])

    body = _message_event_body(shop_id="shop_msg5", conversation_id="conv5",
                               notification_id="n-msg-5")
    _post_webhook(client, body)
    assert sent == []


def test_an_unconnected_shop_never_calls_the_assistant_or_fetches_messages(client):
    fake = _wire_fake_assistant(client)
    body = _message_event_body(shop_id="shop_never_connected", conversation_id="conv6",
                               notification_id="n-msg-6")
    r = _post_webhook(client, body)
    assert r.status_code == 200
    assert fake.invoke_calls == []


def test_a_repeated_notification_id_only_replies_once(client):
    _connect(client, tenant=TENANT, shop_id="shop_msg7")
    fake = _wire_fake_assistant(client)
    sent = _wire_fake_shop_client(client, messages=[_buyer_message("مرحبا")])

    body = _message_event_body(shop_id="shop_msg7", conversation_id="conv7",
                               notification_id="n-msg-dup")
    _post_webhook(client, body)
    _post_webhook(client, body)
    assert len(sent) == 1
    assert len(fake.invoke_calls) == 1


def test_a_tool_call_for_order_status_is_answered_from_a_real_fetched_order(client):
    _connect(client, tenant=TENANT, shop_id="shop_msg8")
    _wire_fake_assistant(client, {
        "kind": "tool_call",
        "calls": [{"name": "check_order_status", "arguments": {"order_id": "9001"}}],
    })
    sent = _wire_fake_shop_client(client, messages=[_buyer_message("وين طلب رقم 9001؟")])
    client.app.state.container.tiktok_shop.client.get_order_detail = (
        lambda **kw: {"id": "9001", "status": "AWAITING_SHIPMENT"})

    body = _message_event_body(shop_id="shop_msg8", conversation_id="conv8",
                               notification_id="n-msg-8")
    _post_webhook(client, body)
    assert len(sent) == 1
    assert "AWAITING_SHIPMENT" in sent[0]["text"]


def test_a_tool_call_for_an_order_that_does_not_exist_answers_honestly(client):
    _connect(client, tenant=TENANT, shop_id="shop_msg9")
    _wire_fake_assistant(client, {
        "kind": "tool_call",
        "calls": [{"name": "check_order_status", "arguments": {"order_id": "does-not-exist"}}],
    })
    sent = _wire_fake_shop_client(client, messages=[_buyer_message("طلبي؟")])
    client.app.state.container.tiktok_shop.client.get_order_detail = lambda **kw: None

    body = _message_event_body(shop_id="shop_msg9", conversation_id="conv9",
                               notification_id="n-msg-9")
    _post_webhook(client, body)
    assert len(sent) == 1
    assert "ما لقيت" in sent[0]["text"]


def test_an_unknown_tool_name_is_dropped_never_sent(client):
    """Defence in depth — a tool call the model somehow returned outside the declared set must
    never reach a customer as if it were answered."""
    _connect(client, tenant=TENANT, shop_id="shop_msg10")
    _wire_fake_assistant(client, {
        "kind": "tool_call",
        "calls": [{"name": "delete_everything", "arguments": {}}],
    })
    sent = _wire_fake_shop_client(client, messages=[_buyer_message("مرحبا")])

    body = _message_event_body(shop_id="shop_msg10", conversation_id="conv10",
                               notification_id="n-msg-10")
    _post_webhook(client, body)
    assert sent == []


def test_the_ai_kill_switch_stops_the_reply_but_not_the_webhook_ack(client):
    import asyncio

    from app.core.ai_toggle import AiToggleStore

    _connect(client, tenant=TENANT, shop_id="shop_msg11")
    asyncio.run(AiToggleStore(client.app.state.container.datastore).set(TENANT, False))
    fake = _wire_fake_assistant(client)
    sent = _wire_fake_shop_client(client, messages=[_buyer_message("مرحبا")])

    body = _message_event_body(shop_id="shop_msg11", conversation_id="conv11",
                               notification_id="n-msg-11")
    r = _post_webhook(client, body)
    assert r.status_code == 200
    assert r.json() == {"received": True}
    assert sent == []
    assert fake.invoke_calls == []


def test_assistant_service_unreachable_is_swallowed_not_a_500(client):
    _connect(client, tenant=TENANT, shop_id="shop_msg12")
    _wire_fake_shop_client(client, messages=[_buyer_message("مرحبا")])

    class _BrokenConnections:
        def list(self, tenant):
            raise ConnectionError("boom")

    client.app.state.container.tiktok_assistant_connections = _BrokenConnections()

    body = _message_event_body(shop_id="shop_msg12", conversation_id="conv12",
                               notification_id="n-msg-12")
    r = _post_webhook(client, body)
    assert r.status_code == 200
    assert r.json() == {"received": True}


def test_a_send_message_failure_is_swallowed_not_a_500(client):
    _connect(client, tenant=TENANT, shop_id="shop_msg13")
    _wire_fake_assistant(client)
    _wire_fake_shop_client(client, messages=[_buyer_message("مرحبا")], send_ok=False)

    body = _message_event_body(shop_id="shop_msg13", conversation_id="conv13",
                               notification_id="n-msg-13")
    r = _post_webhook(client, body)
    assert r.status_code == 200


def test_an_order_shaped_payload_never_reaches_the_message_path(client):
    """`order_id`+`order_status` together must always be read as the order path, even if a
    `conversation_id` were somehow also present — the two paths are mutually exclusive by design."""
    _connect(client, tenant=TENANT, shop_id="shop_msg14")
    fake = _wire_fake_assistant(client)
    body = json.dumps({
        "type": 1, "tts_notification_id": "n-msg-14", "shop_id": "shop_msg14",
        "data": {"order_id": "1", "order_status": "UNPAID", "conversation_id": "conv14"},
    }).encode()
    _post_webhook(client, body)
    assert fake.invoke_calls == []


def test_a_missing_conversation_id_in_a_non_order_event_is_a_harmless_noop(client):
    _connect(client, tenant=TENANT, shop_id="shop_msg15")
    fake = _wire_fake_assistant(client)
    body = json.dumps({
        "type": 5, "tts_notification_id": "n-msg-15", "shop_id": "shop_msg15",
        "data": {"something_else": True},
    }).encode()
    r = _post_webhook(client, body)
    assert r.status_code == 200
    assert fake.invoke_calls == []


def test_feature_tiktok_gated_shop_gets_no_automated_reply(client):
    """`refuses_machine_writes` on `container.tiktok_licence` — same gate Phase 1/2's order
    recording already respects, applied here too: owning the connection is not owning the app."""
    _connect(client, tenant=TENANT, shop_id="shop_msg16")

    class _RefusingLicence:
        async def allowed(self, tenant):
            return False

    client.app.state.container.tiktok_licence = _RefusingLicence()
    fake = _wire_fake_assistant(client)
    sent = _wire_fake_shop_client(client, messages=[_buyer_message("مرحبا")])

    body = _message_event_body(shop_id="shop_msg16", conversation_id="conv16",
                               notification_id="n-msg-16")
    r = _post_webhook(client, body)
    assert r.status_code == 200
    assert sent == []
    assert fake.invoke_calls == []
