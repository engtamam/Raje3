"""Both routes, through the real door — token, capability, rate limit, audit and all.

THE LOAD-BEARING TEST IN THIS FILE IS `test_the_list_can_never_carry_a_value`. Everything else is
ordinary route behaviour; that one is the product promise, and it is written to fail on a shape
rather than on a string — it walks the whole response for any key that could plausibly hold a
credential, so a future edit that adds `{"value": …}` to a row breaks it even if the value it
happens to carry in the test is an empty string.

THE K8S ADAPTER IS FAKED. Its own wire shape is proved in tests/unit/test_k8s_client.py; here it
is a recorder, so these tests are about the route's decisions — refuse, 404, 400, audit, restart —
and not about HTTP.
"""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

TOKEN_SECRET = "h" * 40
ISS, AUD = "iss", "aud"

CAP = "platform.secrets_manage"
LIVE_VALUE = "EAAB-a-real-looking-provider-key-9xQ2"


class FakeK8s:
    """Records patches; answers reads from a dict the test controls."""

    def __init__(self) -> None:
        self.annotations: dict[tuple[str, str], dict[str, str]] = {}
        self.patches: list[dict] = []
        self.restarts: list[dict] = []
        self.fail_restart = False

    def read_secret_annotations(self, namespace, name):
        return dict(self.annotations.get((namespace, name), {}))

    def patch_secret(self, namespace, name, *, data, annotations):
        self.patches.append({"namespace": namespace, "name": name, "data": data,
                             "annotations": annotations})
        self.annotations.setdefault((namespace, name), {}).update(annotations)
        return {}

    def restart_deployment(self, namespace, name, *, at):
        if self.fail_restart:
            from app.adapters.k8s_client import K8sError
            raise K8sError("the cluster API server answered HTTP 500", 500)
        self.restarts.append({"namespace": namespace, "name": name, "at": at})
        return {}


class RecordingAuditor:
    def __init__(self) -> None:
        self.events: list[dict] = []

    async def record(self, action, **kw):
        self.events.append({"action": action, **kw})


@pytest.fixture(scope="module")
def env_guard():
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
    from app.config import get_settings
    get_settings.cache_clear()


@pytest.fixture
def built(env_guard):
    from app.config import get_settings

    os.environ.update({
        "ENV": "test",
        "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": TOKEN_SECRET,
        "TOKEN_ISSUER": ISS,
        "TOKEN_AUDIENCE": AUD,
        "RATELIMIT_MAX": "1000",
    })
    get_settings.cache_clear()
    from app.main import create_app

    app = create_app()
    k8s = FakeK8s()
    auditor = RecordingAuditor()
    app.state.container.k8s = k8s
    app.state.auditor = auditor
    return TestClient(app, raise_server_exceptions=False), k8s, auditor


def _auth(*caps: str) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "op-7", "iss": ISS, "aud": AUD, "caps": list(caps),
                      "exp": now + dt.timedelta(minutes=5), "iat": now},
                     TOKEN_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


# ── the door ──────────────────────────────────────────────────────────────────────────────────

def test_no_token_is_refused_at_the_door(built):
    client, _, _ = built
    assert client.get("/api/v1/secrets").status_code in (401, 403)
    assert client.post("/api/v1/secrets/META_APP_ID", json={"value": "x"}).status_code in (401, 403)


def test_a_neighbouring_platform_capability_does_not_open_this(built):
    """`platform.operations` is the widest capability our operators hold and it is NOT this one.
    If it were accepted here, every content operator could replace the key the whole product sends
    with — which is the entire reason this capability was minted separately."""
    client, _, _ = built
    assert client.get("/api/v1/secrets", headers=_auth("platform.operations")).status_code == 403
    assert client.post("/api/v1/secrets/META_APP_ID", json={"value": "x"},
                       headers=_auth("platform.operations", "platform.secrets")).status_code == 403


# ── the list ──────────────────────────────────────────────────────────────────────────────────

