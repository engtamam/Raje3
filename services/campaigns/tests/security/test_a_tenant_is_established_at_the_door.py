"""A token with no tenant may not write a row that belongs to nobody (ج2-19).

`Principal.tenant` is None whenever the bearer token carries no tenant claim, and
`require_capability` has never looked at it — it checks capabilities and nothing else. So a
platform-level token holding `campaigns.manage` reaches this door with no establishment behind it.

READS ARE NOT THE EXPOSURE, and that was measured rather than assumed: the memory store returns
nothing for `{"tenant": None}`, and postgres turns it into `value @> '{"tenant": null}'`, which
matches only rows whose tenant is literally null. Both fail closed.

THE WRITE IS. `f"{principal.tenant}|{campaign_id}"` becomes the literal string «None|c1», and the
stored row's `tenant` becomes null. That row is real and belongs to nobody: no owner's screen ever
lists it, no export carries it, and no erasure reaches it, because an erasure fans out per tenant.
Nothing fails anywhere along the way — which is exactly why it needs a test that names it.
"""
from __future__ import annotations

import datetime as dt

import jwt

from tests.integration.test_licence_route import AUD, ISS, SECRET, _rows, client  # noqa: F401


def _no_tenant(caps: list[str]) -> dict:
    """A real, VALID token that simply carries no tenant claim — a platform token's shape."""
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "u1", "iss": ISS, "aud": AUD, "caps": caps,
                      "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


def test_a_token_with_no_tenant_writes_no_campaign(client):
    """THE WHOLE PROPERTY: refused at the door, and NOTHING stored.

    Asserted on the store rather than on the status code, because the status is the part that can
    be right by accident — this route already refuses for a missing template and for a licence,
    and either would make a status assertion pass while a row sat in the datastore. What must be
    true is that no row exists with no owner.
    """
    before = dict(_rows(client))
    r = client.post("/api/v1/campaigns",
                    json={"goal": "announce", "owner_text": "افتتحنا فرعاً"},
                    headers=_no_tenant(["campaigns.manage"]))

    assert r.status_code >= 400, "a request with no establishment behind it must not succeed"
    after = _rows(client)
    assert after == before, "a row was stored for a caller with no establishment"
    for key, row in after.items():
        assert "None" not in key, f"a row keyed under the literal string «None»: {key}"
        assert row.get("tenant"), f"a stored row with no tenant: {key}"


def test_the_refusal_names_the_tenant_rather_than_something_else(client):
    """AND IT IS REFUSED FOR THE RIGHT REASON.

    Without this half the test above passes on any refusal at all — the missing template, the
    licence, a rate limit — and would go on passing the day the guard is removed. 403 is the
    guard's own answer, and it is the one this route gives to nobody else.
    """
    r = client.post("/api/v1/campaigns",
                    json={"goal": "announce", "owner_text": "افتتحنا فرعاً"},
                    headers=_no_tenant(["campaigns.manage"]))
    assert r.status_code == 403, r.text
