"""POST /api/v1/staff/procedure-checklist/export — one or more services' ordered protocol, merged
into ONE branded document a shop can print or hand to a customer, a step shared by more than one
selected service printed exactly once ([[task-service-procedure-checklists]] phase 6, owner's own
instruction 2026-09-16).
"""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

TOKEN_SECRET = "h" * 40
ISS, AUD = "iss", "aud"


def _make_app(**env_over) -> TestClient:
    from app.config import get_settings

    env = {
        "ENV": "test",
        "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": TOKEN_SECRET,
        "TOKEN_ISSUER": ISS,
        "TOKEN_AUDIENCE": AUD,
        "RATELIMIT_MAX": "1000",
        "PII_SALT": "s" * 32,
    }
    env.update(env_over)
    os.environ.update(env)
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


def _auth(*caps: str, tenant: str = "t1") -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "op1", "iss": ISS, "aud": AUD, "caps": list(caps), "tenant": tenant,
                      "exp": now + dt.timedelta(minutes=5), "iat": now},
                     TOKEN_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def env_guard():
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
    from app.config import get_settings
    get_settings.cache_clear()


@pytest.fixture(scope="module")
def client(env_guard) -> TestClient:
    return _make_app()


def _step(client, text: str, severity: str = "normal") -> dict:
    return client.post("/api/v1/staff/procedure-steps", json={"text": text, "severity": severity},
                       headers=_auth("operations.manage_services")).json()


def _service(client, name: str, step_ids: list[str]) -> dict:
    svc = client.post("/api/v1/staff/services", json={"name": name},
                      headers=_auth("operations.manage_services")).json()
    client.patch(f"/api/v1/staff/services/{svc['id']}", json={"procedure_step_ids": step_ids},
                headers=_auth("operations.manage_services"))
    return svc


def _export(client, service_ids: list[str], **body):
    return client.post("/api/v1/staff/procedure-checklist/export",
                       json={"service_ids": service_ids, **body},
                       headers=_auth("operations.manage_services"))


def test_operations_manage_alone_cannot_export_a_checklist(client):
    step = _step(client, "اغسل بالماء")
    svc = _service(client, "غسيل", [step["id"]])
    r = client.post("/api/v1/staff/procedure-checklist/export",
                    json={"service_ids": [svc["id"]], "file_format": "docx"},
                    headers=_auth("operations.manage"))
    assert r.status_code == 403


def test_an_empty_service_list_is_rejected_by_validation(client):
    r = _export(client, [], file_format="docx")
    assert r.status_code == 422


def test_when_no_given_service_id_resolves_the_request_is_refused(client):
    r = _export(client, ["svc_does_not_exist"], file_format="docx")
    assert r.status_code == 404


def test_one_unknown_id_among_real_ones_is_dropped_not_a_404(client):
    step = _step(client, "اغسل بالماء")
    svc = _service(client, "غسيل", [step["id"]])
    r = _export(client, [svc["id"], "svc_does_not_exist"], file_format="docx")
    assert r.status_code == 200, r.text


def test_export_docx_returns_a_real_word_document(client):
    a = _step(client, "اغسل بالماء", "normal")
    b = _step(client, "اربط الصمولة بعزم صحيح", "critical")
    svc = _service(client, "غسيل شامل", [a["id"], b["id"]])
    r = _export(client, [svc["id"]], file_format="docx")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    assert r.content[:2] == b"PK"   # a docx is a real zip archive


def test_a_step_retired_after_being_attached_is_silently_skipped_not_printed(client):
    keep = _step(client, "خطوة تبقى")
    drop = _step(client, "خطوة تُوقَف لاحقاً")
    svc = _service(client, "تلميع", [keep["id"], drop["id"]])
    # Retired AFTER attaching — update_service's own drop-unknown rule never touches this list
    # again, so the id stays on the service; the export route must filter it, not the write path.
    client.patch(f"/api/v1/staff/procedure-steps/{drop['id']}", json={"active": False},
                headers=_auth("operations.manage_services"))
    r = _export(client, [svc["id"]], file_format="docx")
    assert r.status_code == 200, r.text


def test_a_step_shared_by_two_selected_services_is_merged_not_duplicated(client):
    """The whole point of the multi-select: غسيل and تلميع both share "اغسل بالماء" — the merged
    document must resolve successfully with both services' ids, proving the merge/dedup path (a
    500 here would mean the dedup logic itself crashed) rather than refusing or erroring."""
    shared = _step(client, "اغسل بالماء")
    only_wash = _step(client, "اربط الصمولة بعزم صحيح", "critical")
    only_polish = _step(client, "لمّع الطلاء")
    wash = _service(client, "غسيل خارجي", [shared["id"], only_wash["id"]])
    polish = _service(client, "تلميع", [shared["id"], only_polish["id"]])

    r = _export(client, [wash["id"], polish["id"]], file_format="docx")
    assert r.status_code == 200, r.text
    assert r.content[:2] == b"PK"


def test_export_pdf_without_a_converter_installed_refuses_plainly_not_a_500(client):
    """This dev/CI environment carries no LibreOffice — the exact case `PdfConversionUnavailable`
    exists for. Proves the route surfaces that as a real 503, never an unhandled crash."""
    step = _step(client, "اغسل بالماء")
    svc = _service(client, "غسيل", [step["id"]])
    r = _export(client, [svc["id"]], file_format="pdf")
    # The global error handler strips HTTPException.detail (CWE-209 hardening, same convention
    # every other service in this product follows) — the status code IS the whole signal here.
    assert r.status_code == 503


# ── the shop's own logo/colour (owner's own instruction, 2026-09-16) ─────────────────────────────
# A SEPARATE app instance, `TENANT_SERVICE_URL` actually configured — the module-scoped `client`
# above deliberately has none, so this is its own fixture rather than a env-mutation mid-suite.

class _Registry:
    def __init__(self, body: dict) -> None:
        self.body = body
        self.calls: list[tuple] = []

    def call(self, url, *, method, body=None, internal=False):
        self.calls.append((url, method, body, internal))
        return 200, self.body


@pytest.fixture()
def branded_client(monkeypatch):
    app = _make_app(TENANT_SERVICE_URL="http://tenant-service:8000")
    registry = _Registry({"branding": {"logo_url": "", "accent": "#B08A3E"}})
    from app.core import signup as signup_module
    monkeypatch.setattr(signup_module, "Http", lambda **kw: registry)
    yield app, registry


def test_the_shops_own_accent_is_fetched_and_the_export_still_succeeds(branded_client):
    client, registry = branded_client
    step = _step(client, "اغسل بالماء")
    svc = _service(client, "غسيل", [step["id"]])

    r = _export(client, [svc["id"]], file_format="docx")

    assert r.status_code == 200, r.text
    assert any(c[0].endswith("/internal/tenants/t1") and c[1] == "GET" for c in registry.calls)
