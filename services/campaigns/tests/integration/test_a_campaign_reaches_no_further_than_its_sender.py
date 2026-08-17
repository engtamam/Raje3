"""A campaign may not reach further than the person who pressed «أطلق».

WHAT WAS TRUE BEFORE THIS FILE. `branch_id` came off the request body and went straight to the
audience resolver and onto the stored campaign the dispatcher re-reads at fire time. Nothing asked
who was pressing. An employee narrowed to one branch could leave the field empty — which means
«the whole establishment» — and reach every customer the shop has, out of the owner's message
quota and under the owner's name.

THIS CROSSES THE CHAIN, not the helper: a real token, the real route, and the row that comes back
out of the list. Deleting the narrowing in `_aim` — or writing `body.branch_id` onto the campaign
instead of the narrowed value — fails a named test here.
"""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

SECRET = "h" * 40
ISS = "iss"
AUD = "aud"
CAPS = ["campaigns.read", "campaigns.manage"]


class _Scope:
    """Stands in for `operations`. `answer` is whatever that service would have replied."""

    def __init__(self) -> None:
        self.answer = ""

    async def scope(self, tenant: str, subject: str):
        return self.answer


@pytest.fixture(scope="module")
def app_and_scope():
    from app.config import get_settings

    saved = dict(os.environ)
    os.environ.update({
        "ENV": "test",
        "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": SECRET,
        "TOKEN_ISSUER": ISS,
        "TOKEN_AUDIENCE": AUD,
        "RATELIMIT_MAX": "1000",
    })
    get_settings.cache_clear()
    from app.main import create_app

    app = create_app()
    from app.adapters.peers import NullTemplates
    app.state.container.templates = NullTemplates([
        {"type": "mkt_announcement", "name": "mkt_announcement", "fills": ["owner"],
         "body": "{{1}} — {{2}}"},
    ])
    scope = _Scope()
    app.state.container.branch_scope = scope
    yield TestClient(app, raise_server_exceptions=False), scope
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


def _auth(subject: str):
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": subject, "iss": ISS, "aud": AUD, "tenant": "tnt_aim",
                      "caps": CAPS, "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


def _launch(client, subject: str, branch_id: str, text: str):
    return client.post("/api/v1/campaigns",
                       json={"goal": "announce", "owner_text": text, "branch_id": branch_id},
                       headers=_auth(subject))


def _stored(client, subject: str, campaign_id: str) -> dict:
    listed = client.get("/api/v1/campaigns", headers=_auth(subject))
    assert listed.status_code == 200, listed.text
    return next(c for c in listed.json()["campaigns"] if c["id"] == campaign_id)


def test_an_empty_branch_from_a_narrowed_man_is_his_branch_not_the_whole_shop(app_and_scope):
    """THE DEFECT ITSELF. He sends nothing, which used to mean «everybody»."""
    client, scope = app_and_scope
    scope.answer = "brn-jed"

    r = _launch(client, "u_jed", "", "عرض هذا الأسبوع")
    assert r.status_code in (200, 201), r.text
    cid = (r.json().get("campaign") or r.json())["id"]

    assert _stored(client, "u_jed", cid)["branch_id"] == "brn-jed"


def test_a_branch_that_is_not_his_is_refused_rather_than_quietly_swapped(app_and_scope):
    """On a read, substituting his own scope is kind. On a send it would put his text in front of
    a different branch's customers than the count he was shown."""
    client, scope = app_and_scope
    scope.answer = "brn-jed"

    r = _launch(client, "u_jed", "brn-ryd", "عرض الرياض")
    assert r.status_code == 403, r.text
    assert r.json()["error"] == "BRANCH_REFUSED"


def test_a_supervisor_over_several_must_name_which_one(app_and_scope):
    """A set is not a branch, and the audience takes one. Asked, never guessed."""
    client, scope = app_and_scope
    scope.answer = frozenset({"brn-jed", "brn-ryd"})

    empty = _launch(client, "u_sup", "", "عرض عام")
    assert empty.status_code == 400, empty.text
    assert empty.json()["error"] == "BRANCH_REFUSED"

    named = _launch(client, "u_sup", "brn-ryd", "عرض الرياض")
    assert named.status_code in (200, 201), named.text
    cid = (named.json().get("campaign") or named.json())["id"]
    assert _stored(client, "u_sup", cid)["branch_id"] == "brn-ryd"

    outside = _launch(client, "u_sup", "brn-dmm", "عرض الدمام")
    assert outside.status_code == 403, outside.text


def test_a_man_his_shop_stopped_launches_nothing(app_and_scope):
    """REVOKED is not «no narrowing». Dismissal must not widen him — the و-1 defect, in the one
    path that spends money."""
    client, scope = app_and_scope
    from app.adapters.branch_scope import REVOKED

    scope.answer = REVOKED
    r = _launch(client, "u_gone", "brn-jed", "عرض من مطرود")
    assert r.status_code == 503, r.text
    assert r.json()["error"] == "BRANCH_REFUSED"


def test_an_unreadable_scope_refuses_instead_of_guessing_at_the_reach(app_and_scope):
    """Fails closed. We cannot ask, so we do not send: a campaign guessed at is a campaign paid
    for, and its reach cannot be taken back once the messages leave."""
    client, scope = app_and_scope
    from app.adapters.branch_scope import UNREADABLE

    scope.answer = UNREADABLE
    r = _launch(client, "u_any", "", "عرض")
    assert r.status_code == 503, r.text


def test_the_owner_is_not_narrowed_and_still_reaches_the_whole_establishment(app_and_scope):
    """The common case, and the one that must not regress: no operator row means no narrowing."""
    client, scope = app_and_scope
    scope.answer = ""

    r = _launch(client, "u_owner", "", "افتتحنا فرعاً جديداً")
    assert r.status_code in (200, 201), r.text
    cid = (r.json().get("campaign") or r.json())["id"]
    assert _stored(client, "u_owner", cid)["branch_id"] == ""


def test_the_preview_is_computed_under_the_reach_the_send_will_have(app_and_scope):
    """A preview run under wider rules than the send is a count he is shown and never receives."""
    client, scope = app_and_scope
    scope.answer = frozenset({"brn-jed", "brn-ryd"})

    r = client.post("/api/v1/campaigns/preview",
                    json={"goal": "announce", "owner_text": "عرض", "branch_id": "brn-dmm"},
                    headers=_auth("u_sup"))
    assert r.status_code == 403, r.text
    assert r.json()["error"] == "BRANCH_REFUSED"
