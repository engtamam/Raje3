# =============================================================================
# whatsapp-assistant — Configuration (fail-fast, ZERO-HARDCODED)
# -----------------------------------------------------------------------------
# Every knob is an env var validated by Pydantic at boot. No hardcoded numbers,
# thresholds, model names or pricing anywhere in app/ — they all live here.
# =============================================================================
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Values come from env vars (or a local .env file)."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore")

    # ── Identity ────────────────────────────────────────────────────────────
    SERVICE_NAME: str = "whatsapp-assistant"
    SERVICE_VERSION: str = "0.1.0"
    ENV: Literal["development", "production", "test"] = "production"

    # ── HTTP server ─────────────────────────────────────────────────────────
    HOST: str = "0.0.0.0"  # noqa: S104 — bind address is operator-controlled config
    PORT: int = 8000
    LOG_LEVEL: Literal["debug", "info", "warning", "error"] = "info"
    REQUEST_TIMEOUT_MS: int = 30_000
    BODY_LIMIT_BYTES: int = 1_048_576
    ALLOWED_FRAME_ANCESTORS: str = "'none'"

    CORS_ALLOWED_ORIGINS: str = ""
    CORS_ALLOW_CREDENTIALS: bool = False
    CORS_ALLOWED_METHODS: str = "GET,POST,PUT,PATCH,DELETE,OPTIONS"
    CORS_ALLOWED_HEADERS: str = "authorization,content-type,x-request-id"
    CORS_MAX_AGE_SECONDS: int = 600

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
        if "*" in self.cors_origins and self.CORS_ALLOW_CREDENTIALS:
            raise ValueError("CORS_ALLOWED_ORIGINS='*' with credentials is refused by every browser.")
        if self.is_production and "*" in self.cors_origins:
            raise ValueError("CORS_ALLOWED_ORIGINS='*' in production is refused.")

    # ── Internal service-to-service auth (REQUIRED) ─────────────────────────
    INTERNAL_SERVICE_TOKEN: str = Field(min_length=32)
    PII_SALT: str = ""
    SECRETS_KEK: str = ""

    @field_validator("INTERNAL_SERVICE_TOKEN")
    @classmethod
    def _reject_placeholder(cls, v: str) -> str:
        lowered = v.strip().lower()
        if lowered.startswith("placeholder") or lowered in {"changeme", "change_me"}:
            raise ValueError("INTERNAL_SERVICE_TOKEN is a placeholder — set a real secret")
        return v

    # ── audit trail — where privileged actions are witnessed ─────────────────
    AUDIT_SINK_DRIVER: str = "null"          # null | http | eventbus
    AUDIT_SERVICE_URL: str = ""
    AUDIT_INGEST_PATH: str = "/internal/audit"
    AUDIT_TOPIC: str = "audit.events"
    AUDIT_TIMEOUT_SECONDS: int = 5
    AUDIT_RETRY_AFTER_SECONDS: int = 30
    # Fail closed: booking confirm / points redeem must not proceed unwitnessed. See
    # app/auditable_actions.py — those two actions are the ones marked critical.
    AUDIT_FAIL_CLOSED: bool = True

    def assert_audit_config_ok(self) -> None:
        if not self.is_production:
            return
        if self.AUDIT_SINK_DRIVER == "null":
            raise ValueError(
                "AUDIT_SINK_DRIVER=null in production: a booking confirmed or points redeemed by "
                "this assistant would happen with no record of who (or what) triggered it.")
        if self.AUDIT_SINK_DRIVER == "http" and not self.AUDIT_SERVICE_URL:
            raise ValueError("AUDIT_SINK_DRIVER=http but AUDIT_SERVICE_URL is empty.")

    def assert_pii_config_ok(self) -> None:
        if self.is_production and not self.PII_SALT:
            raise ValueError(
                "PII_SALT is empty in production: the opaque per-conversation reference handed to "
                "the LLM (see core/conversation.py) is derived from it — without a salt the "
                "reference would be reversible or absent.")

    # ── peers this service depends on ────────────────────────────────────────
    # THEIRS. notification-service is where inbound WhatsApp messages are received, verified and
    # published (`whatsapp.message`, `whatsapp.status`) and where TEMPLATE-ONLY outbound sends go.
    NOTIFICATION_SERVICE_URL: str = ""
    NOTIFICATION_SEND_PATH: str = "/internal/notify"
    # ESCALATED: /internal/notify is template-only — no field or code path for an interactive
    # button/list message. DirectCloudApiSender (adapters/whatsapp_sender/direct.py) exists solely
    # to cover that gap by calling Meta's Graph API directly within the 24h customer-service
    # window. Retire it the day /internal/notify grows interactive-message support.
    NOTIFICATION_INTERACTIVE_GAP_ACK: bool = True

    # operations — customer recognition (phone -> subject_ref) and visit-pattern summaries.
    OPERATIONS_SERVICE_URL: str = ""
    # ESCALATED: no phone->customer lookup existed anywhere in operations before this service. We
    # added the narrowest possible route, /internal/operations/customer-by-phone (reusing the
    # existing CustomerStore.by_phone — see services/operations/app/api/internal.py), returning a
    # pseudonym and a visit-count/last-visit PATTERN only — never the phone or name back to us.
    OPERATIONS_CUSTOMER_BY_PHONE_PATH: str = "/internal/operations/customer-by-phone"
    OPERATIONS_CUSTOMER_VISITS_PATH: str = "/internal/operations/customer-visits"

    # loyalty — points summaries and redemption confirmation (button-only, never LLM-triggered).
    LOYALTY_SERVICE_URL: str = ""
    LOYALTY_BALANCE_PATH: str = "/internal/loyalty/portal/balance"
    LOYALTY_REDEEM_PATH: str = "/internal/loyalty/redeem"

    PEER_TIMEOUT_SECONDS: int = 8

    # ── Meta WhatsApp Cloud API (DirectCloudApiSender) ───────────────────────
    # Per-tenant access tokens are NOT env vars — they are operator-managed credentials sealed by
    # SecretStore (app/core/secret_store.py, same convention as every other service's operator
    # credential), keyed "whatsapp_cloud_api_token:{tenant}". This is only the API version/base.
    META_GRAPH_API_BASE: str = "https://graph.facebook.com"
    META_GRAPH_API_VERSION: str = "v19.0"

    # ── LLM (Gemini function calling) ────────────────────────────────────────
    LLM_DRIVER: str = "null"                 # null | gemini
    GEMINI_MODEL: str = "gemini-1.5-flash"
    GEMINI_API_KEY: str = ""                 # sealed via SecretStore in production; env for dev/test
    GEMINI_TIMEOUT_SECONDS: int = 20
    # The ONLY functions the model may call. Enforced twice: once by what we declare to Gemini's
    # function-calling API, once again server-side (core/tools.py) — a model that hallucinates a
    # tool name outside this list is rejected before any tool body runs.
    LLM_TOOL_ALLOWLIST: str = (
        "check_availability,propose_booking,get_customer_points_summary,suggest_redeemable_offer")

    @property
    def llm_tool_allowlist(self) -> frozenset[str]:
        return frozenset(t.strip() for t in self.LLM_TOOL_ALLOWLIST.split(",") if t.strip())

    def assert_llm_config_ok(self) -> None:
        if not self.is_production:
            return
        if self.LLM_DRIVER == "null":
            raise ValueError(
                "LLM_DRIVER=null in production: the assistant would receive every message and "
                "propose nothing — a receptionist that never answers.")
        if self.LLM_DRIVER == "gemini" and not self.GEMINI_API_KEY:
            raise ValueError("LLM_DRIVER=gemini but GEMINI_API_KEY is empty.")

    # ── conversation engine — debounce, session, summary (all config-driven) ─
    # Consecutive inbound messages inside this window are coalesced into ONE reply cycle — a
    # customer typing three short messages in a row must not receive three separate replies.
    CONVERSATION_DEBOUNCE_SECONDS: int = 180
    # A logical session closes on intent completion OR this much silence — whichever comes first.
    CONVERSATION_SESSION_TIMEOUT_SECONDS: int = 2400
    # How many raw messages are kept verbatim before being folded into the rolling summary. Bounds
    # LLM context/cost — the transcript is never sent whole, only this window plus the summary.
    CONVERSATION_RAW_WINDOW_MESSAGES: int = 12
    # A tick (see core/conversation.py Ticker) sweeps for debounce-window-elapsed and
    # session-timeout-elapsed conversations at this cadence.
    CONVERSATION_TICK_SECONDS: int = 30

    # ── availability / booking (ConfigDrivenAvailabilityProvider) ────────────
    # THE DEFAULT ADAPTER, self-contained — no external booking service. JSON so shape can vary
    # per tenant without a schema migration; see core/booking.py for the parsed structure.
    # {"sun": ["09:00-17:00"], "mon": ["09:00-17:00"], ...} — day keys are 3-letter lowercase.
    BOOKING_DEFAULT_BUSINESS_HOURS_JSON: str = (
        '{"sun":["09:00-21:00"],"mon":["09:00-21:00"],"tue":["09:00-21:00"],'
        '"wed":["09:00-21:00"],"thu":["09:00-21:00"],"fri":["14:00-21:00"],"sat":["09:00-21:00"]}')
    # Minutes. A DEFAULT service duration used when a tenant's own catalogue (read from operations,
    # like reminders reads OPERATIONS_CATALOGUE_PATH) does not declare one for a service.
    BOOKING_DEFAULT_SERVICE_DURATION_MINUTES: int = 30
    # How many concurrent bookings one shop can hold in the same slot — a single-bay wash is 1; a
    # multi-bay shop configures higher. A DEFAULT, overridable per tenant in the same JSON blob.
    BOOKING_DEFAULT_CONCURRENCY: int = 1
    # How far ahead a customer may book. Unbounded availability reads as an infinite calendar and
    # invites a proposal for a date the shop has not planned staffing for.
    BOOKING_MAX_LEAD_DAYS: int = 30
    BOOKING_SLOT_GRANULARITY_MINUTES: int = 15

    # ── pricing (app/core/pricing.py) — SHAPE only, not a final decision ─────
    # Which strategy is active. tier_plus_cap | addon_on_existing_plan | usage_based. See the
    # module docstring: this is scaffolding for a pricing conversation, not a shipped price list.
    PRICING_STRATEGY: str = "tier_plus_cap"
    PRICING_TIER_BASE_HALALAS: int = 0
    PRICING_TIER_INCLUDED_CONVERSATIONS: int = 0
    PRICING_TIER_OVERAGE_HALALAS_PER_CONVERSATION: int = 0
    PRICING_ADDON_FLAT_HALALAS: int = 0
    PRICING_USAGE_HALALAS_PER_1K_TOKENS: int = 0
    PRICING_USAGE_HALALAS_PER_CONVERSATION: int = 0

    # ── ceilings / rate limits specific to this service ──────────────────────
    # Bounded work per tick — an unbounded sweep of due conversations is how a slow query becomes
    # a missed batch, exactly as in reminders' TICK_BATCH_SIZE.
    CONVERSATION_TICK_BATCH_SIZE: int = 200
    # Outbound sends per tenant per rolling window — belt beside notification-service's own ceiling
    # (spec parity with reminders' REACH_WINDOW/CEILING), so a runaway conversation loop cannot
    # spend a shop's whole WhatsApp allowance by itself.
    OUTBOUND_MAX_PER_TENANT_PER_HOUR: int = 200
    # Longest a single conversation may run before it is forcibly closed regardless of activity —
    # a safety ceiling under the session timeout, not a replacement for it.
    CONVERSATION_MAX_DURATION_SECONDS: int = 14_400

    # ── Ports & adapters — driver selection, ZERO-INFRA defaults ────────────
    DATASTORE_DRIVER: str = "memory"
    DATASTORE_DSN: str = ""
    DATASTORE_POOL_MIN: int = 1
    DATASTORE_POOL_MAX: int = 5
    DATASTORE_POOL_TIMEOUT_SECONDS: float = 10.0
    DATASTORE_POOL_MAX_INACTIVE_LIFETIME_SECONDS: float = 300.0

    CACHE_DRIVER: str = "memory"
    CACHE_URL: str = ""

    # Must match notification-service's own EVENTBUS_URL in any deployment where this service is
    # meant to actually receive whatsapp.message/whatsapp.status — the bus is in-process pub/sub
    # per broker instance, not a durable topic (see app/ports/event_bus.py).
    EVENTBUS_DRIVER: str = "memory"
    EVENTBUS_URL: str = ""

    QUEUE_DRIVER: str = "memory"
    QUEUE_URL: str = ""

    OBJECTSTORE_DRIVER: str = "local"
    OBJECTSTORE_ROOT: str = "/tmp/objectstore"  # nosec B108
    OBJECTSTORE_BUCKET: str = ""
    OBJECTSTORE_ENDPOINT_URL: str = ""
    OBJECTSTORE_ACCESS_KEY: str = ""
    OBJECTSTORE_SECRET_KEY: str = ""
    OBJECTSTORE_REGION: str = ""
    OBJECTSTORE_FORCE_PATH_STYLE: bool = False

    SECRETS_DRIVER: str = "env"
    SECRETS_FILE: str = ""
    VAULT_ADDR: str = ""
    VAULT_TOKEN: str = ""
    VAULT_PATH: str = ""

    TOKEN_VERIFIER_DRIVER: str = "null"
    TOKEN_ISSUER: str = ""
    TOKEN_AUDIENCE: str = ""
    TOKEN_HS256_SECRET: str = ""
    TOKEN_PUBLIC_KEY: str = ""
    TOKEN_JWKS_URL: str = ""

    RATELIMITER_DRIVER: str = "memory"
    RATELIMIT_URL: str = ""
    RATELIMIT_MAX: int = 100
    RATELIMIT_WINDOW_SECONDS: int = 60
    RATELIMIT_DEGRADE: str = "local"
    RATELIMIT_KEY_PARTS: str = "subject,ip"
    RATELIMIT_ROUTES: str = ""
    RATELIMIT_COUNT_STATUSES: str = ""

    TELEMETRY_DRIVER: str = "stdout"

    CWE_GUARD_ENABLED: bool = True
    EGRESS_ALLOWED_HOSTS: str = ""
    CWE_STEP_MAP_FILE: str = ""

    @property
    def egress_allowed_hosts(self) -> frozenset[str]:
        return frozenset(h.strip().lower() for h in self.EGRESS_ALLOWED_HOSTS.split(",") if h.strip())

    @property
    def is_test(self) -> bool:
        return self.ENV == "test"

    @property
    def is_production(self) -> bool:
        return self.ENV == "production"

    @property
    def audit_ingest_url(self) -> str:
        if not self.AUDIT_SERVICE_URL:
            return ""
        return self.AUDIT_SERVICE_URL.rstrip("/") + self.AUDIT_INGEST_PATH


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
