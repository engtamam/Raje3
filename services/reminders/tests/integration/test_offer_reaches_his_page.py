"""أ-4 · the coupon and the service names that never left this service.

THE CHAIN. `tick.py` derives a coupon code and writes it on the send log — «the till looks the
offer up by what the customer says, and «عرض وصلني» is not a handle». The customer's page reads
`code` and renders it in large type, `dir=ltr`, «big enough to read from a phone held at arm's
length across a counter». Between the two, `/internal/portal/offers` — the ONLY route that carries
offers to that page — did not emit the field. So the page opened FROM the message that carried the
offer was the one place its code could not be found.

AND THE SCOPE ARRIVED AS IDENTIFIERS. The route emitted `offer_services`, which are ours, and the
page printed them: «على: svc_9f2a…». The names were held at send time — the caller owns the
catalogue and sends the words — used to render the message, and dropped.

Every link was correct alone. Nothing logged, nothing failed, and the defect is only visible from
end to end, which is why this test starts at the store and finishes at the response body.
"""
from __future__ import annotations

import asyncio
import os
import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(monkeypatch):
    from app.config import get_settings

    saved = dict(os.environ)
    os.environ.update({"ENV": "test", "INTERNAL_SERVICE_TOKEN": "t" * 40,
                       "RATELIMIT_MAX": "1000", "PII_SALT": "s" * 32})
    get_settings.cache_clear()
    from app.main import create_app

    # OPERATIONS IS WHO KNOWS WHAT WAS SPENT, and when it cannot be asked this route answers with
    # no offers at all — deliberately, since showing a possibly-spent one sends a customer in
    # expecting something he used last week. Here it is reachable and nothing is spent.
    import app.api.internal as internal

    async def _nothing_spent(tenant, subject_ref):
        return set()

    monkeypatch.setattr(internal, "_spent_or_empty", _nothing_spent)

    yield TestClient(create_app(), raise_server_exceptions=False)
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


def _internal() -> dict:
    return {"X-Internal-Token": "t" * 40}


def _offer(client, tenant: str, *, names: list[str], ids: list[str], code: str) -> None:
    """A send log row exactly as `tick.py` writes one after a message goes out."""
    from app.core.models import SendLog, as_row
    from app.core.stores import SendLogStore

    row = SendLog(tenant=tenant, subject_ref="sub_" + "a" * 24, cls="offer",
                  at=int(time.time()), schedule_id="sch_1", template_name="mkt_offer",
                  outcome="sent", idempotency_key="idem_1",
                  offer_text="خصم 20% على الغسيل الخارجي",
                  offer_expires_at=int(time.time()) + 3 * 86_400,
                  offer_services=ids, offer_service_names=names, offer_code=code)
    asyncio.run(SendLogStore(client.app.state.container.datastore).append(tenant, as_row(row)))


def _offers(client, tenant: str) -> list[dict]:
    r = client.get("/internal/portal/offers",
                   params={"tenant": tenant, "subject_ref": "sub_" + "a" * 24},
                   headers=_internal())
    assert r.status_code == 200, r.text
    return r.json()["offers"]


def test_the_code_he_must_read_out_reaches_his_page(client):
    _offer(client, "t_code", names=["غسيل خارجي"], ids=["svc_9f2a"], code="RJ-7K2M")

    got = _offers(client, "t_code")

    assert got, "the row is live and unspent — it must be on his page at all"
    assert got[0]["code"] == "RJ-7K2M", (
        "the page renders this in large type and the till has no other handle on the offer")


def test_the_scope_arrives_in_words_and_not_as_our_keys(client):
    _offer(client, "t_names", names=["غسيل خارجي", "تلميع"], ids=["svc_9f2a", "svc_1b3c"],
           code="RJ-1A1A")

    got = _offers(client, "t_names")

    assert got[0]["services"] == ["غسيل خارجي", "تلميع"]
    assert all(not s.startswith("svc_") for s in got[0]["services"]), (
        "«على: svc_9f2a…» is our primary key on a customer's page")
    assert got[0]["scoped"] is True


def test_an_offer_with_no_scope_says_so_separately_from_one_we_cannot_name(client):
    """THE THIRD STATE. Empty names used to mean «the whole shop» — so an offer limited to one
    service became a promise covering everything the moment the words were missing, and he found
    that out at the counter in front of somebody who had to refuse him."""
    _offer(client, "t_all", names=[], ids=[], code="RJ-2B2B")
    assert _offers(client, "t_all")[0]["scoped"] is False

    _offer(client, "t_old", names=[], ids=["svc_9f2a"], code="RJ-3C3C")
    assert _offers(client, "t_old")[0]["scoped"] is True, (
        "limited, and we cannot say to what — which is neither «the whole shop» nor a gap")
