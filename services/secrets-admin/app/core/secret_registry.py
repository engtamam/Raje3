"""The external-provider credentials an owner may replace without a developer.

WHY THIS FILE EXISTS AT ALL, AND WHY IT IS A CLOSED LIST.

Meta rotates an app secret, a webhook verify token leaks in a screenshot, a third-party AI key hits
its quota and is reissued. Every one of those is an ordinary Tuesday, and until now every one of them meant
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

ADDING A NEW ONE IS A ONE-PLACE EDIT HERE — plus one line in that Role, UNLESS THE SECRET OBJECT IS
ALREADY NAMED THERE (WHATSAPP_ACCESS_TOKEN/WHATSAPP_PHONE_NUMBER_ID/WHATSAPP_BUSINESS_ACCOUNT_ID
below all write into `notification-service-secrets`, already named in the Role's own
`resourceNames` alongside every other key that shares that Secret object — no Role change needed
for those three). Nothing else in this service knows the name of a secret: the routes, the console
screen and the audit record all read this list.

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
    # NOT ACTUALLY SECRET — Meta's own Facebook Login for Business config id is sent from the
    # BROWSER, in the clear, on every Embedded Signup popup (`fb.login({config_id, ...})`); Meta's
    # App ID above is the same class of value (the `client_id` of a public OAuth-style exchange).
    # It rides this sealed-secret pipe anyway, deliberately, for one reason only: so setting it is
    # 100% from this one panel, with no separate console rebuild step — see console's meta.ts and
    # operations' connect.py for the runtime read this feeds (GET /whatsapp/config).
    SecretEntry(
        key="META_APP_CONFIG_ID",
        secret="notification-service-secrets",
        namespace="base-services",
        deployment="notification-service",
        label="معرّف إعداد تسجيل الدخول (Facebook Login for Business)",
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
    # ── WhatsApp, through Meta directly — the PLATFORM'S OWN identity, not any shop's ────────────
    # A shop's own WHATSAPP_ACCESS_TOKEN is a per-tenant credential, resolved through the secret
    # store its own onboarding (Embedded Signup) writes to — that path is unrelated to this one.
    # These three are the ENVIRONMENT FALLBACK ProviderPool._credential() reads for tenant="" — the
    # platform's OWN sends (signup OTP today; other platform-initiated messages later), which have
    # no tenant to resolve a stored credential for. See notification-service.values.yaml's own note
    # on why WHATSAPP_CHAIN stays "console" until these three are real.
    SecretEntry(
        key="WHATSAPP_ACCESS_TOKEN",
        secret="notification-service-secrets",
        namespace="base-services",
        deployment="notification-service",
        label="توكن واتساب المنصة (System User)",
    ),
    SecretEntry(
        key="WHATSAPP_PHONE_NUMBER_ID",
        secret="notification-service-secrets",
        namespace="base-services",
        deployment="notification-service",
        label="معرّف رقم واتساب المنصة",
    ),
    # Needed for template submit/status/sync calls (MetaTemplateManager), not for sending itself —
    # kept alongside the other two rather than a later seventh edit, since all three arrive together
    # from the same Meta System User setup step.
    SecretEntry(
        key="WHATSAPP_BUSINESS_ACCOUNT_ID",
        secret="notification-service-secrets",
        namespace="base-services",
        deployment="notification-service",
        label="معرّف حساب واتساب الأعمال (WABA) للمنصة",
    ),
    # ── The assistant's model (via assistant-service, Vertex AI) ──────────────────────────────
    SecretEntry(
        key="ASSISTANT_MODEL_PROJECT",
        secret="whatsapp-assistant-secrets",
        namespace="base-services",
        deployment="whatsapp-assistant",
        label="مشروع ذكاء واتساب المحلات (Google Cloud)",
    ),
    SecretEntry(
        key="ASSISTANT_MODEL_CREDENTIAL",
        secret="whatsapp-assistant-secrets",
        namespace="base-services",
        deployment="whatsapp-assistant",
        label="مفتاح ذكاء واتساب المحلات (Google Cloud)",
    ),
    # ── The active payment gateway ────────────────────────────────────────────────────────────
    # GENERIC SLOT NAMES, DELIBERATELY NOT "TUWAIQPAY_*" — every gateway billing-service ships
    # (Moyasar, Tap, HyperPay, PayTabs, Geidea, APS, TuwaiqPay, ...) reuses the SAME two config
    # keys (PAYMENT_API_KEY/PAYMENT_EXTRA_SECRET), switched by PAYMENT_GATEWAY_DRIVER — a label
    # naming today's gateway would silently describe the wrong provider the day that changes. The
    # console's own help text below names the CURRENT gateway; this file's label stays generic.
    #
    # ADDED 2026-09-06 — a real, found gap: TuwaiqPay was activated (PAYMENT_GATEWAY_DRIVER in
    # deploy/services/billing-service.values.yaml) before either credential had anywhere safe to
    # be written. Without this entry the only way to set them was raw kubectl against
    # billing-service-secrets — exactly the access this whole service exists to remove. See
    # deploy/k3s/secrets-admin-rbac.yaml's matching addition — this entry is refused by the
    # cluster itself without it, not only by this file.
    SecretEntry(
        key="PAYMENT_API_KEY",
        secret="billing-service-secrets",
        namespace="base-services",
        deployment="billing-service",
        label="اسم مستخدم بوابة الدفع",
    ),
    # A THIRD SLOT, FOUND MISSING 2026-09-07 — config.py declares PAYMENT_API_KEY/PAYMENT_EXTRA_ID/
    # PAYMENT_EXTRA_SECRET as ONE set of three, and only two of the three had an entry here. Some
    # drivers use all three (APS: access_code + merchant_identifier + SHA phrase), some use two of
    # the three but not this pair (HyperPay: PAYMENT_API_KEY + entityId — no PAYMENT_EXTRA_SECRET;
    # PayPal/Stripe: PAYMENT_API_KEY + a second id — same shape). Leaving it out did not break
    # TuwaiqPay (it never reads this key) but silently capped every OTHER driver at "cannot be
    # fully configured from this screen" — the same shape of gap PAYMENT_PUBLISHABLE_KEY was.
    SecretEntry(
        key="PAYMENT_EXTRA_ID",
        secret="billing-service-secrets",
        namespace="base-services",
        deployment="billing-service",
        label="معرّف إضافي لبوابة الدفع (entityId / merchant_identifier / profile_id / client_secret)",
    ),
    SecretEntry(
        key="PAYMENT_EXTRA_SECRET",
        secret="billing-service-secrets",
        namespace="base-services",
        deployment="billing-service",
        label="كلمة مرور بوابة الدفع",
    ),
    # THE ONE PAYMENT CREDENTIAL A BROWSER IS MEANT TO READ — operations' own /subscription/status
    # route returns it verbatim so the plans screen can mint a card form; the two above never leave
    # billing-service. A DIFFERENT service (operations, not billing-service) holding a slice of the
    # same "is a payment gateway configured" answer, found the same day the other two were: nowhere
    # safe to write it either, until now.
    SecretEntry(
        key="PAYMENT_PUBLISHABLE_KEY",
        secret="operations-secrets",
        namespace="base-services",
        deployment="operations",
        label="المفتاح العام لبوابة الدفع (Publishable)",
    ),
    # ── Salla (the marketplace app — «تحالف استراتيجي» from a real Salla order) ──────────────
    # ALL THREE INTO `operations-secrets` — the integration lives inside operations-service itself
    # (core/marketplaces/salla.py, api/v1/salla.py), not a separate microservice: no new Secret
    # object, no RBAC Role change needed, the same reasoning PAYMENT_PUBLISHABLE_KEY's own entry
    # above already established for a third credential landing in this same object.
    SecretEntry(
        key="SALLA_CLIENT_ID",
        secret="operations-secrets",
        namespace="base-services",
        deployment="operations",
        label="معرّف تطبيق سلة (Client ID)",
    ),
    SecretEntry(
        key="SALLA_CLIENT_SECRET",
        secret="operations-secrets",
        namespace="base-services",
        deployment="operations",
        label="سر تطبيق سلة (Client Secret)",
    ),
    # HMAC-SHA256 key Salla signs every webhook call with — set ONCE for the whole app in the
    # Partners Portal's own webhook settings, never per merchant.
    SecretEntry(
        key="SALLA_WEBHOOK_SECRET",
        secret="operations-secrets",
        namespace="base-services",
        deployment="operations",
        label="سر التحقق من إشعارات سلة (Webhook Secret)",
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
