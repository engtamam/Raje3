"""#327 · the shop's name — one name, and the owner can change it.

It is captured once at signup and was permanent: a browser autofilling a password into that box
left an owner reading garbage at the top of his own account screen for good, while a second name
lived in `branding` because the registry would neither expose the real one to peers nor let anybody
change it. The registry does both now, so this route is the single place a name is written.

THE TENANT COMES FROM THE TOKEN, NEVER THE BODY — a caller who can name the tenant can name
somebody else's, and this route reaches an internal door that trusts whatever we hand it.
"""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

PATH = "/api/v1/staff/shop-name"
SECRET = "h" * 40
ISS, AUD = "iss", "aud"


@pytest.fixture()
def client():
    from app.config import get_settings

    saved = dict(os.environ)
    os.environ.update({
        "ENV": "test", "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256", "TOKEN_HS256_SECRET": SECRET,
        "TOKEN_ISSUER": ISS, "TOKEN_AUDIENCE": AUD, "RATELIMIT_MAX": "1000",
        "TENANT_SERVICE_URL": "http://tenant-service:8000",
    })
    get_settings.cache_clear()
    from app.main import create_app

    yield TestClient(create_app(), raise_server_exceptions=False)
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


def _headers(tenant="tnt_name") -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "u_owner", "iss": ISS, "aud": AUD,
                      "caps": ["operations.manage", "operations.read"], "tenant": tenant,
                      "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


class _Registry:
    """The registry's internal door, recorded rather than reached."""

    def __init__(self, code: int = 200) -> None:
        self.code = code
        self.calls: list[tuple] = []

    def call(self, url, *, method, body=None, internal=False):
        self.calls.append((url, method, body, internal))
        if self.code >= 400:
            return self.code, {"detail": "INVALID_NAME"}
        return 200, {"id": "tnt_name", "name": (body or {}).get("name", "")}


def _patch(monkeypatch, registry):
    from app.core import signup as signup_module
    monkeypatch.setattr(signup_module, "Http", lambda **kw: registry)


def test_the_owner_renames_his_shop(client, monkeypatch):
    registry = _Registry()
    _patch(monkeypatch, registry)

    r = client.put(PATH, json={"name": "محل البنشري"}, headers=_headers())

    assert r.status_code == 200, r.text
    assert r.json()["name"] == "محل البنشري"
    url, method, body, internal = registry.calls[0]
    assert method == "PATCH" and internal is True
    assert body == {"name": "محل البنشري"}


def test_the_tenant_comes_from_the_token_and_not_from_anywhere_else(client, monkeypatch):
    """The registry's door trusts the id in the path. Whoever chooses that id chooses whose shop
    gets renamed, so it may only ever come from the verified token."""
    registry = _Registry()
    _patch(monkeypatch, registry)

    client.put(PATH, json={"name": "x", "tenant": "someone_else"}, headers=_headers("tnt_mine"))

    url = registry.calls[0][0]
    assert url.endswith("/internal/tenants/tnt_mine")
    assert "someone_else" not in url


def test_a_refusal_from_the_registry_is_not_rendered_as_success(client, monkeypatch):
    """He would retype his name, read «تم», and find the old one still there on the next screen."""
    _patch(monkeypatch, _Registry(code=400))

    r = client.put(PATH, json={"name": "  "}, headers=_headers())

    assert r.status_code == 400
    assert r.json()["error"] == "RENAME_REFUSED"


def test_with_no_registry_configured_it_says_so_rather_than_pretending():
    """He would retype his name, read «تم», and find the old one still there on the next screen.

    ITS OWN APP, because the URL is read when the container is built: an env var cleared after
    startup would leave the running service still holding the old one, and the test would pass for
    a reason that has nothing to do with the code.
    """
    from app.config import get_settings

    saved = dict(os.environ)
    os.environ.update({
        "ENV": "test", "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256", "TOKEN_HS256_SECRET": SECRET,
        "TOKEN_ISSUER": ISS, "TOKEN_AUDIENCE": AUD, "RATELIMIT_MAX": "1000",
        "TENANT_SERVICE_URL": "",
    })
    get_settings.cache_clear()
    from app.main import create_app

    bare = TestClient(create_app(), raise_server_exceptions=False)
    try:
        r = bare.put(PATH, json={"name": "محل"}, headers=_headers())
        assert r.status_code == 503 and r.json()["error"] == "NOT_CONFIGURED"
    finally:
        os.environ.clear()
        os.environ.update(saved)
        get_settings.cache_clear()


def test_a_token_with_no_establishment_renames_nothing(client, monkeypatch):
    """A platform-level token on a tenant surface. Refused, never defaulted — defaulting here would
    hand the rename to whichever shop the empty string happens to key, and the registry's door
    trusts the id we put in the path."""
    registry = _Registry()
    _patch(monkeypatch, registry)
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "u_platform", "iss": ISS, "aud": AUD,
                      "caps": ["operations.manage"], "tenant": "",
                      "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")

    r = client.put(PATH, json={"name": "محل"}, headers={"Authorization": f"Bearer {tok}"})

    assert r.status_code == 403
    assert registry.calls == [], "nothing may reach the registry without an establishment"