def test_the_list_names_every_registry_entry_with_its_arabic_label(built):
    from app.core.secret_registry import SECRETS

    client, _, _ = built
    body = client.get("/api/v1/secrets", headers=_auth(CAP)).json()
    assert [r["key"] for r in body["secrets"]] == [e.key for e in SECRETS]
    assert body["secrets"][0]["label"] == "معرّف تطبيق ميتا"


def test_an_unwritten_secret_reads_as_not_configured(built):
    client, _, _ = built
    row = client.get("/api/v1/secrets", headers=_auth(CAP)).json()["secrets"][0]
    assert row["configured"] is False
    assert row["last4"] is None and row["updated_at"] is None and row["updated_by"] is None


def test_a_written_secret_shows_its_last_four_and_who_set_it(built):
    client, k8s, _ = built
    client.post("/api/v1/secrets/GEMINI_API_KEY", json={"value": LIVE_VALUE},
                headers=_auth(CAP))
    rows = {r["key"]: r for r in client.get("/api/v1/secrets",
                                            headers=_auth(CAP)).json()["secrets"]}
    row = rows["GEMINI_API_KEY"]
    assert row["configured"] is True
    assert row["last4"] == LIVE_VALUE[-4:]
    assert row["updated_by"] == "op-7"
    assert row["updated_at"].endswith("Z")
    assert k8s.annotations  # it really went through the adapter


def test_a_cluster_that_will_not_answer_says_so_instead_of_reporting_not_configured(built):
    """Reporting «غير مُعدّ» for a secret we merely could not read tells the owner to set a key
    that is already set — and that ends in a live credential overwritten during an incident."""
    client, k8s, _ = built

    def boom(namespace, name):
        from app.adapters.k8s_client import K8sError
        raise K8sError("the cluster API server is unreachable: timed out")

    k8s.read_secret_annotations = boom
    rows = client.get("/api/v1/secrets", headers=_auth(CAP)).json()["secrets"]
    assert all(r["unreadable"] is True and r["configured"] is None for r in rows)


def test_the_list_can_never_carry_a_value(built):
    """The promise this whole service is built on, asserted on the response's SHAPE.

    Written against every key in the tree rather than against the one string the test happens to
    have used: a row that grew a `value` field would break this even while holding an empty one.
    """
    client, _, _ = built
    client.post("/api/v1/secrets/GEMINI_API_KEY", json={"value": LIVE_VALUE}, headers=_auth(CAP))
    resp = client.get("/api/v1/secrets", headers=_auth(CAP))
    raw = resp.text
    assert LIVE_VALUE not in raw
    # ...and not base64 of it either, which is how it would arrive if `data` were ever passed on.
    import base64
    assert base64.b64encode(LIVE_VALUE.encode()).decode() not in raw

    forbidden = {"value", "data", "secret", "stringData", "plaintext"}

    def walk(node, path="$"):
        if isinstance(node, dict):
            for k, v in node.items():
                assert k not in forbidden, f"{path}.{k} could hold a secret value"
                walk(v, f"{path}.{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")

    walk(resp.json())


# ── the write ─────────────────────────────────────────────────────────────────────────────────

def test_a_key_that_is_not_in_the_registry_is_a_404(built):
    client, k8s, _ = built
    for key in ("IDENTITY_SIGNING_KEY", "", "../../etc/passwd", "meta_app_id"):
        r = client.post(f"/api/v1/secrets/{key}", json={"value": "x"}, headers=_auth(CAP))
        assert r.status_code in (404, 405), key
    assert k8s.patches == []


def test_an_empty_value_is_refused_with_a_sentence_the_owner_can_act_on(built):
    client, k8s, _ = built
    for value in ("", "   ", "\n\t"):
        r = client.post("/api/v1/secrets/META_APP_SECRET", json={"value": value},
                        headers=_auth(CAP))
        assert r.status_code == 400
        assert r.json()["reason"]
    assert k8s.patches == []


