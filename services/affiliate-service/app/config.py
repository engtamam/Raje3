# =============================================================================
# affiliate-service — Configuration (fail-fast, ZERO-HARDCODED)
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
    SERVICE_NAME: str = "affiliate-service"
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
    # Salts the subject pseudonym on an erasure ack. FROZEN — config/product.identifiers.lock.json.
    PII_SALT: str = ""
    ERASURE_MAX_SCAN: int = 100_000   # a DSAR is rare, but must never be an unbounded read

    # ── onboarding («بوابة القبول», spec §2) ───────────────────────────────────
    # identity-service is generic (confirmed by reading its own auth_service.py) — no change was
    # needed there. Every marketer becomes a MEMBER of this one tenant; there is no tenant per
    # marketer, because the hierarchy (manager -> promoter) is ours to keep, not identity's.
    IDENTITY_SERVICE_URL: str = ""              # e.g. http://identity-service:8000
    AFFILIATE_TENANT: str = ""                  # the one shared tenant id — REQUIRED in production
    # THE TENANT'S OWN PROVISIONING (onboarding.py::_ensure_tenant_ready). Both optional: empty
    # means "assume AFFILIATE_TENANT already exists and is bootstrapped", which is what keeps a
    # local/test run working exactly as before this existed. Set both in production, or the
    # first-ever approval mints a membership into a tenant no role was ever declared for.
    TENANT_SERVICE_URL: str = ""
    AUTHZ_SERVICE_URL: str = ""
    AFFILIATE_MANAGER_ROLE: str = "affiliate_manager"
    AFFILIATE_PROMOTER_ROLE: str = "affiliate_promoter"
    AFFILIATE_PHONE_DEFAULT_CC: str = "966"
    ONBOARDING_TIMEOUT_SECONDS: int = 10
    # THE VERSION OF THE TERMS AN APPLICANT IS AGREEING TO — spec §2's own "قبول الشروط إجباري
    # قبل التفعيل". NOT a full compliance-service integration (the version-pinned, re-prompt-on-
    # publish machinery Door.tsx's own LegalGate drives for shops) — that is a real future
    # upgrade, tracked as such rather than pretended away. This is the honest minimum until then:
    # apply() refuses without agreement, and WHICH version he agreed to is recorded, so a later
    # dispute has an answer ("he agreed to v1 on this date") rather than nothing at all. A config
    # value, never hardcoded, so a real wording change is a value bump an admin makes on purpose.
    AFFILIATE_TERMS_VERSION: str = "v1"
    # ── phone-ownership OTP (Tamam, 2026-08-23) — same two-knob shape as operations' own
    # SIGNUP_OTP_DELIVERABLE/SIGNUP_REQUIRE_OTP, deliberately: DELIVERABLE is "can a code actually
    # reach a phone" (false everywhere today — notification-service's own WHATSAPP_CHAIN/
    # SMS_CHAIN are still the no-op `console` driver), REQUIRE is "does apply() refuse without
    # one". Independent knobs so the moment real WhatsApp/SMS credentials exist, flipping both to
    # true turns this into a hard gate with no further code change — see onboarding.py's own note.
    AFFILIATE_OTP_DELIVERABLE: bool = False
    AFFILIATE_REQUIRE_OTP: bool = False

    # ── referral commission (spec §4 — a FLAT amount, not a percentage) ────────────────────────
    # Halalas, never riyals-as-float: money as a float is how "40.10" becomes "40.099999999999994"
    # three additions later. 4000 halalas = 40.00 SAR. LOCKED onto each Referral row at stamp
    # time (see core/referrals.py) — changing this later reprices only referrals stamped after
    # the change, never ones already promised a rate.
    AFFILIATE_COMMISSION_AMOUNT_HALALAS: int = 0

    # THE CONVERSION WINDOW — Tamam, 2026-08-19: bounds our liability to a written, known
    # duration rather than an open-ended one. A shop can register through an affiliate's link
    # today and subscribe two years from now; without a limit that is still a live, disputable
    # claim two years later. From `stamped_at`, NOT from any click — this product has no click
    # tracking and does not need one (SaaS, not a product-marketing funnel): registration is the
    # anchor event. See core/models.py's own LAPSED status.
    AFFILIATE_CONVERSION_WINDOW_DAYS: int = 90

    # ── the commission engine itself (spec §4, "٥/٦/٧" of the slice table) ────────────────────
    # billing-service v0.16.26+ — GET /internal/billing/invoices, the durable read this engine
    # keys money on rather than the at-most-once event bus (billing's own events.py contract).
    BILLING_SERVICE_URL: str = ""
    # "مُستحقة" ليست "مؤكدة" — a commission holds this many days from the invoice's own paid_at
    # before it is withdrawable, in case that payment is refunded within the window.
    AFFILIATE_COMMISSION_HOLD_DAYS: int = 7
    # RENEWAL COMMISSIONS RETIRED (Tamam, 2026-08-20): a flat cut on every Nth renewal paid
    # indefinitely for revenue nobody was servicing — see core/models.py's own note on
    # COMMISSION_KINDS. Real ongoing team involvement belongs to a separate program (a shop-count
    # threshold + actual support work, its own KPI), not a recurring commission here.

    # ── «برنامج دعم الوفاء» (spec §8, Tamam, 2026-08-20) — see core/wafa.py's own module docstring
    # for the full reasoning behind every one of these.
    # floor(active_shops / WAFA_TIER_SHOPS) * WAFA_TIER_AMOUNT_HALALAS — 50 shops = 500 SAR.
    WAFA_TIER_SHOPS: int = 50
    WAFA_TIER_AMOUNT_HALALAS: int = 50000
    # Anchored to the REQUEST, never the decision — see core/wafa.py.
    WAFA_COOLDOWN_DAYS: int = 30
    # The system's own recommendation threshold — retention_rate at/above this AND refund_rate
    # at/below the other one both required, or the system recommends REJECT. Advisory only: an
    # admin may still grant against it (see WafaService.admin_decide).
    WAFA_RETENTION_MIN: float = 0.70
    WAFA_REFUND_MAX: float = 0.15

    # ── «رشّح نفسك لوظيفة» (spec §8) — see core/employment.py's own module docstring.
    AFFILIATE_EMPLOYMENT_THRESHOLD_CUSTOMERS: int = 500

    # ── §٦ Lead Sourcing — see core/leads.py's own module docstring on BYOK.
    # A platform-wide LAST-RESORT default, only reached when a manager has set no key of his own
    # AND no admin has set a tenant="" default via SecretStore either. Blank means "refused" —
    # see the routes in api/v1/affiliate_self.py.
    LEADS_PLACES_API_KEY_FALLBACK: str = ""
    # How many (grid point × keyword) units POST /internal/leads/tick advances per call — same
    # "capped sweep records where it stopped" shape as AFFILIATE_SWEEP_MAX. A k3s CronJob calls
    # this on a schedule; a full search is hours (places_scraper_v2.py's own estimate), so this
    # is what turns "hours" into "many small, resumable calls" rather than one long request.
    LEADS_TICK_UNITS: int = 20

    # ── §١٣ Ticket integration — see core/tickets.py's own module docstring.
    # ticket-service v0.16.27+ — GET /internal/tickets(+/{id}), consent-scoped via ShareGrant.
    # Blank means "not wired yet" — WafaService.performance_for degrades support_kpis to
    # available:False rather than failing.
    TICKET_SERVICE_URL: str = ""
    # §١٣'s auto-escalation (Tamam, 2026-08-20) — see core/escalation.py's own module docstring.
    # No response within this many hours -> escalated to the promoter's own manager. Config, not
    # a hardcoded 24 — a deployment may want a different SLA.
    AFFILIATE_TICKET_ESCALATION_HOURS: int = 24
    # Same "capped, records where it stopped" bound as AFFILIATE_SWEEP_MAX.
    AFFILIATE_TICKET_ESCALATION_SWEEP_MAX: int = 200
    # THE FAST PATH — billing's own event bus, subscribed to as a HINT that makes sync() run
    # sooner, never as the only way a commission is discovered (app/ports/event_bus.py's own
    # contract: "at-most-once, best effort... An event is a HINT... It is NEVER the only way a
    # fact can be learned"). Comma list; empty disables the subscription entirely (an in-memory
    # eventbus driver makes this inert regardless — each pod's bus is its own, so a real
    # subscription needs EVENTBUS_DRIVER=redis shared with billing-service).
    AFFILIATE_COMMISSION_SYNC_TOPICS: str = "payment.succeeded,invoice.paid"
    # THE BACKSTOP — POST /internal/commissions/sweep, meant to run on a schedule (see the
    # deploy values' cronJobs). Bounded: a referral history that outgrows this in one sweep needs
    # a real paged sweep, not a bigger number silently hiding the day it happens.
    AFFILIATE_SWEEP_MAX: int = 500

    # ── withdrawal (spec §5) ────────────────────────────────────────────────────────────────
    # 0 disables the floor (any confirmed balance may be withdrawn) — an explicit choice, not a
    # missing config: a deployment that wants no minimum should not have to fake one.
    AFFILIATE_WITHDRAWAL_MIN_HALALAS: int = 0
    # THE RECEIPT ITSELF (Tamam, 2026-08-20: "كل الطرق ممكنة" — an admin may either upload the
    # actual file or just paste a link; both write to the SAME `receipt_reference` field, so
    # completing a withdrawal never has to know which one happened). Bounded well under
    # BODY_LIMIT_BYTES's own default (1 MiB) is wrong for a real photo of a transfer
    # confirmation, so raise BOTH together — this alone being generous does nothing if the
    # request never gets past BodyLimitMiddleware first.
    # UNDER the template's own BODY_LIMIT_BYTES default (1 MiB) ON PURPOSE — see
    # assert_receipt_config_ok below for why a bigger default here would fail every upload near
    # it rather than actually allow one. A deployment that wants real phone-camera photos raises
    # BOTH this and BODY_LIMIT_BYTES together, deliberately.
    AFFILIATE_RECEIPT_MAX_BYTES: int = 1_000_000
    AFFILIATE_RECEIPT_CONTENT_TYPES: str = "image/jpeg,image/png,image/webp,application/pdf"

    @property
    def affiliate_receipt_content_types(self) -> list[str]:
        return [t.strip() for t in self.AFFILIATE_RECEIPT_CONTENT_TYPES.split(",") if t.strip()]

    @property
    def affiliate_commission_sync_topics(self) -> list[str]:
        return [t.strip() for t in self.AFFILIATE_COMMISSION_SYNC_TOPICS.split(",") if t.strip()]

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
    # Retrying a transient audit failure is safe because every emit carries an idempotency key (a
    # repeat is deduped by the log, never appended twice). Small by design: this sits on the request
    # path, so 2 attempts with a short backoff turns one slow call into a second chance without
    # spending the whole budget the timeout protects.
    AUDIT_MAX_ATTEMPTS: int = 2
    AUDIT_RETRY_BACKOFF_SECONDS: float = 0.2
    # How long a client should wait before retrying an action we REFUSED because the audit log
    # was unreachable. It is a 503 + Retry-After, never a 500: the action did not happen, nothing
    # committed, and trying again later is the correct response. A 500 would tell the caller we
    # crashed, which invites a bug report instead of a retry.
    AUDIT_RETRY_AFTER_SECONDS: int = 30

    # ── consent gate — ask before processing personal data ────────────────────
    # compliance-service served consent-check with ZERO callers for four phases: the control was
    # built and nothing consulted it. `null` answers UNKNOWN (never ALLOWED — a gate that invented
    # permission would be worse than no gate), and each call site declares what to do with that.
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

    # ── object-store credentials: one provider seam, selected by config (see credentials.py) ─────
    # static | imds | alibaba-ecs-ram | sts-endpoint. Default static = the two keys above, unchanged.
    #   imds             botocore's ambient chain (AWS EC2 / ECS task role).
    #   alibaba-ecs-ram  the Alibaba ECS instance RAM role (short-lived, self-refreshing); botocore's
    #                    imds provider cannot read Alibaba's dialect, so "" credentials there fail.
    #   sts-endpoint     a generic STS-style HTTP endpoint (JSON field names configurable below).
    OBJECTSTORE_CREDENTIALS: str = "static"
    # Metadata / STS base URL — REQUIRED for the two metadata modes (refused empty at startup). The
    # address is a property of the cloud (e.g. Alibaba serves it at http://100.100.100.200); set it in
    # the deploy values, never in code. Config allowlist, never a request value (SSRF).
    OBJECTSTORE_METADATA_ENDPOINT: str = ""
    OBJECTSTORE_METADATA_ROLE: str = ""                 # alibaba: optional — auto-discovered if empty
    OBJECTSTORE_METADATA_TOKEN_TTL: int = 21600         # alibaba IMDSv2-style metadata-token TTL (s)
    OBJECTSTORE_METADATA_TIMEOUT_SECONDS: float = 5.0   # bound the metadata call
    # sts-endpoint: which JSON field carries each value. Defaults to Alibaba's STS names; override for
    # another provider so the next cloud is a values change, not a release.
    OBJECTSTORE_STS_ACCESS_KEY_FIELD: str = "AccessKeyId"
    OBJECTSTORE_STS_SECRET_KEY_FIELD: str = "AccessKeySecret"
    OBJECTSTORE_STS_TOKEN_FIELD: str = "SecurityToken"
    OBJECTSTORE_STS_EXPIRY_FIELD: str = "Expiration"

    SECRETS_DRIVER: str = "env"
    SECRETS_FILE: str = ""  # file driver: path to a KEY=VALUE file
    VAULT_ADDR: str = ""
    VAULT_TOKEN: str = ""
    VAULT_PATH: str = ""

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

    def assert_onboarding_config_ok(self) -> None:
        """Boot guard. Without these two, every /apply and every /admin/applications/*/approve
        would fail at the FIRST identity call — but only once a real applicant hits it, minutes
        or days after deploy, never at boot where the mistake is cheap to see."""
        if not self.is_production:
            return
        if not self.AFFILIATE_TENANT:
            raise ValueError(
                "AFFILIATE_TENANT is empty in production: there would be no tenant to mint "
                "marketer memberships into, and every approval would fail."
            )
        if not self.IDENTITY_SERVICE_URL:
            raise ValueError(
                "IDENTITY_SERVICE_URL is empty in production: onboarding cannot reach identity "
                "at all, so no applicant could ever sign in even once approved."
            )
        if not self.IDENTITY_SERVICE_URL.startswith(("http://", "https://")):
            raise ValueError(
                f"IDENTITY_SERVICE_URL {self.IDENTITY_SERVICE_URL!r} must start with "
                f"http:// or https://"
            )

    def assert_receipt_config_ok(self) -> None:
        """Boot guard. BODY_LIMIT_BYTES applies to EVERY request, including a receipt upload — a
        generous AFFILIATE_RECEIPT_MAX_BYTES does nothing if BodyLimitMiddleware rejects the
        request before the route ever sees it. Silent otherwise: every upload past the real
        (smaller) ceiling would 413, and the error would look like a bug in the receipt route
        rather than the two limits disagreeing.

        Production-only, same as the platform's other deployment-readiness guards — a local/test
        run tightens BODY_LIMIT_BYTES for its own unrelated reasons (see tests/conftest.py) and
        must not be made to also reason about receipt sizing to boot at all."""
        if not self.is_production:
            return
        if self.AFFILIATE_RECEIPT_MAX_BYTES > self.BODY_LIMIT_BYTES:
            raise ValueError(
                f"AFFILIATE_RECEIPT_MAX_BYTES ({self.AFFILIATE_RECEIPT_MAX_BYTES}) exceeds "
                f"BODY_LIMIT_BYTES ({self.BODY_LIMIT_BYTES}) — every receipt upload near the "
                f"declared max would be rejected by BodyLimitMiddleware first. Raise "
                f"BODY_LIMIT_BYTES to at least match."
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
