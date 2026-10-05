"""ط-3: four typed digits must not hand a branch manager the whole chain.

THE LEAK WAS NOT IN THIS SERVICE, WHICH IS WHY IT SURVIVED و-8. The keypad called search-service
directly — `/suggest` for the terms, `POST /search` for the people — and neither route has ever
known what a branch is. Every narrowing in `field.py` was intact and irrelevant: the browser was
not asking operations at all. So the fix is a route HERE, and this test is what says the route
narrows rather than merely existing.

AND THE FAILURE ANSWER IS PART OF THE CONTRACT. `ok: false` is «we could not ask»; an empty list
with `ok: true` is «nobody matched». Telling a man standing at the counter that he is not
registered, when the index was merely unreachable, is the one wrong answer this screen must never
give — so the two are tested apart.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

SECRET = "h" * 40
ISS, AUD = "iss", "aud"
TENANT = "tnt_keypad"


class _Search:
    """A search-service that answers, standing in for the peer.

    The shape is the peer's own, measured on the cluster and recorded in adapters/search: `suggest`
    returns TERMS (strings), `query` returns hits carrying `fields`.
    """
    driver = "stub"

    def __init__(self, hits, terms=("0500",)):
        self.hits, self.terms = hits, list(terms)

    async def index(self, **kw):
        return True

    async def suggest(self, **kw):
        return list(self.terms)

    async def query(self, **kw):
        return list(self.hits)


class _Unreachable(_Search):
    async def suggest(self, **kw):
        return None

    async def query(self, **kw):
        return None


@pytest.fixture()
def client():
    from app.config import get_settings

    saved = dict(os.environ)
    os.environ.update({
        "ENV": "test", "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256", "TOKEN_HS256_SECRET": SECRET,
        "TOKEN_ISSUER": ISS, "TOKEN_AUDIENCE": AUD, "RATELIMIT_MAX": "1000",
        "PII_SALT": "s" * 32, "SECRETS_KEK": "unit-test-kek-not-a-real-key",
    })
    get_settings.cache_clear()
    from app.main import create_app

    yield TestClient(create_app(), raise_server_exceptions=False)
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


def _headers(subject: str) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": subject, "iss": ISS, "aud": AUD,
                      "caps": ["operations.read", "operations.record"],
                      "tenant": TENANT, "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


def _shop(client, search):
    from app.core.models import Operator
    from app.core.stores import OperatorStore

    store = client.app.state.container.datastore
    asyncio.run(OperatorStore(store).save(Operator(
        id="opr_jed", tenant=TENANT, name="مدير جدة", role="manager",
        branch_id="brn-jeddah", person_id="u_jeddah")))
    client.app.state.container.search = search


HITS = [
    {"id": "cus_j", "fields": {"phone": "966500000001", "name": "عميل جدة",
                               "branch_id": "brn-jeddah"}},
    {"id": "cus_r", "fields": {"phone": "966500000002", "name": "عميل الرياض",
                               "branch_id": "brn-riyadh"}},
    # A customer the till recorded, which sends no branch. Empty means «visible to everybody» —
    # the same rule as everywhere else, and getting it wrong hides every customer from before the
    # day the field was added, which is the leak inverted.
    {"id": "cus_t", "fields": {"phone": "966500000003", "name": "عميل الصندوق",
                               "branch_id": ""}},
]


def _suggest(client, subject, prefix="0500"):
    r = client.get(f"/api/v1/field/customers/suggest?prefix={prefix}", headers=_headers(subject))
    assert r.status_code == 200, r.text
    return r.json()


def test_a_branch_manager_does_not_see_another_branchs_customers(client):
    _shop(client, _Search(HITS))

    out = _suggest(client, "u_jeddah")

    names = {c["name"] for c in out["customers"]}
    assert "عميل جدة" in names
    assert "عميل الرياض" not in names, (
        "four typed digits handed a manager scoped to Jeddah a Riyadh customer by name and number")


def test_the_unbranched_customer_stays_visible(client):
    """A till records no branch, and empty has always meant «everybody», not «nobody»."""
    _shop(client, _Search(HITS))

    out = _suggest(client, "u_jeddah")

    assert "عميل الصندوق" in {c["name"] for c in out["customers"]}


def test_the_owner_still_sees_the_whole_chain(client):
    """A guard that narrows everybody is an outage."""
    _shop(client, _Search(HITS))

    out = _suggest(client, "u_owner_with_no_operator_row")

    assert {c["name"] for c in out["customers"]} == {"عميل جدة", "عميل الرياض", "عميل الصندوق"}


def test_the_branch_is_not_handed_back(client):
    """The scope field is what a scoped reader must not be able to enumerate."""
    _shop(client, _Search(HITS))

    out = _suggest(client, "u_jeddah")

    assert all("branch_id" not in c for c in out["customers"])


def test_an_unreachable_index_is_not_an_empty_shop(client):
    _shop(client, _Unreachable([]))

    out = _suggest(client, "u_jeddah")

    assert out["ok"] is False
    assert out["customers"] == []


def test_the_typed_number_survives_a_page_of_near_neighbours(client):
    """The query carries eight words. With the peer's fuzzy suggestions first, a whole number whose
    eight near neighbours exist (one digit away) was cut off the query entirely — the customer at
    the counter could not be found by his own number. What was typed must always be asked."""
    seen: list[str] = []

    class _Recording(_Search):
        async def query(self, **kw):
            seen.append(kw["text"])
            return list(self.hits)

    neighbours = [f"057000100{d}" for d in range(10) if d != 1]   # nine near misses, not the number
    _shop(client, _Recording(HITS, terms=neighbours))

    _suggest(client, "u_owner_with_no_operator_row", prefix="0570001001")

    assert "0570001001" in seen[-1].split(), f"the typed number was dropped from the query: {seen[-1]}"


def test_nobody_matched_is_not_an_outage(client):
    _shop(client, _Search([], terms=[]))

    out = _suggest(client, "u_jeddah")

    assert out["ok"] is True
    assert out["customers"] == []
