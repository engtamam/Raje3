"""`GET /internal/operations/whatsapp-auto-register` — whatsapp-assistant's own read, before it
ever registers a stranger's number as a real جهات الاتصال row. See core/whatsapp_auto_register.py's
own docstring for why this defaults off.
"""
from __future__ import annotations

INTERNAL = {"X-Internal-Token": "t" * 40}
PATH = "/internal/operations/whatsapp-auto-register"


def test_a_tenant_that_never_opted_in_reads_false(client):
    r = client.get(PATH, params={"tenant": "tnt_war_read_1"}, headers=INTERNAL)
    assert r.status_code == 200, r.text
    assert r.json() == {"tenant": "tnt_war_read_1", "enabled": False}


def test_a_tenant_that_opted_in_reads_true(client):
    import asyncio
    from app.core.whatsapp_auto_register import WhatsAppAutoRegisterFlagStore

    c = client.app.state.container
    asyncio.run(WhatsAppAutoRegisterFlagStore(c.datastore).set("tnt_war_read_2", True))
    r = client.get(PATH, params={"tenant": "tnt_war_read_2"}, headers=INTERNAL)
    assert r.status_code == 200, r.text
    assert r.json() == {"tenant": "tnt_war_read_2", "enabled": True}


def test_no_token_is_refused(client):
    r = client.get(PATH, params={"tenant": "tnt_war_read_3"})
    assert r.status_code == 401
