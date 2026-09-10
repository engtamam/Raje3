"""`GET /internal/operations/operator-by-person` — whatsapp-assistant's own WhatsApp-sender-to-
operator resolution, second half (the first half is identity-service's own `GET /internal/
tenancy/members`, matching the sender's phone against a tenant's `identifier` list)."""
from __future__ import annotations

import asyncio

INTERNAL = {"X-Internal-Token": "t" * 40}
PATH = "/internal/operations/operator-by-person"
TENANT = "tnt_op_by_person"


def _seed(client):
    from app.core.models import Operator
    from app.core.stores import OperatorStore

    op = Operator(id="op_bp1", tenant=TENANT, name="سارة", role="operator",
                 person_id="prs_abc123", active=True, created=1786860000)
    asyncio.run(OperatorStore(client.app.state.container.datastore).save(op))
    return op.id


def test_a_known_person_id_resolves_the_operator(client):
    op_id = _seed(client)
    r = client.get(PATH, params={"tenant": TENANT, "person_id": "prs_abc123"}, headers=INTERNAL)
    assert r.status_code == 200, r.text
    assert r.json() == {"operator_id": op_id, "name": "سارة"}


def test_an_unknown_person_id_is_404_not_500(client):
    _seed(client)
    r = client.get(PATH, params={"tenant": TENANT, "person_id": "prs_nobody"}, headers=INTERNAL)
    assert r.status_code == 404


def test_an_unknown_tenant_is_also_404_never_confirming_which_check_failed(client):
    _seed(client)
    r = client.get(PATH, params={"tenant": "tnt_nope", "person_id": "prs_abc123"},
                   headers=INTERNAL)
    assert r.status_code == 404


def test_no_token_is_refused(client):
    r = client.get(PATH, params={"tenant": TENANT, "person_id": "prs_abc123"})
    assert r.status_code == 401
