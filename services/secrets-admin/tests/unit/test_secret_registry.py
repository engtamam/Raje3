"""The registry is the allow-list, so its shape is a security property rather than a data class.

Every assertion here is about a failure that would be SILENT. A duplicate key would mean one entry
shadowing another in `BY_KEY` — the screen shows five rows, one of them writes to the wrong Secret,
and nothing anywhere says so. An annotation suffix with an underscore would be rejected by the API
server at the moment of writing, in production, on the one path that matters. A namespace or
deployment that drifts out of the cluster Role's `resourceNames` would 403 at exactly that moment
too — so the pair is pinned here, in the same test file, rather than trusted to stay in step.
"""
from __future__ import annotations

import re

from app.core.secret_registry import (
    ANNOTATION_PREFIX,
    BY_KEY,
    SECRETS,
    last4_annotation,
    last4_of,
    updated_at_annotation,
    updated_by_annotation,
)


def test_the_registry_is_the_five_we_decided_on():
    assert {e.key for e in SECRETS} == {
        "META_APP_ID", "META_APP_SECRET", "WHATSAPP_WEBHOOK_VERIFY_TOKEN",
        "WHATSAPP_360DIALOG_API_KEY", "GEMINI_API_KEY",
    }


def test_no_key_is_declared_twice():
    """A duplicate would shadow silently in BY_KEY and write to the wrong Secret."""
    keys = [e.key for e in SECRETS]
    assert len(keys) == len(set(keys))
    assert len(BY_KEY) == len(SECRETS)


def test_every_entry_carries_every_field_it_needs_to_be_written():
    for e in SECRETS:
        assert e.key and e.secret and e.namespace and e.deployment and e.label, e
        # THE LABEL IS WHAT THE OWNER READS, so it must be Arabic rather than the env var name
        # repeated. An ASCII-only label is the signature of an entry added without a decision.
        assert any("؀" <= ch <= "ۿ" for ch in e.label), e.key


def test_only_the_two_secret_objects_the_cluster_role_names():
    """Pinned against deploy/k3s/secrets-admin-rbac.yaml. A sixth entry pointing at a third Secret
    would be refused 403 by the cluster, and the failure would arrive in production."""
    assert {e.secret for e in SECRETS} == {
        "notification-service-secrets", "whatsapp-assistant-secrets"}
    assert {e.deployment for e in SECRETS} == {"notification-service", "whatsapp-assistant"}
    assert {e.namespace for e in SECRETS} == {"base-services"}


def test_every_annotation_key_is_one_kubernetes_accepts():
    """`META_APP_SECRET` -> `meta-app-secret`, and the whole annotation name is checked, not just
    the suffix — the prefix is ours and must stay ours."""
    valid = re.compile(r"^raje3\.sa/[a-z0-9]([-a-z0-9.]*[a-z0-9])?$")
    for e in SECRETS:
        assert "_" not in e.annotation_suffix
        assert e.annotation_suffix == e.key.lower().replace("_", "-")
        for name in (last4_annotation(e), updated_at_annotation(e), updated_by_annotation(e)):
            assert name.startswith(ANNOTATION_PREFIX)
            assert valid.match(name), name
            assert len(name.split("/", 1)[1]) <= 63, name


def test_the_three_annotations_of_one_key_are_three_different_names():
    for e in SECRETS:
        names = {last4_annotation(e), updated_at_annotation(e), updated_by_annotation(e)}
        assert len(names) == 3


def test_two_keys_in_one_secret_object_never_share_an_annotation():
    """Four of the five live in `notification-service-secrets`, so a suffix that did not embed the
    key name would have each write overwrite the previous one's last4."""
    all_names = [last4_annotation(e) for e in SECRETS]
    assert len(all_names) == len(set(all_names))


def test_last4_never_invents_a_character():
    assert last4_of("abcdefgh") == "efgh"
    # A three-character value yields three characters. Padding to a fixed width would be inventing
    # a character of a secret, which is worse than a short answer.
    assert last4_of("abc") == "abc"
    assert last4_of("") == ""
