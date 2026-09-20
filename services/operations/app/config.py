# =============================================================================
# operations — Configuration (fail-fast, ZERO-HARDCODED)
# -----------------------------------------------------------------------------
# Every knob is an env var validated by Pydantic at boot. If a required value is
# missing or invalid, the process refuses to start (fail-fast). Defaults are
# safe: they reach NO external system until explicitly pointed at real infra.
# No hardcoded hosts/URLs/secrets/limits anywhere in the codebase — they all
# live here, sourced from the environment.
# =============================================================================
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Values come from env vars (or a local .env file)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── Identity ────────────────────────────────────────────────────────────
    SERVICE_NAME: str = "operations"
    SERVICE_VERSION: str = "0.1.0"
    ENV: Literal["development", "production", "test"] = "production"

    # ── HTTP server ─────────────────────────────────────────────────────────
    HOST: str = "0.0.0.0"  # noqa: S104 — bind address is operator-controlled config, not hardcoded exposure
    PORT: int = 8000

    # ── Logging ─────────────────────────────────────────────────────────────
    LOG_LEVEL: Literal["debug", "info", "warning", "error"] = "info"

    # ── Request hardening ───────────────────────────────────────────────────
    REQUEST_TIMEOUT_MS: int = 30_000
    BODY_LIMIT_BYTES: int = 1_048_576  # 1 MiB

    # ── Security headers ────────────────────────────────────────────────────
    # CSP frame-ancestors — who may embed this service's responses in a frame.
    ALLOWED_FRAME_ANCESTORS: str = "'none'"

    # ── CORS — who may call this service FROM A BROWSER ─────────────────────
    # Empty by default, and that default is a real choice rather than an omission: with no origins
    # configured no CORS headers are emitted at all, so a browser blocks every cross-origin call
    # and a server-to-server caller is unaffected. Opening a hole must be a decision somebody
    # typed, not the state a service arrives in.
    #
    # There was no CORS anywhere in this platform, which is invisible from a terminal and fatal
    # from a product: curl works, every fetch() from a client app or an operator panel is refused
    # by the browser before our code sees the request, and no server-side test catches it because
    # the rule is enforced in the browser.
    #
    # `*` IS REFUSED when credentials are allowed — the browser refuses that combination too, so
    # accepting it here would only move the failure somewhere harder to read. Serving the app and
    # the API from one origin remains the better answer where it is possible; this is for the
    # deployments where it is not.
    CORS_ALLOWED_ORIGINS: str = ""            # comma list of exact origins, e.g. https://app.example.com
    CORS_ALLOW_CREDENTIALS: bool = False      # cookies / Authorization on cross-origin calls
    CORS_ALLOWED_METHODS: str = "GET,POST,PUT,PATCH,DELETE,OPTIONS"
    CORS_ALLOWED_HEADERS: str = "authorization,content-type,x-request-id"
    CORS_MAX_AGE_SECONDS: int = 600           # how long a browser may cache the preflight

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ALLOWED_ORIGINS.split(",") if o.strip()]

    @property
    def cors_methods(self) -> list[str]:
        return [m.strip().upper() for m in self.CORS_ALLOWED_METHODS.split(",") if m.strip()]

    @property
    def cors_headers(self) -> list[str]:
        return [h.strip() for h in self.CORS_ALLOWED_HEADERS.split(",") if h.strip()]

    def assert_cors_config_ok(self) -> None:
        """Boot guard. A CORS policy that cannot mean what it says must not start.

        `*` with credentials is refused by every browser, so a service configured that way would
        serve headers that look permissive and work for nobody — the hardest kind of failure to
        diagnose, because the configuration and the symptom disagree.
        """
        if "*" in self.cors_origins and self.CORS_ALLOW_CREDENTIALS:
            raise ValueError(
                "CORS_ALLOWED_ORIGINS='*' with CORS_ALLOW_CREDENTIALS=true is refused by every "
                "browser, so this would emit headers that satisfy nothing. List the exact origins "
                "that need credentials.")
        if self.is_production and "*" in self.cors_origins:
            raise ValueError(
                "CORS_ALLOWED_ORIGINS='*' in production lets any site on the internet call this "
                "service with a user's browser. List the origins you actually serve.")

    # ── Operator-managed credentials (Phase 44) ─────────────────────────────
    # The key-encryption-key. Credentials an operator sets from the panel are sealed under this,
    # and it is settable through NO api: secrecy cannot be bootstrapped from a form, so if the key
    # protecting the secrets were itself editable in the panel, panel access would own everything.
    # Empty means the operator surface refuses to store anything rather than storing it unsealed.
    SECRETS_KEK: str = ""
    # Seals backup archives at rest. SEPARATE from SECRETS_KEK by design: restoring must not
    # require the key a running service uses for its own live secrets. Empty means this service
    # cannot produce a backup, and its export endpoint refuses rather than writing one in the clear.
    # SHARED: it must be the SAME value backup-service holds (in the class of PII_SALT /
    # INTERNAL_SERVICE_TOKEN); gen-secrets.py mints it consistently. Two different values and
    # the archives backup-service collects from this service cannot be opened.
    BACKUP_KEK: str = ""
    # The most rows a single collection may hold before a backup FAILS rather than reads on
    # unbounded. Not a limit anyone "chose" at a million — a real ceiling an operator sets to the
    # size their data actually reaches, so a runaway collection is a failed backup, not an OOM.
    BACKUP_MAX_ROWS_PER_COLLECTION: int = 5_000_000
    # How long a replaced credential stays valid. A request in flight when a key rotates must not
    # fail, and a mistaken paste needs a way back.
    SECRETS_ROTATION_WINDOW_SECONDS: int = 300

    # ── Internal service-to-service auth (REQUIRED) ─────────────────────────
    # Shared token for /internal/* endpoints. Must be strong (>= 32 chars).
    INTERNAL_SERVICE_TOKEN: str = Field(min_length=32)
    # job-service push-dispatch verification (app/core/push_verify.py) — empty means "verify
    # against INTERNAL_SERVICE_TOKEN instead", the SAME fallback job-service's own dispatcher uses
    # when ITS OWN PUSH_SIGNING_SECRET is unset, so the two sides agree by default with nothing
    # extra to configure.
    PUSH_SIGNING_SECRET: str = ""
    PUSH_SIGNATURE_MAX_SKEW_SECONDS: int = 300
    # Salts the subject pseudonym on an erasure ack. FROZEN — config/product.identifiers.lock.json.
    PII_SALT: str = ""
    ERASURE_MAX_SCAN: int = 100_000   # a DSAR is rare, but must never be an unbounded read

    # ── audit trail (Phase 38) — where privileged actions are witnessed ───────
    # `null` records NOTHING and says so; the boot guard below refuses it in production, because a
    # service that cannot witness its own privileged actions has no audit trail at all — and an
    # empty hash chain looks like a working control while answering nothing.
    AUDIT_SINK_DRIVER: str = "null"          # null | http | eventbus
    AUDIT_SERVICE_URL: str = ""              # e.g. http://audit-service:8000
    # OUR ingest path is a default, not an assumption about anyone else's platform — the same
    # reasoning as PRIVACY_ERASE_PATH. Nothing in the sink hardcodes it.
    AUDIT_INGEST_PATH: str = "/internal/audit"
    AUDIT_TOPIC: str = "audit.events"        # eventbus sink
    # Short on purpose: this sits on the request path, and a slow audit must not become a slow API.
    AUDIT_TIMEOUT_SECONDS: int = 5
    # How long a client should wait before retrying an action we REFUSED because the audit log
    # was unreachable. It is a 503 + Retry-After, never a 500: the action did not happen, nothing
    # committed, and trying again later is the correct response. A 500 would tell the caller we
    # crashed, which invites a bug report instead of a retry.
    AUDIT_RETRY_AFTER_SECONDS: int = 30

    # ── the message-template library — same pattern, same reason ──────────────
    # 69 templates across 23 types and five regulatory classes. In the datastore, edited from the
    # platform console at runtime; this file is the ONE-TIME seed applied to an empty table.
    #
    # The first version lived in a document, which meant changing a word cost a rebuild and a
    # rollout. That is not a library, it is a constant.
    TEMPLATES_SEED_FILE: str = ""
    # THE PLATFORM'S OWN TEMPLATES (tenant `_platform`) — a SEPARATE, much smaller file: these are
    # sent from our own WhatsApp number (subscription-renewal, low-AI-wallet-balance, ...), never
    # a shop's library. Registered automatically at boot (a local upsert, no Meta call — see
    # core/platform_templates.py), but NEVER submitted automatically: submitting is a live Meta
    # call and stays the operator's own "أرسل للمراجعة" click, by owner decision (2026-09-10).
    PLATFORM_TEMPLATES_SEED_FILE: str = ""

    # ── search — how a customer becomes findable ──────────────────────────────
    # `null` indexes nothing and SAYS so. Correct for tests; refused in production by the boot
    # guard below, because a screen that silently cannot find anybody is the single worst thing
    # this product can do to an operator with a customer standing in front of him.
    SEARCH_DRIVER: str = "null"              # null | http
    SEARCH_SERVICE_URL: str = ""             # e.g. http://search-service:8000
    # THEIRS, so it is a default rather than an assumption about another platform's routing.
    SEARCH_INDEX_PATH: str = "/internal/search/index"
    SEARCH_INDEX_NAME: str = "customers"
    # The READING half, and it is two paths because the peer answers two different questions:
    # a prefix returns TERMS and a whole token returns PEOPLE (ط-3).
    #
    # INTERNAL, NOT THE PUBLIC ROUTE — the public one demands a signed Bearer token, and this
    # service holds no signing key to make one (that key stays with identity-service alone). Every
    # call through the old /api/v1/search/... defaults answered 401, silently, for as long as this
    # config existed: the keypad showed nothing typed past three digits, and nothing here failed
    # loudly enough to say why. search-service now carries an internal twin of both routes for
    # exactly this (platform/, escalated and fixed 2026-08-19 — repin once the next platform
    # release tags it).
    SEARCH_SUGGEST_PATH: str = "/internal/search/suggest"
    SEARCH_QUERY_PATH: str = "/internal/search/query"
    # Short, and it runs after the response anyway — a slow index must never hold a worker.
    SEARCH_TIMEOUT_SECONDS: int = 5

    # THE MOST VISIT ROWS ONE READ MAY CARRY — and it is the SAME NUMBER insights asks for.
    #
    # It was `le=1000`, written straight into the route's request model, while insights asked for
    # `SNAPSHOT_VISIT_LIMIT: 5000`. Neither number was wrong on its own: 5000 is what ninety-day
    # indicators need on a busy shop, 1000 is what one response may comfortably hold. Nothing had
    # ever compared them, so every snapshot computation was refused 422 before it reached any
    # logic — the dashboard was never computed for any establishment, and the owner's «حدّث الآن»
    # answered 500.
    #
    # DECLARED HERE RATHER THAN INLINE so there is one place to change and one place to read, and
    # paired with insights' own name in `ci/check_paired_config.py`: two processes cannot share a
    # variable, and a gate that fails the build the day they differ is the closest honest thing.
    VISITS_PAGE_MAX: int = 5000

    # ── consent gate — ask before processing personal data ────────────────────
    # compliance-service served consent-check with ZERO callers for four phases: the control was
    # built and nothing consulted it. `null` answers UNKNOWN (never ALLOWED — a gate that invented
    # permission would be worse than no gate), and each call site declares what to do with that.
    # ── seats and branches, as gauges ─────────────────────────────────────────
    # A GAUGE IS REPORTED, NEVER INCREMENTED. It is the current value of something owned HERE —
    # how many employees exist right now — and it goes down as well as up. Increment it and a
    # deleted employee never gives the seat back, and the drift is invisible until somebody
    # cannot add a person they can see they have room for.
    GAUGE_DRIVER: str = "null"               # null | http
    BILLING_SERVICE_URL: str = ""            # e.g. http://billing-service:8000
    BILLING_USAGE_SET_PATH: str = "/internal/billing/usage/set"
    BILLING_CHECK_PATH: str = "/internal/billing/entitlements/check"
    # billing v0.24.1's read-only "who renews soon, across every tenant" scan — see
    # core/renewal_heads_up.py. Never used for invoicing; that stays exactly where it already is.
    BILLING_RENEWING_SOON_PATH: str = "/internal/billing/subscriptions/renewing-soon"
    # 2 days ahead, the owner's own instruction (2026-09-15).
    RENEWAL_HEADS_UP_WITHIN_SECONDS: int = 2 * 24 * 3600
    WHATSAPP_ASSISTANT_SERVICE_URL: str = ""  # e.g. http://whatsapp-assistant:8000
    WHATSAPP_UPCOMING_RENEWAL_TRIGGER_PATH: str = "/internal/whatsapp/upcoming-renewal/trigger"
    # Full Meta Business Agent onboarding, fired once right after a number connects — see
    # services/whatsapp-assistant/app/core/meta_agent_provisioning.py for the 7-step sequence.
    # OFF by default (that service's own META_AGENT_PROVISIONING_ENABLED gate decides whether the
    # call does anything real; this side just needs somewhere real to send it).
    WHATSAPP_META_AGENT_PROVISION_PATH: str = "/internal/whatsapp/meta-agent/provision"
    # The on/off switch for a number ALREADY onboarded -- see meta_agent_rollout_trigger.py's own
    # docstring. Fired by the AI kill switch (staff.py::set_ai_toggle) and by the entitlement sweep
    # below, never a re-run of provisioning.
    WHATSAPP_META_AGENT_ROLLOUT_PATH: str = "/internal/whatsapp/meta-agent/rollout"

    # ── the programmatic link (`feature.api`) — CLOSED by product decision, 2026-09-16 ────────
    # The owner's own call: rather than sell it (a new price/plan row) or bundle it free into every
    # app (a marketing decision nobody had made yet), the till/POS door stays shut for everyone,
    # unconditionally, until a real decision reopens it. `core/licence.py::build_api_licence`
    # refuses every machine write while this is false — it never asks billing at all, so no plan
    # can accidentally grant what nobody has priced. Flip to true (and price it in
    # deploy/seed/plans.json) to reopen the door with no code change beyond that.
    API_LINK_ENABLED: bool = False

    # ── our own subscribe path (§6.2.1) ───────────────────────────────────────
    # The one product rule billing must never learn: no PAID subscription before WhatsApp is
    # connected. The trial is exempt — it is for trying, and most of the product works without a
    # connection at all. And it is the CONNECTION (minutes) rather than Meta's business
    # VERIFICATION (days, and not required to send).
    BILLING_PLANS_DRIVER: str = "null"       # null | http
    # THE INTERNAL TWINS, ADDED IN PLATFORM v0.16.12 AT OUR ESCALATION.
    #
    # These two were the last user-tier routes any service of ours called. The user tier rate
    # limits per caller; this service presents only X-Internal-Token and cannot mint a bearer (the
    # signing key lives in identity-service and stays there), so the limiter had no subject and
    # keyed on the IP it could see — THIS POD'S. Every establishment on the fleet shared one
    # bucket, and past it billing answered 429 on the purchase path, which is the one path that
    # must fail closed: our own code could not tell that 429 from «you already hold this plan».
    #
    # Raising the number was never the fix — a limit tuned for one pod is wrong at the next
    # customer. `tenant` rides in the body and the query exactly as it already did, so the shape
    # this service sends did not change; only the door it knocks on.
    BILLING_PLANS_PATH: str = "/internal/billing/plans"
    BILLING_SUBSCRIBE_PATH: str = "/internal/billing/subscriptions"
    # WHAT THIS SHOP HOLDS — the internal, token-authed list (base-services v0.16.7). It is the
    # same billable set the entitlement resolver computes over, so the purchase rules and the
    # gates in every service can never disagree about what was bought.
    BILLING_SUBSCRIPTIONS_PATH: str = "/internal/billing/subscriptions"
    # SHOP-TO-SHOP COUPONS (base-services v0.23.0) — a narrow internal-tier pair, neither of
    # which touches `platform.billing`: create ONE coupon row (base URL below the "subscriptions"
    # one, same rstrip pattern as everywhere else) and attach a coupon code to an EXISTING
    # subscription. See `core/coupons.py`'s own module docstring for the full design.
    BILLING_COUPON_CREATE_PATH: str = "/internal/billing/coupons"

    # ── the payment gateway, as the SCREEN needs to know it ───────────────────────────────────
    #
    # ONE KEY IS THE WHOLE SWITCH. Empty means no gateway is live, and the plans screen says so in
    # a sentence instead of handing out paid tiers to whoever presses hardest. Filled means the
    # card form appears and the subscription waits for a real charge. No code change, no rebuild:
    # put the key in the secret and the product starts selling.
    #
    # PUBLISHABLE BY DESIGN. This is the key the gateway means to be read by a browser — it can
    # create a token and nothing else. The SECRET key lives in billing-service and is never here,
    # never in the console, and never in a response.
    PAYMENT_PUBLISHABLE_KEY: str = ""
    PAYMENT_PROVIDER: str = "moyasar"

    # ── Salla (marketplace app — shop-to-shop alliances from a real Salla order) ────────────────
    # SET FROM THE PARTNERS PORTAL, THROUGH secrets-admin — never typed here. A shop owner
    # registers the app at portal.salla.partners, pastes the three values this app gives him into
    # the secrets screen (same posture as every other external credential — see
    # secrets-admin/app/core/secret_registry.py's own module docstring). Empty means the Salla
    # integration simply answers "not configured" rather than failing — same posture
    # PAYMENT_PUBLISHABLE_KEY's own comment above documents for an unconfigured gateway.
    SALLA_CLIENT_ID: str = ""
    SALLA_CLIENT_SECRET: str = ""
    # HMAC-SHA256 key Salla signs every webhook call with (`X-Salla-Signature` header) — set ONCE
    # for the whole app in the Partners Portal's own webhook settings, not per merchant. Verified
    # in core/marketplaces/salla.py::verify_signature.
    SALLA_WEBHOOK_SECRET: str = ""

    # job-service — the platform's own durable scheduler (adapters/job_service.py). Empty means
    # NullJobService, same posture as every other optional peer URL in this file: the refresh
    # scan simply finds nothing to enqueue rather than crashing.
    JOB_SERVICE_URL: str = ""                # e.g. http://job-service:8000

    # ── shop-content translation (phase 3 — core/translation_engine.py) ────────────────────────
    # "null" — the honest default until a deployment actually seals a model in place. "nllb200"
    # loads a local, quantized NLLB-200 model via ctranslate2 (never a cloud API — see
    # [[task-catalog-translation-phases]] memory for why: a shop's service names and procedure
    # text stay on this box). Empty paths under "nllb200" refuse at first use, not at boot — a
    # deployment with the driver flipped on before the model files are actually staged must not
    # crash startup for every OTHER route this service serves.
    TRANSLATION_ENGINE_DRIVER: str = "null"     # null | nllb200
    TRANSLATION_MODEL_PATH: str = ""            # ctranslate2 model directory (model.bin, config)
    TRANSLATION_SP_MODEL_PATH: str = ""         # the shared sentencepiece.bpe.model file
    # THE FRACTION OF CPU COUNT `core/server_load.py::is_idle` refuses above — see that module's
    # own docstring for why this is a fraction, not a raw load number.
    TRANSLATION_LOAD_THRESHOLD: float = 0.7
    # Whether a shop has a WhatsApp account, ASKED of notification-service rather than stored: a
    # copy here is a second answer to the same question, and the first disagreement refuses a
    # subscription from a shop that connected an hour ago.
    CONNECTIONS_DRIVER: str = "null"         # null | http

    # ── the door (§16.5) ──────────────────────────────────────────────────────
    # Signing up creates a TENANT and registers its owner, which no platform service does on its
    # own: identity registers a user INTO a tenant, tenant-service creates a tenant for an
    # internal caller, and deciding that those two together mean "a new establishment" is a
    # product rule. Empty URLs disable both routes rather than half-creating anything.
    # WHO DECIDES WHICH OFFER A VISIT APPLIES. We record the spend on the visit (§5.6.2); only
    # reminders knows what was sent, with what scope and expiry. Empty = the tap refuses rather
    # than guesses, which is the safe direction for money.
    REMINDERS_SERVICE_URL: str = ""          # e.g. http://reminders:8000
    # THE EVIDENCE FILE'S OTHER HALF (task 283): consent transitions and the send log, read from
    # the service that writes them. A copy of either here would be evidence about our copy.
    REMINDERS_EVIDENCE_PATH: str = "/internal/reminders/evidence"
    COMPLIANCE_SERVICE_URL: str = ""         # e.g. http://compliance-service:8000
    # THE ONE QUESTION ASKED OF `bookings`: the shop's own working hours, so a staff member's
    # custom hours can be refused at write time if they reach outside them. Empty means this
    # write-time check is simply skipped (bookings intersects defensively at read time regardless
    # — this is belt, not the only suspender) rather than every staff-hours edit failing closed on
    # a peer that may not be configured in every environment.
    BOOKINGS_SERVICE_URL: str = ""           # e.g. http://bookings:8000
    BOOKINGS_WORKING_HOURS_PATH: str = "/internal/working-hours"
    # WHERE A SHOP'S DATA LIVES, as "service:category" pairs, registered at signup so a DSAR has
    # somewhere to go. Config and not code: a service deployed next month must not need a release
    # of the signup saga, and a deployment that omits one can be seen in one place.
    TENANT_DATA_MAP: str = ""
    IDENTITY_SERVICE_URL: str = ""           # e.g. http://identity-service:8000
    # OUR OWN MACHINE CREDENTIAL AT BILLING, held for one purpose: reading what every shop paid,
    # so a partner's commission can be computed on money that actually arrived. It exists because
    # billing publishes that list on the admin tier rather than the internal one — ESCALATED, and
    # the day an internal aggregate exists these two go away with it.
    BILLING_CLIENT_ID: str = ""
    BILLING_CLIENT_SECRET: str = ""
    TENANT_SERVICE_URL: str = ""             # e.g. http://tenant-service:8000
    SIGNUP_TIMEOUT_SECONDS: int = 10
    # Saudi Arabia, and it MUST match identity's IDENTITY_PHONE_DEFAULT_CC. Our phone index folds
    # numbers to E.164 the same way identity does; two different country codes would produce an
    # index that disagrees with the platform's uniqueness rule, and the account would exist while
    # the login said it did not.
    SIGNUP_PHONE_DEFAULT_CC: str = "966"
    # CAN A CODE ACTUALLY REACH A PHONE TODAY? Declared here because it is OUR deployment fact,
    # and because nothing downstream will tell us the truth: notification-service's `console`
    # driver writes a log line and returns True, so identity answers `delivered: true` and every
    # layer reports success while no message exists. A chain of honest components can still add up
    # to a lie, and the only place that knows is the one that chose the driver — us.
    #
    # FALSE means the signup path says so plainly instead of parking a person on a code screen for
    # a message nobody sent. Flipped to true in the same change that points notification-service at
    # Meta, and a CI check keeps the two in step.
    SIGNUP_OTP_DELIVERABLE: bool = False
    # IS PROVING THE NUMBER A CONDITION OF ENTRY? Separate from whether a code CAN be delivered,
    # and the two are checked together by a CI gate: requiring a proof we cannot send is a locked
    # door with no key, which is what it was until this knob existed.
    #
    # FALSE IS NOT "NO PROOF" — it is proof DEFERRED. The number is still recorded unverified, the
    # screen still offers to confirm it, and «حسابي» still says it is unconfirmed. What changes is
    # that it no longer stands between a person and his own shop. And the cost is real and worth
    # naming: an unproven number is one a reminder may never reach, so this is a launch-phase
    # setting rather than a preference.
    SIGNUP_REQUIRE_OTP: bool = True
    # ── the roles a new establishment is born with ────────────────────────────────────────
    # Posted to authz's internal bootstrap during the signup saga. Without it the owner's token
    # carries `caps: []` and he signs in to an empty application — every response a 2xx, and
    # nothing anywhere reporting a fault. See core/signup.py.
    AUTHZ_SERVICE_URL: str = ""              # e.g. http://authz-service:8000
    # Where redemptions and points live. Nothing is seeded into it — a rewards table guessed
    # from a trade we have never seen was wrong for most shops, so the owner writes his own.
    # Empty means a shop starts with no rewards — a missing table rather than a failed signup,
    # which is the right trade for a peer that may not be deployed.
    LOYALTY_SERVICE_URL: str = ""            # e.g. http://loyalty:8000
    # WHO BROUGHT THIS SHOP — the affiliate portal's own attribution, deliberately separate from
    # PartnerRegistry/partner_key just above: a marketer earns a flat amount on an identity-
    # authenticated account, a till partner earns a percentage on a bearer key. See
    # affiliate-service/app/core/referrals.py for the whole reasoning. Optional, like LOYALTY_
    # SERVICE_URL above it: a signup with no affiliate_ref never calls this at all, and a
    # deployment without the affiliate portal simply never sets it.
    AFFILIATE_SERVICE_URL: str = ""          # e.g. http://affiliate-service:8000
    # WHO BROUGHT THIS SHOP MAY ALSO SEE ITS SUPPORT PERFORMANCE — spec §13's own consent: at
    # signup, a shop that came through a marketer's link grants that SAME marketer a scoped,
    # revocable read (and, once ticket-service ships write access, reply) over its tickets —
    # ticket-service's own ShareGrant (v0.16.27+), never a blanket cross-tenant capability.
    # Blank means "not wired" — TICKET_SERVICE_URL empty is a silent no-op, same trade as
    # LOYALTY_SERVICE_URL/AFFILIATE_SERVICE_URL above it.
    TICKET_SERVICE_URL: str = ""             # e.g. http://ticket-service:8000
    # WHICH TICKET TYPES a referring marketer's grant covers — spec §13's own reasoning: a
    # marketer pulling from the same pool as trained technical support staff would get authority
    # to resolve tickets he has no training for. Comma-separated ticket `type` values; BLANK
    # means no restriction (every type) — a deployment should set this explicitly to exclude
    # technical/complex categories before relying on it; the empty default is honest about "not
    # yet decided", never a silent safe assumption.
    AFFILIATE_TICKET_SCOPE_TYPES: str = ""
    # SHIPPED IN THE IMAGE, like the template seed, so a signup at three in the
    # morning needs nobody present. Read once per signup; after that authz owns the roles and the
    # owner edits them from the console.
    SIGNUP_ROLES_FILE: str = ""              # e.g. /app/data/roles.seed.json
    # Which of those roles the registrant is given. Named rather than assumed to be the first in
    # the file: a reordering of a JSON array must not decide who owns a shop.
    SIGNUP_OWNER_ROLE: str = "owner"
    NOTIFICATION_SERVICE_URL: str = ""       # e.g. http://notification-service:8000
    NOTIFICATION_MESSAGING_LIMIT_PATH: str = "/internal/whatsapp/messaging-limit"
    # WHERE WE ASK WHAT META DECIDED. Empty disables the sweep entirely rather than pointing it at
    # a guessed path — a sweep that 404s on every shop reports failures that look like Meta's.
    NOTIFICATION_TEMPLATE_SYNC_PATH: str = "/internal/whatsapp/templates/sync"
    # PUTTING THE LIBRARY WHERE META CAN APPROVE IT — the internal twins added in base-services
    # v0.16.6 in answer to our escalation. `register` is a local upsert with no Meta call and no
    # cap; `drain` hands over what has never been submitted, inside Meta's 100/hour.
    NOTIFICATION_TEMPLATE_REGISTER_PATH: str = "/internal/whatsapp/templates"
    NOTIFICATION_TEMPLATE_DRAIN_PATH: str = "/internal/whatsapp/templates/submit-pending"
    # SAME ROUTE AS REGISTER, DIFFERENT VERB — GET lists, POST registers (notification-service's
    # own /internal/whatsapp/templates). Read once at startup to seed the platform's OWN templates
    # without ever re-registering (and so reverting) one an operator has since edited — see
    # core/platform_templates.py's own docstring.
    NOTIFICATION_TEMPLATE_LIST_PATH: str = "/internal/whatsapp/templates"
    # The one-time placeholder-image upload a carousel template's cards need at creation — see
    # app/core/library.py's own note on why this is never a static, pre-baked handle.
    NOTIFICATION_MEDIA_UPLOAD_HANDLE_PATH: str = "/internal/whatsapp/media/upload-handle"
    # GIVING A SHOP ITS OWN COPY OF THE RATING FLOW (base-services v0.18.26's flow-provisioning
    # twin) — see core/flows.py. Idempotent by name on notification-service's own side, same as
    # the template register above.
    WHATSAPP_FLOW_PROVISION_PATH: str = "/internal/whatsapp/flows/provision"
    # THE FLOW'S OTHER connect-time STEP (Phase 5, base-services v0.18.55) — ensures a sealed
    # per-tenant Flow-encryption key exists and its public half is registered with Meta. See
    # core/flows.py's `HttpFlows.ensure_encryption`.
    WHATSAPP_FLOW_ENCRYPTION_ENSURE_PATH: str = "/internal/whatsapp/flow-encryption/ensure"
    # THE MASTER FLOW'S id, minted ONCE by each Flow's own deploy/seed/bootstrap-*-flow.sh under
    # the platform's own WABA and stored through THIS SETTING'S RuntimeConfig override (platform
    # scope, tenant="") — never a static default, because the id does not exist until that
    # script has run. Read at connect time through RuntimeConfig, not this field directly, so a
    # fresh install needs no redeploy once the bootstrap script has written it.
    #
    # RATING AND REPORT FLOWS BOTH REMOVED (2026-09-16) — `MASTER_RATING_FLOW_ID`/
    # `MASTER_REPORT_FLOW_ID` used to sit here; see core/flows.py's own module docstring for why
    # (the rating screen moved off native Flow entirely; the report Flow's template was already
    # deleted 2026-09-13 and this was orphaned config left behind by that same deletion).
    MASTER_BOOKING_FLOW_ID: str = ""
    # THE SAME PATTERN, ANOTHER REMAINING FLOW — subscription renewal (deploy/seed/
    # subscription-renewal-flow.json), minted once by
    # deploy/seed/bootstrap-subscription-renewal-flow.sh. See `MASTER_BOOKING_FLOW_ID`'s own
    # comment above; DYNAMIC like booking (needs its own endpoint_uri at connect time, below).
    MASTER_SUBSCRIPTION_RENEWAL_FLOW_ID: str = ""
    # WHERE META CALLS BACK — unlike a static Flow (no server round-trip ever needed), the booking
    # Flow is DYNAMIC and MUST tell Meta a real endpoint per shop's own clone
    # (notification-service's `/webhooks/whatsapp/flow/{tenant}` resolves which shop's sealed key
    # to decrypt with FROM this URL — a clone with no endpoint_uri, or the wrong tenant's, can
    # never receive real traffic). Same "set from DOMAIN at install time, never guessed" posture
    # as reminders' own PUBLIC_BASE_URL — empty here means booking-Flow provisioning simply omits
    # endpoint_uri (Meta then refuses/ignores actual traffic, but the clone itself still succeeds,
    # so a shop connecting before DOMAIN is set is not blocked, only inert until it is).
    PUBLIC_BASE_URL: str = ""                # e.g. https://raje3.sa
    # How many establishments one sweep pass reconciles. A repair pass that runs again in an hour:
    # progress beats completeness, and a fleet-wide scan on one request is a request that times out.
    TEMPLATE_SYNC_MAX_TENANTS: int = 200
    PEER_TIMEOUT_SECONDS: int = 8

    # WhatsApp connection (Embedded Signup). The exchange itself belongs to notification-service,
    # which holds the Tech Provider secret and never lets the shop's token reach a route. What is
    # named here is only how we hand the code over.
    #
    # `null` UNTIL THERE IS A ROUTE WE CAN REACH. The exchange endpoint that exists requires a
    # platform capability the shop owner does not and must not hold, and no internal variant exists;
    # escalated. Null answers "not configured" honestly rather than reporting a connection that did
    # not happen — the failure that would have a shop recording visits all week and wondering where
    # its messages went.
    WHATSAPP_ONBOARDING_DRIVER: str = "null"     # null | http
    WHATSAPP_ONBOARDING_PATH: str = "/internal/whatsapp/embedded-signup"
    # ── WHAT THE CONSOLE NEEDS TO EVEN OPEN THE POPUP — GET /whatsapp/config (this service's own
    # route). Meta's App ID and Facebook Login Config ID are not secret (both travel from the
    # BROWSER to Meta's own JS SDK in the clear on every popup open already); they are sealed
    # through secrets-admin anyway so an operator sets them from one panel with no console
    # rebuild — see notification-service's own settings for where the sealed values actually
    # live, and this route's own docstring for why it asks THERE rather than holding a copy.
    WHATSAPP_META_CONFIG_PATH: str = "/internal/whatsapp/config"
    # ── THE STEP THE EXCHANGE STOPS BEFORE (base-services v0.16.10) ──────────────────────────
    # Meta refuses to SEND from a number until it is registered (error 133010), so a connection
    # that stops at the token exchange is «مربوط» and mute — this product's signature failure,
    # and the reason we escalated it. Registration is PER NUMBER, which is what a number per
    # branch needs.
    WHATSAPP_REGISTER_PATH: str = "/internal/whatsapp/register"
    # And the number's REAL readiness, read live from Meta: `code_verification_status` answers
    # «can this shop actually send» instead of a screen assuming it from a successful exchange.
    WHATSAPP_STATUS_PATH: str = "/internal/whatsapp/status"

    # ── retention (§14.5) ─────────────────────────────────────────────────────
    # HOW LONG A PERSON'S NUMBER IS KEPT. Two clocks, and neither is a constant in code:
    # the customer's is the ESTABLISHMENT'S to shorten (core/retention.py reads it per tenant
    # through RuntimeConfig); these are the ceiling and the default it starts from.
    #
    # Generous on purpose. A customer away three years is exactly what the return engine exists
    # to bring back — deleting him for being absent would delete the product's raw material.
    RETENTION_CUSTOMER_YEARS: int = 5
    # OURS: how long a departed establishment's data waits for it. Deleting a shop's history is
    # exactly what a competitor needs in order to take it (§16.4.2), and a shop that finds its
    # data waiting comes back.
    RETENTION_LAPSED_YEARS: int = 2
    # The entitlement the sweep asks about to tell "still with us" from "left". Named here rather
    # than in code because it is billing's key, not ours, and a rename there is a config change.
    RETENTION_ENTITLEMENT_KEY: str = ""      # empty → the sweep starts no lapse clock at all
    # How many customer rows one nightly pass may read. A whole-collection read is deliberate here
    # (it is a cron, not a request path) but it is still bounded: the cap is the difference
    # between a slow night and an outage on the one tenant large enough to cause it.
    RETENTION_SCAN_CAP: int = 20_000

    # ── wallet top-up reconciliation (v0.18.44's hosted-checkout top-up has no signed webhook) ──
    # billing-service's own listing/reconcile routes — path templates, not full URLs, joined onto
    # BILLING_SERVICE_URL. BOTH ARE platform.billing (ADMIN tier, confirmed v0.18.45), same as
    # the invoice list settlements.py already reads — so this reuses BILLING_CLIENT_ID/
    # BILLING_CLIENT_SECRET/IDENTITY_SERVICE_URL above rather than the internal token.
    BILLING_WALLET_TOPUPS_PENDING_PATH: str = "/api/v1/billing/admin/wallet-topups/pending"
    BILLING_WALLET_TOPUP_RECONCILE_PATH: str = "/api/v1/billing/payments/{payment_id}/reconcile"
    # How many pending payments one sweep may take, and how fresh one may be before it is worth
    # asking about — a payment opened seconds ago is almost never done yet, and asking anyway is a
    # wasted round trip on every single sweep of every single top-up.
    WALLET_TOPUP_RECONCILE_LIMIT: int = 50
    WALLET_TOPUP_RECONCILE_OLDER_THAN_SECONDS: int = 90

    # How far back a claimed visit time may be before it is a broken clock rather than a backlog.
    # A shop migrating a year of its own history legitimately needs more than the default, and a
    # release is the wrong way to give it to them.
    # ── branch modes ──────────────────────────────────────────────────────────────────────────
    # OFF UNTIL THE SENDING IDENTITY EXISTS. Per-branch numbers need credentials keyed by number
    # rather than by establishment; until then this deployment can only honour `central`, and the
    # screen says so instead of offering a switch that changes nothing.
    #
    # WHAT IS PROVEN, so the next reader does not re-audit the whole chain (#386): the derivation
    # that decides which number a message leaves from is pinned by
    # `reminders/tests/unit/test_the_branch_decides_which_number_sends.py`, and
    # `ci/check_every_send_says_which_number_it_leaves_from.py` refuses a send site that omits it
    # — it found one the day it was written. What is NOT proven is the last seam: that the
    # sender's credential lookup resolves `tenant:branch` to that branch's own registered Meta
    # number. That needs two registered numbers (#167). This flag turns on after that ONE check,
    # not after a chain nobody has walked.
    BRANCH_MODE_PER_BRANCH_READY: bool = False

    # ── the shared-tablet employee ────────────────────────────────────────────────────────────
    # OFF, AND KEPT WHOLE. «رمز على الجهاز» adds a person with four digits instead of a login: he
    # proves himself at «من يحفظ؟» and the visit carries his name. It is built end to end — the
    # form, `create_operator`, `verify-pin`, the five-minute proof — and it is not what this
    # product is being sold on today: every employee gets an account on his own phone.
    #
    # SWITCHED OFF RATHER THAN DELETED, on purpose. Deleting a working path costs a rewrite the day
    # a shop with one counter tablet asks for it; leaving it visible costs every owner a choice he
    # does not need and a second credential to manage. So it stays complete and unreachable, and
    # this line is the whole of the decision.
    #
    # AND IT IS ENFORCED AT THE DOOR, not only in the screen: `create_operator` refuses while this
    # is false. A capability hidden by the console alone is a capability, and this file would then
    # be describing a wish.
    PIN_OPERATORS_ENABLED: bool = False

    # THE KILL SWITCH for selling any plan marked `plan.standalone` (core/subscribe.py::may_add,
    # is_standalone) WITHOUT الأساس underneath it — e.g. "واتساب الذكي (مستقل)". False makes
    # may_add demand a base for those plans too, same as every other app; existing standalone
    # subscribers are unaffected, only NEW purchases are refused while it is off.
    STANDALONE_PLANS_ENABLED: bool = True

    # THE FULL KILL SWITCH for shop-owner AI-assistant notes (app/core/ai_notes.py). False means
    # the field always reads back empty — GET, PUT, and the internal peer route whatsapp-assistant
    # calls — regardless of what is stored. The stored text is NOT erased when this is off: turning
    # it back on returns exactly what was there before, so this is a behaviour switch, never a
    # data-loss one. Enforced at every route that touches the field, not only hidden from the
    # console — a capability hidden by the console alone is a capability, and this line would then
    # be describing a wish.
    AI_NOTES_ENABLED: bool = True

    # THE FULL KILL SWITCH for the per-shop customer-message word limit (app/core/msg_limits.py).
    # False means the internal peer route always answers `DEFAULT_MSG_WORD_LIMIT`, and the owner's
    # own GET/PUT read/refuse the same way `AI_NOTES_ENABLED` does above — the stored value is not
    # erased, only ignored while this is off.
    MSG_WORD_LIMIT_ENABLED: bool = True

    MAX_BACKDATE_SECONDS: int = 7_776_000

    CONSENT_GATE_DRIVER: str = "null"        # null | http
    COMPLIANCE_SERVICE_URL: str = ""         # e.g. http://compliance-service:8000
    # THEIR path, so it is a default rather than an assumption about another platform's routing.
    CONSENT_CHECK_PATH: str = "/internal/compliance/consent-check"
    # Short: this sits on a request path, and a slow consent question must not become a slow API.
    CONSENT_TIMEOUT_SECONDS: int = 3
    # Does this service process personal data for a declared purpose? Set by the SERVICE, not the
    # deployment — it is a fact about what the code does, and an operator should not be able to
    # switch off a control by editing an env var. It exists so the boot guard below can tell
    # "this service has no consent-gated processing" from "somebody forgot to configure the gate",
    # which are indistinguishable from the driver alone and were exactly how the gap survived.
    CONSENT_GATED: bool = False
    # What happens when a CRITICAL action cannot be witnessed. Default closed: an action nobody can
    # prove is worse than a refused one for the actions investigations actually turn on (permission
    # grants, credential changes, exports, suspensions). Routine actions always fail open — the
    # split is per action, declared by each service, not a global switch.
    #
    # Turning this off is a deliberate availability-over-evidence trade. It is config so an operator
    # CAN make it during an audit outage, and it is documented so nobody makes it by accident.
    AUDIT_FAIL_CLOSED: bool = True

    # ── Ports & adapters (Phase 2) — driver selection, ZERO-INFRA defaults ──
    # Every default reaches NO external system; point at real infra by config.
    DATASTORE_DRIVER: str = "memory"
    DATASTORE_DSN: str = ""  # e.g. postgresql://user:pass@host/db  (postgres driver)
    # ── Postgres connection pool ──────────────────────────────────────────────────────────────
    # asyncpg's default pool is min_size=10, max_size=10, and min is a LAZY-but-STICKY floor: the
    # pool fills to it on first use and holds there for the process lifetime. Left at the default,
    # 24 services each pin 10 backend connections — 240 against a single postgres whose stock ceiling
    # is 100 — and the fleet deadlocks on an ordinary request once enough services have been touched
    # (with maxUnavailable:0, a rollout deadlocks outright: a new pod needs its 10 slots to go Ready
    # while the old pod still holds its 10). So the floor is 1: a pod is Ready on one connection, an
    # idle service costs one, and horizontal scale spends the ceiling deliberately, not by default.
    DATASTORE_POOL_MIN: int = 1
    DATASTORE_POOL_MAX: int = 5
    DATASTORE_POOL_TIMEOUT_SECONDS: float = 10.0            # wait for a free slot, then fail cleanly
    DATASTORE_POOL_MAX_INACTIVE_LIFETIME_SECONDS: float = 300.0  # return idle connections to postgres
    DATASTORE_STATEMENT_CACHE_SIZE: int = 0   # 0 => PgBouncer transaction-mode safe (no asyncpg prepared-statement cache)

    # ── the phone-search DB role (app/adapters/datastore/phone_search_ro.py) ────────────────────
    # A SECOND, DELIBERATELY WEAKER, POSTGRES ROLE — the first of its kind on this platform (every
    # other service, and every other query in THIS service, uses the one role gen-secrets mints;
    # see ci/check_a_deploy_script_does_not_invent_a_postgres_role.py's own history for why a
    # second role is not introduced lightly here). This one exists for exactly one query: the
    # human-driven `GET /customers/by-phone` search screen — the one read an insider can abuse
    # (checking a number out of curiosity, or probing whether someone is a customer at all,
    # discussed and audited this session — see customer.searched_by_phone in auditable_actions.py).
    #
    # WHY A SEPARATE ROLE AND NOT JUST THE AUDIT ROW ABOVE. The audit trail proves who searched and
    # when, AFTER the fact — real, but it does not shrink what a compromised app process (a bug, an
    # injected query, a stolen service credential) can read in the meantime. This role can. It has
    # SELECT on ONE VIEW (`customers_phone_search_v`, provisioned by
    # deploy/hooks/provision-phone-search-role.sh) exposing only `tenant, phone, key` for
    # `collection='customers'` rows — not the base `kv_store` table every other collection
    # (visits, branches, operators, everything) shares, and not even a customer's own name or
    # subject_ref. A phone search under this role, worst case, can only ever answer "does a phone
    # number exist" — nothing else in this database is reachable with it.
    #
    # EMPTY IS THE SAFE DEFAULT, same convention as every other optional wire in this service: with
    # this unset, `customer_by_phone_searched()` below falls back to the exact same single-role
    # lookup this screen has always used — no regression, no crash, just no extra isolation until
    # the role is actually provisioned and this DSN is set.
    DATASTORE_DSN_PHONE_SEARCH: str = ""

    CACHE_DRIVER: str = "memory"
    CACHE_URL: str = ""  # e.g. redis://host:6379/0  (redis driver)

    EVENTBUS_DRIVER: str = "memory"
    EVENTBUS_URL: str = ""

    QUEUE_DRIVER: str = "memory"
    QUEUE_URL: str = ""

    OBJECTSTORE_DRIVER: str = "local"
    # nosec B108 — /tmp is where the chart mounts a WRITABLE volume under readOnlyRootFilesystem;
    # this is the object store's data dir, not an insecure shared-temp file. Production uses s3.
    OBJECTSTORE_ROOT: str = "/tmp/objectstore"  # nosec B108
    OBJECTSTORE_BUCKET: str = ""  # s3 driver
    OBJECTSTORE_ENDPOINT_URL: str = ""  # s3-compatible endpoint (config allowlist)
    # Any S3-compatible store — AWS S3, MinIO, or a Saudi cloud's object storage. There is no
    # separate "minio driver": MinIO speaks S3, so it IS the s3 driver, pointed at your endpoint.
    #
    # Leave the keys EMPTY on AWS to use the ambient chain (IAM role / instance profile) — that is
    # strictly safer than static keys, so it stays the default. Set them for MinIO or anywhere the
    # ambient chain does not exist.
    OBJECTSTORE_ACCESS_KEY: str = ""
    OBJECTSTORE_SECRET_KEY: str = ""
    OBJECTSTORE_REGION: str = ""          # boto refuses to sign without one; MinIO ignores it
    # THE MINIO KNOB. Boto defaults to virtual-host addressing (https://bucket.host/key), which
    # needs a wildcard DNS record. MinIO and most on-prem stores serve path-style
    # (https://host/bucket/key) and simply fail to resolve otherwise.
    OBJECTSTORE_FORCE_PATH_STYLE: bool = False

    SECRETS_DRIVER: str = "env"
    SECRETS_FILE: str = ""  # file driver: path to a KEY=VALUE file

    # Token verifier — 'null' denies all (deny-by-default) until a real driver +
    # key is configured. Prefer asymmetric (rs256/jwks): verify-only, never forge.
    TOKEN_VERIFIER_DRIVER: str = "null"
    TOKEN_ISSUER: str = ""
    TOKEN_AUDIENCE: str = ""
    TOKEN_HS256_SECRET: str = ""  # hs256 driver
    TOKEN_PUBLIC_KEY: str = ""  # rs256 driver (PEM public key)
    TOKEN_JWKS_URL: str = ""  # jwks driver (config allowlist)

    RATELIMITER_DRIVER: str = "memory"
    RATELIMIT_URL: str = ""
    RATELIMIT_MAX: int = 100
    RATELIMIT_WINDOW_SECONDS: int = 60
    RATELIMIT_DEGRADE: str = "local"            # local | closed | open
    RATELIMIT_KEY_PARTS: str = "subject,ip"     # subject | ip | tenant | route (comma list)
    RATELIMIT_ROUTES: str = ""                  # JSON: [{"prefix","class","limit","window_s","cost"}]
    RATELIMIT_COUNT_STATUSES: str = ""          # e.g. "401" for a login surface; comma list

    TELEMETRY_DRIVER: str = "stdout"

    # ── CWE self-guard (Phase 3) ────────────────────────────────────────────
    CWE_GUARD_ENABLED: bool = True
    # SSRF allowlist (CWE-918): comma-separated hostnames egress may target.
    EGRESS_ALLOWED_HOSTS: str = ""
    # Path to a step->CWE map override (TOML). Empty => built-in default map.
    CWE_STEP_MAP_FILE: str = ""

    @property
    def egress_allowed_hosts(self) -> frozenset[str]:
        return frozenset(
            h.strip().lower() for h in self.EGRESS_ALLOWED_HOSTS.split(",") if h.strip()
        )

    # ── Derived helpers ─────────────────────────────────────────────────────
    @property
    def is_test(self) -> bool:
        return self.ENV == "test"

    @property
    def is_production(self) -> bool:
        return self.ENV == "production"

    @property
    def audit_ingest_url(self) -> str:
        """Where audit events go. Empty when no URL is configured — never a guessed default, because
        a wrong host would send the audit trail somewhere the operator cannot read while every call
        still looked successful."""
        if not self.AUDIT_SERVICE_URL:
            return ""
        return self.AUDIT_SERVICE_URL.rstrip("/") + self.AUDIT_INGEST_PATH

    def assert_pii_config_ok(self) -> None:
        """Boot guard. Refuse to start production without the salt that pseudonyms are built from.

        Every service in the platform writes `subject_ref` — the per-tenant pseudonym that lets an
        immutable audit row, ledger entry or invoice outlive the person named in it. It is
        HMAC(PII_SALT, tenant|subject), and `core.pii.subject_ref` REFUSES an empty salt rather
        than emitting an unsalted digest that anyone could reverse by hashing every email address.

        That refusal is correct and badly timed. Without this guard the service starts, passes
        every health check, serves traffic for weeks, and then raises the first time a real person
        touches a path that pseudonymises — which is a 500 in production, at whatever hour the
        first DSAR or first audited action happens to arrive. A misconfiguration must refuse to
        START, not fail one request months later.

        Two services already did this. Nineteen declared PII_SALT and never checked it, which is
        why safety:pii-salt now fails the build for any service that reads the salt without
        guarding it.

        NOT CHECKED HERE, because it cannot be: that every service was given the SAME salt. Two
        different non-empty salts fold one person to two pseudonyms, and every service still boots
        and still works. That is a deployment invariant — see the chart's shared-secret handling
        and config/product.identifiers.lock.json, which freezes the value for exactly this reason.
        """
        if self.is_production and not self.PII_SALT:
            raise ValueError(
                "PII_SALT is empty in production: subject pseudonyms would be unsalted, which "
                "makes them reversible by guessing every email address — not pseudonyms at all. "
                "Any audited or pseudonymised write would 500 the first time it was reached. Set "
                "PII_SALT (it is FROZEN — see config/product.identifiers.lock.json; changing it "
                "re-maps every pseudonym and orphans the history), and set the SAME value in "
                "every service or one person becomes two."
            )

    def assert_search_config_ok(self) -> None:
        """Boot guard. Refuse production with an indexer that indexes nothing.

        The symptom of getting this wrong is not an error anywhere: visits record perfectly, the
        API is green, and the field screen simply never finds a returning customer. The operator
        concludes the customer is new, records them again, and the product's entire premise —
        recognising the customer who came back — is quietly gone.
        """
        if not self.is_production:
            return
        if self.SEARCH_DRIVER == "null":
            raise ValueError(
                "SEARCH_DRIVER=null in production: customers would be recorded and never indexed, "
                "so the field screen could never find a returning customer and every visit would "
                "create a new one. Set it to 'http' with SEARCH_SERVICE_URL."
            )
        if self.SEARCH_DRIVER == "http" and not self.SEARCH_SERVICE_URL:
            raise ValueError("SEARCH_DRIVER=http but SEARCH_SERVICE_URL is empty — nothing to "
                             "index against.")

    def assert_apps_config_ok(self) -> None:
        """Boot guard. Refuse production with no way to read what a shop bought.

        The failure is invisible and it points the wrong way: `NullApps` reports an empty set with
        `checked: true`, so every screen would draw a lock on every paid app for every shop —
        including the ones paying for all five. Nothing errors, nothing logs, and the support call
        is «اشتريت الحملات وما تظهر».
        """
        if not self.is_production:
            return
        if not self.BILLING_SERVICE_URL or not self.BILLING_CHECK_PATH:
            raise ValueError(
                "BILLING_SERVICE_URL/BILLING_CHECK_PATH are empty in production: the console could "
                "not read what any establishment bought, so every paid app would be drawn locked "
                "for every shop — including the ones that pay for all of them.")

    def assert_billing_plans_config_ok(self) -> None:
        """Boot guard. A deployment that cannot list or read subscriptions sells nothing.

        `build_plans` returns `NullPlans` when `BILLING_PLANS_DRIVER` is anything but `http` —
        `"null"` by default, on purpose, so a service under test never dials out. In production
        that silence is total: the store shows no plans, no purchase can be made, and
        `/api/v1/subscription/apps` answers `base: null` for every shop, forever — a paying
        establishment reads exactly the same screen as one that never subscribed, and nothing
        anywhere says why. This is the same shape as `assert_apps_config_ok` and
        `assert_subscription_config_ok` above, guarding the one billing path neither of them
        reaches.
        """
        if not self.is_production:
            return
        if (self.BILLING_PLANS_DRIVER or "null").lower() != "http":
            raise ValueError(
                "BILLING_PLANS_DRIVER is not 'http' in production: no plan can be listed or "
                "subscribed to, and every shop's own subscription reads back empty — the store "
                "sells nothing and the base itself never shows as active."
            )
        if not self.BILLING_SERVICE_URL or not self.BILLING_PLANS_PATH \
                or not self.BILLING_SUBSCRIBE_PATH or not self.BILLING_SUBSCRIPTIONS_PATH:
            raise ValueError(
                "BILLING_PLANS_DRIVER is 'http' but one of BILLING_SERVICE_URL/"
                "BILLING_PLANS_PATH/BILLING_SUBSCRIBE_PATH/BILLING_SUBSCRIPTIONS_PATH is empty — "
                "the driver is configured and inert."
            )

    def assert_seed_config_ok(self) -> None:
        """Boot guard. Refuse production with no message library.

        A SHOP'S OWN SERVICES ARE NOT SEEDED and there is nothing to guard there: it writes its own
        catalogue in «خدماتي», and an empty one is the honest first state rather than a fault. The
        template library is different — it is ours, it is the same for everybody, and without it a
        shop cannot send a single message, which is the product.
        """
        if self.is_production and not self.TEMPLATES_SEED_FILE:
            raise ValueError(
                "TEMPLATES_SEED_FILE is empty in production: the template library would be empty, "
                "and an establishment with no templates cannot send a single message — which is "
                "the product.")

    def assert_audit_config_ok(self) -> None:
        """Boot guard. Refuse to start production without somewhere to witness privileged actions.

        The failure this prevents is specific and was real here: audit-service ran for months with
        a complete ingest endpoint and no callers, so the chain verified perfectly and contained
        nothing. Nothing failed, no test went red, and the control existed only on paper. A service
        that cannot record what it does must not quietly serve traffic as though it can.
        """
        if not self.is_production:
            return
        if self.AUDIT_SINK_DRIVER == "null":
            raise ValueError(
                "AUDIT_SINK_DRIVER=null in production: privileged actions would be performed and "
                "never recorded anywhere. Set it to 'http' (with AUDIT_SERVICE_URL) or 'eventbus'."
            )
        if self.AUDIT_SINK_DRIVER == "http" and not self.AUDIT_SERVICE_URL:
            raise ValueError(
                "AUDIT_SINK_DRIVER=http but AUDIT_SERVICE_URL is empty: every audit event would "
                "fail and the chain would stay empty while the service looked healthy."
            )
        if self.AUDIT_SERVICE_URL and not self.AUDIT_SERVICE_URL.startswith(("http://", "https://")):
            raise ValueError(
                f"AUDIT_SERVICE_URL {self.AUDIT_SERVICE_URL!r} must start with http:// or https://"
            )

    def assert_onboarding_config_ok(self) -> None:
        """Boot guard. `http` with nowhere to send is a driver that degrades into no driver.

        `build_exchange` falls back to `NullExchange` when the peer URL is empty — which it must,
        because building a Request from a relative URL raises outside the try and 500s the owner's
        connect request while Meta's thirty-second code expires. But falling back SILENTLY means a
        deployment with the driver switched on and the URL unset looks configured, serves traffic,
        and refuses every single connection attempt. That combination shipped.

        So the ambiguity is resolved where it can be: at boot, in production, once.
        """
        if not self.is_production:
            return
        if self.WHATSAPP_ONBOARDING_DRIVER == "http" and not self.NOTIFICATION_SERVICE_URL:
            raise ValueError(
                "WHATSAPP_ONBOARDING_DRIVER=http but NOTIFICATION_SERVICE_URL is empty: the "
                "exchange would fall back to the null driver and every owner who finished "
                "Embedded Signup would be told the connection could not be completed."
            )

    def assert_subscription_config_ok(self) -> None:
        """Boot guard. A deployment that cannot ask about a subscription gives the product away.

        `build_feature_licence`/`build_whatsapp_licence` return a Null licence when billing is not
        wired, and a Null licence allows every write. That is right for tests and fatal in
        production: every one of these is a thing shops actually pay for, and a null licence is a
        silent decision to charge nobody. It would look exactly like a healthy service for as long
        as nobody thought to check.

        This is the same shape as the audit guard above, and it exists for the same reason: the
        failure is invisible from the outside, so it has to be refused at boot, once.
        """
        if not self.is_production:
            return
        if not self.BILLING_SERVICE_URL or not self.BILLING_CHECK_PATH:
            raise ValueError(
                "BILLING_SERVICE_URL/BILLING_CHECK_PATH are empty in production: the base licence "
                "would fall back to the null driver and every write would be allowed, so an "
                "expired shop — and a shop that never subscribed — would keep using the product."
            )

    def assert_consent_config_ok(self) -> None:
        """Boot guard. A service that gates processing on consent must be able to ask.

        Only applies when the SERVICE declares CONSENT_GATED — the whole point of that flag is to
        distinguish "this service has no consent-gated processing" from "somebody forgot to
        configure the gate". Those are identical from the driver alone, and that ambiguity is how
        consent-check ran for four phases with no callers and nothing ever went red.
        """
        if not self.is_production or not self.CONSENT_GATED:
            return
        if self.CONSENT_GATE_DRIVER == "null":
            raise ValueError(
                "CONSENT_GATE_DRIVER=null in production, but this service declares consent-gated "
                "processing: every check would answer UNKNOWN and the decision would fall to each "
                "call site's fallback, which is not where a compliance posture should be decided. "
                "Set 'http' with COMPLIANCE_SERVICE_URL."
            )
        if self.CONSENT_GATE_DRIVER == "http" and not self.COMPLIANCE_SERVICE_URL:
            raise ValueError(
                "CONSENT_GATE_DRIVER=http but COMPLIANCE_SERVICE_URL is empty: every consent "
                "question would fail to send and answer UNKNOWN while the service looked healthy."
            )
        if (self.COMPLIANCE_SERVICE_URL
                and not self.COMPLIANCE_SERVICE_URL.startswith(("http://", "https://"))):
            raise ValueError(
                f"COMPLIANCE_SERVICE_URL {self.COMPLIANCE_SERVICE_URL!r} must start with "
                f"http:// or https://"
            )

    @field_validator("INTERNAL_SERVICE_TOKEN")
    @classmethod
    def _reject_placeholder(cls, v: str) -> str:
        # Refuse obvious placeholder/dev tokens in any environment — fail fast so
        # a template default never ships as a real secret.
        lowered = v.strip().lower()
        if lowered.startswith("placeholder") or lowered in {"changeme", "change_me"}:
            raise ValueError("INTERNAL_SERVICE_TOKEN is a placeholder — set a real secret")
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the validated singleton settings.

    Raises pydantic.ValidationError at first call if the environment is invalid,
    which surfaces as a hard startup failure (fail-fast).
    """
    return Settings()  # type: ignore[call-arg]  # values are supplied by env
