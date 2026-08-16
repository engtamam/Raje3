"""و-8 and its two twins: a LIST of people handed across every branch.

`Customer.public()` carries the name, the phone and `last_branch_id`; `Operator.public()` carries
the name, the role and the branch. Three routes returned those lists whole:

  · the strip along the top of the field screen — fixed when و-8 was written;
  · `customers/resolve`, the join behind «من تأخّر» — the same leak, two hundred at a time, and
    nobody looked at it because the finding named the strip;
  · `GET /operators` — «فريقي» handing a branch manager the whole chain's roster, which no
    finding named at all. The gate found it.

A TARGETED LOOKUP IS DELIBERATELY NOT A BROWSE and stays open: `by-phone` and the customer record
are one person the operator already has in front of him, and a customer is shared across the chain
(§12.4) — one person, one balance. What narrows is the browse and the history.
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
TENANT = "tnt_browse"


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
                      "caps": ["operations.read", "operations.manage"],
                      "tenant": TENANT, "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


def _shop(client):
    """Two branches, a manager tied to one of them, and a customer served by each."""
    from app.core.models import Customer, Operator
    from app.core.stores import CustomerStore, OperatorStore

    store = client.app.state.container.datastore
    asyncio.run(OperatorStore(store).save(Operator(
        id="opr_jed", tenant=TENANT, name="مدير جدة", role="manager",
        branch_id="brn-jeddah", person_id="u_jeddah")))
    asyncio.run(OperatorStore(store).save(Operator(
        id="opr_ryd", tenant=TENANT, name="موظف الرياض", role="staff",
        branch_id="brn-riyadh", person_id="u_riyadh")))

    refs = {}
    for name, phone, branch in (("عميل جدة", "966500000001", "brn-jeddah"),
                                ("عميل الرياض", "966500000002", "brn-riyadh")):
        ref = f"sub_{branch}_{'a' * 20}"
        asyncio.run(CustomerStore(store).save(Customer(
            id=f"cus_{branch}", tenant=TENANT, phone=phone, name=name,
            subject_ref=ref, last_branch_id=branch)))
        refs[branch] = ref
    return refs


def _resolve(client, refs, subject):
    r = client.post("/api/v1/field/customers/resolve", json={"refs": list(refs.values())},
                    headers=_headers(subject))
    assert r.status_code == 200, r.text
    return r.json()["customers"]


def test_the_overdue_join_does_not_hand_a_manager_another_branchs_customers(client):
    """THE TWIN NOBODY LOOKED AT. It answers «من تأخّر» — a browse, by name and phone."""
    refs = _shop(client)

    got = _resolve(client, refs, "u_jeddah")

    names = {c["name"] for c in got}
    assert "عميل جدة" in names
    assert "عميل الرياض" not in names, (
        "a manager scoped to Jeddah read Riyadh's customers by name and number")


def test_the_owner_still_sees_the_whole_chain(client):
    """A guard that narrows everybody is an outage: the owner has no branch and owns them all."""
    refs = _shop(client)

    got = _resolve(client, refs, "u_owner_with_no_operator_row")

    assert {c["name"] for c in got} == {"عميل جدة", "عميل الرياض"}


def test_the_team_screen_shows_his_branchs_team_not_the_chains(client):
    """FOUND BY THE GATE, NAMED BY NO FINDING. `Operator.public()` carries the name, the role and
    the branch, and «فريقي» handed the whole roster to whoever could read."""
    _shop(client)

    got = client.get("/api/v1/staff/operators", headers=_headers("u_jeddah")).json()["operators"]

    names = {o["name"] for o in got}
    assert "مدير جدة" in names
    assert "موظف الرياض" not in names


def test_an_unbranched_colleague_stays_visible_to_everybody(client):
    """A shop in the default central mode gives nobody a branch. Hiding those would leave a
    manager looking at a team that appears to be empty."""
    from app.core.models import Operator
    from app.core.stores import OperatorStore

    _shop(client)
    asyncio.run(OperatorStore(client.app.state.container.datastore).save(Operator(
        id="opr_any", tenant=TENANT, name="بلا فرع", role="staff")))

    got = client.get("/api/v1/staff/operators", headers=_headers("u_jeddah")).json()["operators"]

    assert "بلا فرع" in {o["name"] for o in got}
