"""The five external-provider credentials an owner may replace without a developer.

WHY THIS FILE EXISTS AT ALL, AND WHY IT IS A CLOSED LIST.

Meta rotates an app secret, a 360dialog key leaks in a screenshot, a Gemini key hits its quota and
is reissued. Every one of those is an ordinary Tuesday, and until now every one of them meant
somebody with a kubeconfig running `kubectl create secret … --dry-run | kubectl apply` and then
remembering to restart the right Deployment. That is a developer on call for a task with no
engineering in it, performed by hand, at a keyboard where one wrong namespace edits the wrong
cluster.

IT IS A CLOSED LIST BECAUSE THE ALTERNATIVE IS A GENERIC SECRET EDITOR. A route that took a Secret
name and a key from the request body would let whoever holds this capability rewrite
`identity-service-secrets` — the signing key every token in the product is verified against — from
a form. The RBAC Role (deploy/k3s/secrets-admin-rbac.yaml) names the same two objects with
`resourceNames`, so the cluster refuses what this list does not contain even if a future bug here
tried; the two are deliberately the same fact written twice, in the two places that can enforce it.

ADDING A SIXTH IS A ONE-PLACE EDIT HERE plus one line in that Role. Nothing else in this service
knows the name of a secret: the routes, the console screen and the audit record all read this list.

WHAT IS DELIBERATELY NOT HERE: our own secrets. INTERNAL_SERVICE_TOKEN, TOKEN_PUBLIC_KEY, PII_SALT
and BACKUP_KEK are shared across the fleet and changing one of them is a coordinated migration, not
a form submission — a console that could edit them would be a console that can split the product in
half with one save.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SecretEntry:
    """One credential, and everything needed to write it and to make the write take effect."""

    #: The env var name the consuming service reads. Also the key inside the k8s Secret's `data`.
    key: str
    #: The k8s Secret object that holds it.
    secret: str
    #: The namespace that Secret lives in.
    namespace: str
    #: The Deployment that must be restarted for the new value to be read. A secret is injected as
    #: an env var at container start, so a write with no restart is a write that changes nothing
    #: until the next unrelated deploy — the failure mode where the owner pastes a correct key,
    #: sees success, and watches the sends keep failing.
    deployment: str
    #: What the owner reads on the screen. Arabic, because the person doing this is the owner.
    label: str

    @property
    def annotation_suffix(self) -> str:
        """`META_APP_SECRET` -> `meta-app-secret`.

        A k8s annotation key must be a valid DNS-ish name: lowercase alphanumerics, `-`, `_` and
        `.` are all technically accepted in the NAME part, but the convention across this cluster
        is lowercase-with-dashes and an underscore reads as a typo forever after. The transform is
        a property rather than a sixth field because two spellings of one fact drift.
        """
        return self.key.lower().replace("_", "-")


#: The whole scope of this service. See the module docstring before adding to it.
SECRETS: tuple[SecretEntry, ...] = (
    # ── WhatsApp, through Meta directly ───────────────────────────────────────────────────────
    SecretEntry(
        key="META_APP_ID",
        secret="notification-service-secrets",
        namespace="base-services",
        deployment="notification-service",
        label="معرّف تطبيق ميتا",
    ),
    SecretEntry(
        key="META_APP_SECRET",
        secret="notification-service-secrets",
        namespace="base-services",
        deployment="notification-service",
        label="سر تطبيق ميتا",
    ),
    # Meta calls our webhook with this token on every re-subscribe. A stale one does not break
    # sending — it breaks RECEIVING, silently, which is the harder half to notice.
    SecretEntry(
        key="WHATSAPP_WEBHOOK_VERIFY_TOKEN",
        secret="notification-service-secrets",
        namespace="base-services",
        deployment="notification-service",
        label="توكن تحقق الـwebhook",
    ),
    # ── WhatsApp, through the 360dialog BSP ───────────────────────────────────────────────────
    SecretEntry(
        key="WHATSAPP_360DIALOG_API_KEY",
        secret="notification-service-secrets",
        namespace="base-services",
        deployment="notification-service",
        label="مفتاح 360dialog",
    ),
    # ── The assistant's model ─────────────────────────────────────────────────────────────────
    SecretEntry(
        key="GEMINI_API_KEY",
        secret="whatsapp-assistant-secrets",
        namespace="base-services",
        deployment="whatsapp-assistant",
        label="مفتاح Gemini",
    ),
)

#: key -> entry. Built once; the routes look up by key and 404 on anything not here.
BY_KEY: dict[str, SecretEntry] = {e.key: e for e in SECRETS}

# ── the annotation names, in ONE place ────────────────────────────────────────────────────────
#
# THE PREFIX IS OURS AND MUST STAY OURS. `kubernetes.io/` and `k8s.io/` are reserved, and an
# annotation under a prefix somebody else owns is one a future controller may rewrite.
ANNOTATION_PREFIX = "raje3.sa/secret-"


def last4_annotation(entry: SecretEntry) -> str:
    return f"{ANNOTATION_PREFIX}{entry.annotation_suffix}-last4"


def updated_at_annotation(entry: SecretEntry) -> str:
    return f"{ANNOTATION_PREFIX}{entry.annotation_suffix}-updated-at"


def updated_by_annotation(entry: SecretEntry) -> str:
    return f"{ANNOTATION_PREFIX}{entry.annotation_suffix}-updated-by"


def last4_of(value: str) -> str:
    """The only fragment of a secret that ever leaves this process.

    FOUR CHARACTERS, AND SHORTER WHEN THE VALUE IS SHORTER — never padded, never a fixed-width
    mask built from the real thing. `value[-4:]` on a three-character value returns three
    characters, which is correct: inventing a fourth would be inventing a character of a secret.
    """
    return value[-4:]
