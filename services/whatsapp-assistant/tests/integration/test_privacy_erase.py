"""Integration: /internal/privacy/erase — DSAR erasure, immediate and independent of the 30-day
retention tick. See app/core/erasure.py and app/api/internal.py."""
from tests.conftest import INTERNAL_TOKEN

TENANT = "erase_shop"
SUBJECT = "erase_sub_1"


def _headers():
    return {"X-Internal-Token": INTERNAL_TOKEN}


def _seed_container(client):
    """Reach into the real app container (memory datastore, the actual app instance the
    TestClient drives) and write rows directly — the same shape the conversation engine and
    inbound store would produce, without needing a full LLM round trip."""
    import time

    app = client.app
    c = app.state.container
    import asyncio

    async def _seed():
        from app.adapters.inbound_store.datastore_backed import DataStoreInboundMessageStore
        from app.core.models import CONVERSATIONS

        ims = DataStoreInboundMessageStore(c.datastore)
        await ims.record_if_new(TENANT, "erase_wamid_1", {"text": "hello", "from": "+9665"})
        await ims.attach_subject_ref(TENANT, "erase_wamid_1", SUBJECT)
        await c.datastore.put(CONVERSATIONS, f"{TENANT}|{SUBJECT}", {
            "tenant": TENANT, "subject_ref": SUBJECT, "state": "idle",
            "session_closed_at": int(time.time()), "raw_window": [], "summary": "secret chat"})

    asyncio.run(_seed())


def test_erase_removes_inbound_messages_and_conversation_row_immediately(client):
    _seed_container(client)

    resp = client.post("/internal/privacy/erase", json={"tenant": TENANT, "subject": SUBJECT},
                       headers=_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["service"] == "whatsapp-assistant"
    assert body["subject_ref"] == SUBJECT
    assert any(e.startswith("inbound_messages:") for e in body["erased"])
    assert any(e.startswith("wa_conversations:") for e in body["erased"])

    app = client.app
    c = app.state.container
    import asyncio

    async def _check():
        from app.adapters.inbound_store.datastore_backed import DataStoreInboundMessageStore
        from app.core.models import CONVERSATIONS

        ims = DataStoreInboundMessageStore(c.datastore)
        assert await ims.get(TENANT, "erase_wamid_1") is None
        assert await c.datastore.get(CONVERSATIONS, f"{TENANT}|{SUBJECT}") is None

    asyncio.run(_check())


def test_erase_is_idempotent_on_an_already_erased_subject(client):
    resp = client.post("/internal/privacy/erase",
                       json={"tenant": TENANT, "subject": "never_existed"},
                       headers=_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["already_absent"] is True
    assert body["erased"] == []


def test_erase_requires_internal_token(client):
    resp = client.post("/internal/privacy/erase", json={"tenant": TENANT, "subject": SUBJECT})
    assert resp.status_code == 401
