"""The exact bytes this would put on the wire — the only way to check a REST shape with no cluster.

WHAT THIS PROVES AND WHAT IT CANNOT. It proves the method, the path, the content-type and the body
are the ones the Kubernetes API reference specifies for a merge patch of a Secret and of a
Deployment. It does NOT prove a real API server accepts them: nothing here has ever spoken to one,
and no test on a laptop can. That single verification is a manual step, recorded in the values
file, and pretending otherwise would be the exact failure this repository keeps writing gates
about — a green suite standing in for a check nobody performed.

The fake transport records instead of sending, which is also what makes the negative assertions
possible: that a read never carries a body, and that the value is base64 of exactly what was
handed in and not of something re-encoded on the way.
"""
from __future__ import annotations

import base64
import json

import pytest

from app.adapters.k8s_client import K8sClient, K8sError


class FakeTransport:
    """Records every call and answers from a queued script."""

    def __init__(self, replies=None):
        self.calls: list[dict] = []
        self._replies = list(replies or [])

    def request(self, method, url, *, headers, body):
        self.calls.append({"method": method, "url": url, "headers": headers, "body": body})
        if self._replies:
            return self._replies.pop(0)
        return 200, b"{}"

    @property
    def last(self) -> dict:
        return self.calls[-1]


def client(replies=None, token_file=None, tmp_path=None) -> tuple[K8sClient, FakeTransport]:
    t = FakeTransport(replies)
    if token_file is None:
        token_file = tmp_path / "token"
        token_file.write_text("sa-token-value\n", encoding="utf-8")
    return K8sClient(t, host="10.43.0.1", port="443", token_file=str(token_file)), t


# ── writing a secret ──────────────────────────────────────────────────────────────────────────

def test_a_write_is_one_merge_patch_carrying_the_value_and_all_three_annotations(tmp_path):
    c, t = client(tmp_path=tmp_path)
    c.patch_secret("base-services", "notification-service-secrets",
                   data={"META_APP_SECRET": "s3cr3t-value"},
                   annotations={"raje3.sa/secret-meta-app-secret-last4": "alue",
                                "raje3.sa/secret-meta-app-secret-updated-at": "2026-08-31T09:00:00Z",
                                "raje3.sa/secret-meta-app-secret-updated-by": "op-7"})
    call = t.last
    assert call["method"] == "PATCH"
    assert call["url"] == ("https://10.43.0.1:443/api/v1/namespaces/base-services"
                           "/secrets/notification-service-secrets")
    assert call["headers"]["Content-Type"] == "application/merge-patch+json"
    assert call["headers"]["Authorization"] == "Bearer sa-token-value"
    sent = json.loads(call["body"])
    # THE VALUE IS BASE64 OF EXACTLY WHAT WAS HANDED IN. `data` is the field's contract; sending
    # it here rather than through `stringData` keeps what we transmit identical to what is stored.
    assert sent["data"] == {"META_APP_SECRET": base64.b64encode(b"s3cr3t-value").decode()}
    assert sent["metadata"]["annotations"]["raje3.sa/secret-meta-app-secret-last4"] == "alue"
    assert len(sent["metadata"]["annotations"]) == 3
    # ONE REQUEST, NOT TWO. A value written by one call and annotations by another can half-fail,
    # leaving the screen describing a credential that is no longer there.
    assert len(t.calls) == 1


def test_a_write_never_replaces_the_object(tmp_path):
    """A PUT, or a patch that named `metadata` wholesale, would drop every other key in the Secret
    and every annotation somebody else put on it."""
    c, t = client(tmp_path=tmp_path)
    c.patch_secret("base-services", "s", data={"K": "v"}, annotations={"a": "b"})
    sent = json.loads(t.last["body"])
    assert set(sent) == {"data", "metadata"}
    assert set(sent["metadata"]) == {"annotations"}


# ── restarting a deployment ───────────────────────────────────────────────────────────────────

