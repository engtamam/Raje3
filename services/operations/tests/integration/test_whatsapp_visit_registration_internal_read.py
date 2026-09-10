"""`GET /internal/operations/whatsapp-visit-registration` — whatsapp-assistant's own read, before
it ever opens the visit-registration Flow for an identified staff sender. See
core/whatsapp_visit_flag.py's own docstring for why this defaults off.
"""
from __future__ import annotations

INTERNAL = {"X-Internal-Token": "t" * 40}
PATH = "/internal/operations/whatsapp-visit-registration"


def test_a_tenant_that_never_opted_in_reads_false(client):
    r = client.get(PATH, params={"tenant": "tnt_wvf_read_1"}, headers=INTERNAL)
    assert r.status_code == 200, r.text
    assert r.json() == {"tenant": "tnt_wvf_read_1", "enabled": False}


def test_a_tenant_that_opted_in_reads_true(client):
    import asyncio
    from app.core.whatsapp_visit_flag import WhatsAppVisitFlagStore

    c = client.app.state.container
    asyncio.run(WhatsAppVisitFlagStore(c.datastore).set("tnt_wvf_read_2", True))
    r = client.get(PATH, params={"tenant": "tnt_wvf_read_2"}, headers=INTERNAL)
    assert r.status_code == 200, r.text
    assert r.json() == {"tenant": "tnt_wvf_read_2", "enabled": True}


def test_no_token_is_refused(client):
    r = client.get(PATH, params={"tenant": "tnt_wvf_read_3"})
    assert r.status_code == 401