def test_a_write_patches_the_right_object_and_restarts_the_right_deployment(built):
    client, k8s, _ = built
    r = client.post("/api/v1/secrets/META_APP_SECRET", json={"value": LIVE_VALUE},
                    headers=_auth(CAP))
    assert r.status_code == 200
    assert r.json() == {"key": "META_APP_SECRET", "last4": LIVE_VALUE[-4:],
                        "updated_at": r.json()["updated_at"], "restarted": True}
    assert LIVE_VALUE not in r.text

    patch = k8s.patches[0]
    assert patch["namespace"] == "base-services"
    assert patch["name"] == "notification-service-secrets"
    assert patch["data"] == {"META_APP_SECRET": LIVE_VALUE}
    assert set(patch["annotations"]) == {
        "raje3.sa/secret-meta-app-secret-last4",
        "raje3.sa/secret-meta-app-secret-updated-at",
        "raje3.sa/secret-meta-app-secret-updated-by"}
    assert k8s.restarts == [{"namespace": "base-services", "name": "notification-service",
                             "at": patch["annotations"][
                                 "raje3.sa/secret-meta-app-secret-updated-at"]}]


def test_a_write_is_audited_as_the_person_and_the_record_holds_no_fragment_of_the_value(built):
    client, _, auditor = built
    client.post("/api/v1/secrets/META_APP_SECRET", json={"value": LIVE_VALUE}, headers=_auth(CAP))
    assert len(auditor.events) == 1
    ev = auditor.events[0]
    assert ev["action"] == "platform.secret_changed"
    # THE TOKEN'S SUBJECT, never a field in the body — «who did this» is the whole record.
    assert ev["actor"] == "op-7"
    assert ev["resource"] == "secret:notification-service-secrets:META_APP_SECRET"
    blob = repr(ev)
    assert LIVE_VALUE not in blob
    # NOT EVEN THE LAST FOUR. The chain is permanent and widely readable.
    assert LIVE_VALUE[-4:] not in blob


def test_a_declared_action_is_the_one_that_is_emitted():
    """An action the auditor does not know is refused write-ahead: the route would 500 and perform
    nothing, for ever, and no test that stubs the auditor would notice."""
    from app.auditable_actions import AUDITABLE_ACTIONS

    assert {a["action"] for a in AUDITABLE_ACTIONS} == {"platform.secret_changed"}
    assert AUDITABLE_ACTIONS[0]["critical"] is True


def test_reading_the_list_is_not_audited(built):
    """Recording every page load would bury the writes an investigation is looking for."""
    client, _, auditor = built
    client.get("/api/v1/secrets", headers=_auth(CAP))
    assert auditor.events == []


def test_a_saved_value_whose_restart_failed_says_saved_but_not_applied(built):
    """A real, recoverable state. Reporting success would leave the owner watching a correct key
    fail to send; reporting a plain failure would have him paste it again, which fixes nothing."""
    client, k8s, _ = built
    k8s.fail_restart = True
    r = client.post("/api/v1/secrets/GEMINI_API_KEY", json={"value": LIVE_VALUE},
                    headers=_auth(CAP))
    assert r.status_code == 400
    body = r.json()
    assert body["restarted"] is False
    assert body["last4"] == LIVE_VALUE[-4:]
    assert "whatsapp-assistant" in body["reason"]
    assert k8s.patches, "the value WAS saved — that is what the message says"


def test_there_is_no_route_that_reads_a_value_back(built):
    """Not «it returns 404 today» — that no such handler is mounted at all.

    ASSERTED BY REQUEST, NOT BY INTROSPECTING `client.app.routes` — that attribute's shape
    depends on exactly which TestClient/Starlette version builds it (found live: identical code,
    identical FastAPI app, empty under pytest's own TestClient construction path while a plain
    script import showed all eleven routes fine — a version quirk, not a fact about this app).
    A live request settles it either way: a genuinely unmounted GET answers 405 (method not
    allowed on a path that only has POST) or 404 (no path at all), never 200/401/403, which is
    what an existing-but-guarded route would answer.
    """
    client, _, _ = built
    r = client.get("/api/v1/secrets/META_APP_ID", headers=_auth(CAP))
    assert r.status_code in (404, 405), r.status_code
    # AND NOT BECAUSE THE DOOR REFUSED IT FIRST — a real token with the real capability got here;
    # a 401/403 would mean this proved the auth gate, not the absence of a read route.
    assert r.status_code != 401 and r.status_code != 403