def test_a_restart_is_the_same_annotation_kubectl_rollout_restart_writes(tmp_path):
    c, t = client(tmp_path=tmp_path)
    c.restart_deployment("base-services", "notification-service", at="2026-08-31T09:00:00Z")
    call = t.last
    assert call["method"] == "PATCH"
    assert call["url"] == ("https://10.43.0.1:443/apis/apps/v1/namespaces/base-services"
                           "/deployments/notification-service")
    assert call["headers"]["Content-Type"] == "application/merge-patch+json"
    assert json.loads(call["body"]) == {"spec": {"template": {"metadata": {"annotations": {
        "kubectl.kubernetes.io/restartedAt": "2026-08-31T09:00:00Z"}}}}}


# ── reading ───────────────────────────────────────────────────────────────────────────────────

def test_a_read_returns_annotations_and_discards_the_data_field(tmp_path):
    """THE ASSERTION THIS FILE EXISTS FOR. The API server has no field selector for this, so the
    real value DOES come back over the wire — and it is dropped one layer below every caller."""
    body = json.dumps({
        "metadata": {"annotations": {"raje3.sa/secret-assistant-model-credential-last4": "9xQ2"}},
        "data": {"ASSISTANT_MODEL_CREDENTIAL": base64.b64encode(b"the-real-live-key").decode()},
    }).encode()
    c, t = client([(200, body)], tmp_path=tmp_path)
    out = c.read_secret_annotations("base-services", "whatsapp-assistant-secrets")
    assert out == {"raje3.sa/secret-assistant-model-credential-last4": "9xQ2"}
    assert t.last["method"] == "GET"
    assert t.last["body"] is None
    assert "ASSISTANT_MODEL_CREDENTIAL" not in json.dumps(out)


def test_a_secret_object_that_does_not_exist_yet_reads_as_nothing_configured(tmp_path):
    """A fresh cluster before anything was ever set. «غير مُعدّ» is the honest answer, not a banner."""
    c, _ = client([(404, b'{"kind":"Status"}')], tmp_path=tmp_path)
    assert c.read_secret_annotations("base-services", "nope") == {}


def test_a_secret_with_no_annotations_reads_as_nothing_configured(tmp_path):
    c, _ = client([(200, b'{"metadata":{}}')], tmp_path=tmp_path)
    assert c.read_secret_annotations("base-services", "s") == {}


# ── failures, each with its own sentence ──────────────────────────────────────────────────────

def test_a_refusal_by_the_cluster_role_says_so_rather_than_looking_like_an_outage(tmp_path):
    c, _ = client([(403, b'{"message":"forbidden"}')], tmp_path=tmp_path)
    with pytest.raises(K8sError) as exc:
        c.patch_secret("base-services", "s", data={"K": "v"}, annotations={})
    assert exc.value.status == 403
    assert "Role" in str(exc.value)


def test_a_missing_service_account_token_is_named_not_a_401_later(tmp_path):
    c = K8sClient(FakeTransport(), host="10.43.0.1", port="443",
                  token_file=str(tmp_path / "absent"))
    with pytest.raises(K8sError) as exc:
        c.patch_secret("base-services", "s", data={"K": "v"}, annotations={})
    assert "ServiceAccount token" in str(exc.value)


def test_the_token_is_read_at_call_time_so_a_rotated_one_is_picked_up(tmp_path):
    """kubelet rewrites a projected token roughly hourly. A client that cached it at boot works
    for an hour and 401s for ever after — a failure no test that runs in seconds would see."""
    token = tmp_path / "token"
    token.write_text("first", encoding="utf-8")
    c, t = client(token_file=token)
    c.patch_secret("ns", "s", data={"K": "v"}, annotations={})
    token.write_text("second", encoding="utf-8")
    c.patch_secret("ns", "s", data={"K": "v"}, annotations={})
    assert t.calls[0]["headers"]["Authorization"] == "Bearer first"
    assert t.calls[1]["headers"]["Authorization"] == "Bearer second"


def test_no_cluster_address_refuses_instead_of_guessing_one(tmp_path):
    token = tmp_path / "token"
    token.write_text("t", encoding="utf-8")
    c = K8sClient(FakeTransport(), host="", port="443", token_file=str(token))
    with pytest.raises(K8sError, match="not running inside a cluster"):
        c.read_secret_annotations("ns", "s")
