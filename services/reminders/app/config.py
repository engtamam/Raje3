# =============================================================================
# reminders — Configuration (fail-fast, ZERO-HARDCODED)
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
    SERVICE_NAME: str = "reminders"
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

    # ── audit trail (Phase 38) — where privileged actions are witnessed ───────
    # `null` records NOTHING and says so; the boot guard below refuses it in production, because a
    # service that cannot witness its own privileged actions has no audit trail at all — and an
    # empty hash chain looks like a working control while answering nothing.
    # WHERE A CUSTOMER READS THEIR PAGE, as a customer can reach it. Every other URL in this file
    # is a service address inside the cluster; this is the only one a person outside it ever sees.
    #
    # EMPTY BY DEFAULT AND NEVER GUESSED. `core/links.py` refuses to build a link without it, and
    # that refusal is the point: a default of `https://raje3.sa` would work in production and
    # silently misdirect every pilot, test box and customer install to a domain that is not theirs.
    # Set from DOMAIN at install time.
    PUBLIC_BASE_URL: str = ""                # e.g. https://raje3.sa
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

    # ── sending: the peers this service cannot work without ───────────────────
    # `null` records what it WOULD have sent and delivers nothing. Correct for tests and a local
    # run; refused in production by the boot guard below, where it would mean a service that
    # schedules perfectly and messages nobody — the quietest outage this platform can produce.
    SENDER_DRIVER: str = "null"              # null | http
    NOTIFICATION_SERVICE_URL: str = ""       # e.g. http://notification-service:8000
    # THEIR path, read from notification-service's manifest rather than assumed. An earlier service
    # on this platform shipped /internal/notifications/send against a peer serving /internal/notify,
    # and every notification went to a silent 404 for weeks — a failed notification is not a failed
    # ticket, so nothing looked wrong.
    NOTIFICATION_SEND_PATH: str = "/internal/notify"
    # DID IT ARRIVE, AND WAS IT READ. The status webhook is at-most-once and lands on the
    # notification peer, which persists each receipt against the delivery it belongs to and serves
    # them from a cursor, oldest first. This service reads that forward and writes the fact onto
    # its own send log — the answer to «هل وصلت؟», which it could not give about its own work.
    # Added in base-services v0.16.11, after we escalated that a receipt could not be matched to a
    # send at all.
    NOTIFICATION_RECEIPTS_PATH: str = "/internal/notifications/receipts"
    # WHICH TEMPLATES META HAS APPROVED, for this tenant. Added in base-services v0.13.5 after we
    # escalated: the user-tier list needed a JWT this service cannot mint, so choose(approved=) was
    # written and removed the same day. Empty means the filter is skipped and a send is spent
    # discovering a template is still in review — correct, and wasteful for a shop that connected
    # this morning with its whole library pending.
    NOTIFICATION_TEMPLATES_PATH: str = "/internal/whatsapp/templates"
    # HIS OWN TEXT, TO META. The internal twins (base-services v0.16.6) that answered our
    # escalation: register is a local upsert, submit hands one template to Meta for review.
    NOTIFICATION_TEMPLATE_REGISTER_PATH: str = "/internal/whatsapp/templates"
    NOTIFICATION_TEMPLATE_SUBMIT_PATH: str = "/internal/whatsapp/templates/{name}/{language}/submit"

    # ── the measurement group (proof 2) ──────────────────────────────────────────────────────
    # A tenth of each shop's customers receive no reminder, offer or campaign, so that «هل الرسائل
    # تنفع؟» has an answer the owner measures instead of one we assert. OFF BY DEFAULT AT THE
    # PLATFORM LEVEL and switched on per establishment from his own settings: withholding a shop's
    # product from its customers is not a decision a config default should make for him.
    #
    # The share is here rather than per-tenant on purpose. It is a statistical choice, not a
    # business one, and a shop that sets it to 40% has not customised anything — it has stopped
    # sending to nearly half its people while believing it bought a report.
    HOLDOUT_ENABLED: bool = False
    HOLDOUT_SHARE_PERCENT: int = 10

    # ── WhatsApp's own ceiling — THEIR numbers, so none of them lives in code ──
    # The rolling window a business-initiated conversation counts against. Meta's, and Meta has
    # changed its messaging rules more than once.
    REACH_WINDOW_SECONDS: int = 86_400
    # The error codes that mean "not now" rather than "never" or "something broke" — from Meta's
    # Cloud API error reference. Codes, never message text: the text is translated and reworded,
    # and a branch matching a phrase stops matching with nothing failing.
    WHATSAPP_CEILING_CODES: str = "130429,80007,131048,131056,131064,131049"
    # How long a refused message waits. OURS, and the only certainly-wrong answer is an hour: the
    # window is rolling, so an hour later is the same closed door and a tick spent finding out.
    CEILING_DEFER_SECONDS: int = 43_200
    # THE CEILING ITSELF, read live from Meta through notification-service (base-services v0.14.1,
    # added after we escalated it). `null` answers unknown, and unknown is a real answer here — we
    # stop PLANNING and never stop sending, because Meta enforces its own limit at the door and a
    # shop silenced by our failure to read a number is our outage wearing their ceiling.
    CEILING_DRIVER: str = "null"             # null | http
    NOTIFICATION_MESSAGING_LIMIT_PATH: str = "/internal/whatsapp/messaging-limit"

    @property
    def whatsapp_ceiling_codes(self) -> tuple[str, ...]:
        return tuple(c.strip() for c in self.WHATSAPP_CEILING_CODES.split(",") if c.strip())
    # OURS. Turns a subject_ref back into a destination at send time, so no phone number ever rests
    # in this service. See adapters/message_sender for why this is a route and not a column.
    OPERATIONS_SERVICE_URL: str = ""         # e.g. http://operations:8000
    OPERATIONS_RECIPIENT_PATH: str = "/internal/operations/recipient"
    # WHICH BRANCH THIS PERSON MAY SEE — asked of the only service that staffs the shop.
    #
    # The send log narrows by branch, and until now it narrowed by whatever branch the CALLER
    # typed: a manager assigned to Jeddah could read every message that went out in Riyadh's name
    # by changing one query parameter. «ما الذي خرج باسمي» is the question this service exists to
    # answer, and it was answering it about other people's branches.
    OPERATIONS_SCOPE_PATH: str = "/internal/operations/branch-scope"
    # The catch-up read. The event bus is at-most-once (see ports/event_bus.py), so a missed visit
    # is a reminder that never exists — for ever. This is the readable path that repairs it.
    OPERATIONS_VISITS_SINCE_PATH: str = "/internal/operations/visits/since"
    # THE TEXTS THEMSELVES. Read from the service that owns them; the alternative was a cache
    # collection nothing wrote, which answered "no templates" on every tick for as long as it
    # existed. Empty here means the engine keeps whatever it last read and never an empty library.
    OPERATIONS_TEMPLATES_PATH: str = "/internal/operations/templates"
    # THE SHOP'S OWN SERVICE CYCLES. Not a preference of ours — the number the owner sees in
    # «خدماتي», which the owner writes himself. Unread until today, so every shop that never
    # edited a service had every reminder scheduled on the 90-day default.
    OPERATIONS_CATALOGUE_PATH: str = "/internal/operations/catalogue"
    # Per tenant, per tick at most. A catalogue changes when its owner edits it; a minute of
    # staleness costs a reminder scheduled a day early at worst.
    CATALOGUE_TTL_SECONDS: int = 300
    # Platform content, identical for every tenant, edited by us. Minutes of staleness cost
    # nothing; a read per tenant per tick would be one call per shop per five minutes.
    TEMPLATE_LIBRARY_TTL_SECONDS: int = 300

    # ── who the establishment is ──────────────────────────────────────────────
    # Every message renders {{2}} as the shop's name. `null` answers nothing, which means every
    # message would go out with a blank where the name belongs — accepted by Meta, read by the
    # customer, and apologised for by the owner. Refused in production by the boot guard.
    IDENTITY_DRIVER: str = "null"            # null | http
    TENANT_SERVICE_URL: str = ""             # e.g. http://tenant-service:8000
    # THEIRS, from tenant-service's manifest. The record carries `name` and a free-form `branding`
    # dict; our `tone` lives inside that dict under a key we own rather than in a table we invent.
    TENANT_READ_PATH: str = "/internal/tenants/{id}"
    # Short, so a shop that fixes a typo sees it in the next message rather than next week. The
    # FALLBACK to a stale value is unbounded on purpose — see adapters/identity.
    IDENTITY_CACHE_TTL_SECONDS: int = 300
    MESSAGE_CHANNEL: str = "whatsapp"
    PEER_TIMEOUT_SECONDS: int = 8

    # ── the message meter ─────────────────────────────────────────────────────
    # We do not sell messages — Meta bills the establishment directly (spec §16.7). This measures
    # what we send on its behalf, so a runaway loop of ours is caught here rather than on its bill.
    # The call is still the atomic one: an advisory check followed by a send measures nothing
    # reliable when two replicas run the same tick.
    QUOTA_DRIVER: str = "null"               # null | http
    BILLING_SERVICE_URL: str = ""            # e.g. http://billing-service:8000
    # THEIRS, from billing-service's internal API. Written as settings rather than constants for
    # the same reason as every other peer path here: a peer that moves a route must not need a
    # code change in six services.
    BILLING_CONSUME_PATH: str = "/internal/billing/usage/consume"
    BILLING_RELEASE_PATH: str = "/internal/billing/usage/release"
    BILLING_CHECK_PATH: str = "/internal/billing/entitlements/check"

    # ── the engines, as settings rather than constants ────────────────────────
    # The right smoothing factor for a car wash is not the right one for a workshop, and we do not
    # know either yet. What we know is the shape — freezing a guess into code is how a tunable
    # becomes a rewrite.
    ADAPTIVE_ALPHA: float = 0.3
    ADAPTIVE_ANOMALY_FACTOR: float = 2.5
    ADAPTIVE_MIN_DAYS: float = 7.0
    ADAPTIVE_MAX_DAYS: float = 730.0
    ADAPTIVE_WARMUP_OBSERVATIONS: int = 2
    DEFAULT_INTERVAL_DAYS: float = 90.0
    DEFAULT_LEAD_DAYS: float = 7.0

    # HOW LONG AFTER A VISIT THE CONFIRMATION GOES OUT (§8.4.2). Ten minutes, not instantly: a
    # message that arrives while the customer is still at the counter is a message about something
    # he is watching happen. And not an hour, either — after that it stops being a confirmation
    # and becomes a shop remembering him, which is a different message with a different name.
    VISIT_CONFIRM_DELAY_SECONDS: int = 600

    ENGAGEMENT_HALF_LIFE_DAYS: float = 60.0
    # Derived from the half-life, not chosen to look round: with a visit worth 10 points, a
    # threshold of 10 is reachable only on the DAY of the visit. See core/engagement.py.
    ENGAGEMENT_FULL_THRESHOLD: float = 5.0
    ENGAGEMENT_MINIMAL_THRESHOLD: float = 1.5

    # ── the caps (spec 8.4.2) ─────────────────────────────────────────────────
    # Platform-owned. An establishment cannot raise these from its own screen: a blocked number
    # lowers the quality rating of every number we hold, so the cost of one shop's decision lands
    # on shops that did not make it.
    SEND_WINDOW_START_HOUR: int = 7
    SEND_WINDOW_END_HOUR: int = 22
    DAILY_SERVICE_CAP: int = 1
    DAILY_TOTAL_CAP: int = 2
    MONTHLY_MARKETING_CAP: int = 4
    MONTHLY_AWARENESS_CAP: int = 1
    MARKETING_COOLDOWN_HOURS: int = 72
    # Bounded per tenant per tick. An unbounded sweep is how a slow query becomes a missed batch
    # becomes a day of reminders that never went out.
    TICK_BATCH_SIZE: int = 100
    # Tenants per tick. The cron runs every five minutes; a run that tries to serve ten thousand
    # establishments in one request holds a worker until it is killed, and the next run starts over
    # from the same place. Bounded work that finishes beats complete work that never does.
    TICK_MAX_TENANTS: int = 200

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

    def assert_subscription_config_ok(self) -> None:
        """Boot guard. A deployment that cannot ask about a subscription gives the product away.

        `build_base_licence` returns `NullBaseLicence` when billing is not wired, and it allows
        every write. That is right for tests and fatal in production: the base is the thing every
        shop pays for, and a null licence is a silent decision to charge nobody. It would look
        exactly like a healthy service for as long as nobody thought to check.

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


    def assert_sender_config_ok(self) -> None:
        """Boot guard. Refuse production with a sender that sends nothing.

        The symptom is not an error anywhere: visits record, schedules are created, the tick runs
        green, the log fills with rows marked sent — and no customer ever receives a message. Every
        dashboard on the platform says the product works. This is the single most important guard
        in this service.
        """
        if not self.is_production:
            return
        if self.IDENTITY_DRIVER == "null":
            raise ValueError(
                "IDENTITY_DRIVER=null in production: every message would render an empty "
                "establishment name — accepted by Meta, read by the customer, and apologised for "
                "by the owner. Set it to 'http' with TENANT_SERVICE_URL.")
        if self.IDENTITY_DRIVER == "http" and not self.TENANT_SERVICE_URL:
            raise ValueError("IDENTITY_DRIVER=http but TENANT_SERVICE_URL is empty.")
        if self.SENDER_DRIVER == "null":
            raise ValueError(
                "SENDER_DRIVER=null in production: reminders would be scheduled, gated, rendered "
                "and logged as sent, and not one message would reach a customer. Set it to 'http' "
                "with NOTIFICATION_SERVICE_URL and OPERATIONS_SERVICE_URL.")
        if not self.NOTIFICATION_SERVICE_URL:
            raise ValueError("SENDER_DRIVER=http but NOTIFICATION_SERVICE_URL is empty — nothing "
                             "to send through.")
        if not self.OPERATIONS_SERVICE_URL:
            raise ValueError(
                "SENDER_DRIVER=http but OPERATIONS_SERVICE_URL is empty. This service holds no "
                "phone numbers by design; without the recipient resolver every send fails with no "
                "destination, and the failure looks like a notification-service outage.")
        # THE METER IS NOT OPTIONAL IN PRODUCTION, even though it no longer caps anything.
        # QUOTA_DRIVER=null sends every message and records none, so a runaway loop in our own code
        # is invisible here and surfaces as a bill the OWNER pays to Meta. We do not sell messages
        # (spec §16.7); we are still responsible for not generating them by accident.
        if self.QUOTA_DRIVER == "null":
            raise ValueError(
                "QUOTA_DRIVER=null in production: every send would go unmeasured, so a runaway "
                "loop of ours would first appear on the owner's bill from Meta. Set it to 'http' "
                "with BILLING_SERVICE_URL.")
        if not self.BILLING_SERVICE_URL:
            raise ValueError("QUOTA_DRIVER=http but BILLING_SERVICE_URL is empty — there is "
                             "nothing to record the sends against.")

    def assert_caps_sane(self) -> None:
        """Boot guard. Refuse a configuration that disables the protection it looks like it sets.

        A window of 0-24 and a cap of 999 are not 'generous settings' — they are the absence of the
        control, expressed in the same shape as the control. Someone widening a limit for one noisy
        establishment must not be able to switch the whole regime off by rounding.
        """
        if not (0 <= self.SEND_WINDOW_START_HOUR < self.SEND_WINDOW_END_HOUR <= 24):
            raise ValueError("the sending window must be a real interval inside one day.")
        if self.is_production and self.SEND_WINDOW_END_HOUR - self.SEND_WINDOW_START_HOUR > 17:
            raise ValueError(
                "a sending window wider than 17 hours is not a window: promotional messages are "
                "barred 10pm-7am by regulation, and a configuration that permits them is a "
                "compliance failure expressed as a setting.")
        for name, value, ceiling in (("DAILY_TOTAL_CAP", self.DAILY_TOTAL_CAP, 5),
                                     ("MONTHLY_MARKETING_CAP", self.MONTHLY_MARKETING_CAP, 12)):
            if value < 1 or value > ceiling:
                raise ValueError(f"{name}={value} is outside the defensible range (1..{ceiling}). "
                                 f"A cap that high is the absence of a cap.")

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the validated singleton settings.

    Raises pydantic.ValidationError at first call if the environment is invalid,
    which surfaces as a hard startup failure (fail-fast).
    """
    return Settings()  # type: ignore[call-arg]  # values are supplied by env
