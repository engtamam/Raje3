"""Integration: /internal/carousel-shown — the door a campaign's own carousel walks through so
its card's button tap resolves exactly like a card the assistant itself had shown. See
app/core/conversation.py::ConversationEngine.register_carousel_shown and app/api/internal.py."""
import asyncio

from tests.conftest import INTERNAL_TOKEN

TENANT = "carshown_shop"
SUBJECT = "carshown_sub_1"


def _headers():
    return {"X-Internal-Token": INTERNAL_TOKEN}


def test_registers_the_ids_on_a_brand_new_conversation_row(client):
    resp = client.post("/internal/carousel-shown",
                       json={"tenant": TENANT, "subject_ref": SUBJECT,
                            "item_ids": ["svc_1", "svc_2"], "branch_id": "br_1"},
                       headers=_headers())
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"ok": True}

    app = client.app
    c = app.state.container

    async def _check():
        from app.core.models import CONVERSATIONS

        row = await c.datastore.get(CONVERSATIONS, f"{TENANT}|{SUBJECT}")
        assert row is not None
        assert set(row["shown_carousel_ids"]) == {"svc_1", "svc_2"}
        assert row["branch_id"] == "br_1"

    asyncio.run(_check())


def test_merges_onto_an_existing_conversations_own_list_without_dropping_it(client):
    app = client.app
    c = app.state.container

    async def _seed():
        from app.core.models import CONVERSATIONS

        await c.datastore.put(CONVERSATIONS, f"{TENANT}|sub_merge", {
            "tenant": TENANT, "subject_ref": "sub_merge", "state": "idle",
            "shown_carousel_ids": ["model_shown"], "branch_id": "br_from_chat"})

    asyncio.run(_seed())

    resp = client.post("/internal/carousel-shown",
                       json={"tenant": TENANT, "subject_ref": "sub_merge",
                            "item_ids": ["campaign_shown"], "branch_id": "br_campaign"},
                       headers=_headers())
    assert resp.status_code == 200

    async def _check():
        from app.core.models import CONVERSATIONS

        row = await c.datastore.get(CONVERSATIONS, f"{TENANT}|sub_merge")
        assert set(row["shown_carousel_ids"]) == {"model_shown", "campaign_shown"}
        # THE EXISTING BRANCH SURVIVES — never overwritten by a campaign that fires after a real
        # chat already fixed it.
        assert row["branch_id"] == "br_from_chat"

    asyncio.run(_check())


def test_refuses_without_the_internal_token(client):
    resp = client.post("/internal/carousel-shown",
                       json={"tenant": TENANT, "subject_ref": SUBJECT, "item_ids": ["svc_1"]})
    assert resp.status_code in (401, 403)


def test_refuses_an_empty_item_ids_list(client):
    resp = client.post("/internal/carousel-shown",
                       json={"tenant": TENANT, "subject_ref": SUBJECT, "item_ids": []},
                       headers=_headers())
    assert resp.status_code == 422
