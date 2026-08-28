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
    # Seals any operator-managed per-tenant credential this service holds through SecretStore
    # (app/core/secret_store.py — same class services/reminders and services/loyalty import
    # unmodified). Nothing sealed under it today: the one credential that used to live here — a
    # per-tenant WhatsApp Cloud API token — was retired with InteractiveNotifySender (see
    # app/adapters/whatsapp_sender/direct.py); kept as a general facility for the next operator
    # credential this service needs to hold.
    SECRETS_KEK: str = ""
    # Seals backup archives at rest. SEPARATE from SECRETS_KEK by design: restoring must not
    # require the key this service uses for its own sealed operator credentials.
    # Empty means this service cannot produce a backup, and its export endpoint refuses rather
    # than writing one in the clear. SHARED: it must be the SAME value backup-service holds (in
    # the class of PII_SALT / INTERNAL_SERVICE_TOKEN) — see services/loyalty/app/config.py.
    BACKUP_KEK: str = ""
    # The most rows a single collection may hold before a backup FAILS rather than reads on
    # unbounded — same convention as loyalty/reminders, not a number chosen for this service.
    BACKUP_MAX_ROWS_PER_COLLECTION: int = 5_000_000

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
    # Fail closed: a booking confirm must not proceed unwitnessed. See
    # app/auditable_actions.py — the actions marked critical there.
    AUDIT_FAIL_CLOSED: bool = True

    def assert_audit_config_ok(self) -> None:
        if not self.is_production:
            return
        if self.AUDIT_SINK_DRIVER == "null":
            raise ValueError(
                "AUDIT_SINK_DRIVER=null in production: a booking confirmed by this assistant "
                "would happen with no record of who (or what) triggered it.")
        if self.AUDIT_SINK_DRIVER == "http" and not self.AUDIT_SERVICE_URL:
            raise ValueError("AUDIT_SINK_DRIVER=http but AUDIT_SERVICE_URL is empty.")

    def assert_pii_config_ok(self) -> None:
        if self.is_production and not self.PII_SALT:
            raise ValueError(
                "PII_SALT is empty in production: the opaque per-conversation reference handed to "
                "the LLM (see core/conversation.py) is derived from it — without a salt the "
                "reference would be reversible or absent.")

    # ── consent (compliance-service) ─────────────────────────────────────────
    # ports/consent_gate.py was wired into this container from day one and never actually asked —
    # the same defect its own docstring names across all nineteen other services on this platform.
    # This is the first real caller: app/core/inbound_ingest.py checks BEFORE the raw phone number
    # is folded into subject_ref and discarded (the port needs the raw subject; a service holding
    # only a pseudonym structurally cannot use it — see the port's own docstring on that point).
    CONSENT_GATE_DRIVER: str = "null"        # null | http
    COMPLIANCE_SERVICE_URL: str = ""
    # WHAT WE ARE ASKING PERMISSION FOR — not "may we message you" (WhatsApp's own opt-in already
    # covers that; this platform did not invent WhatsApp messaging) but "may we run this specific
    # AI processing on what you send": retained raw text for up to CHAT_RETENTION_DAYS, sent to a
    # third-party model (Gemini/Google), used to read your loyalty balance and propose actions on
    # your behalf. A materially different processing purpose from ordinary transactional messages.
    CONSENT_PURPOSE: str = "whatsapp_ai_assistant"
    # FAIL_OPEN, NOT FAIL_CLOSED — and this is a real product decision, not a default nobody
    # thought about: the customer TEXTED THE SHOP FIRST. Refusing to answer him because
    # compliance-service could not be reached (UNKNOWN) reads as "the shop's WhatsApp appears
    # broken from unrelated infra", not as caution — the same "refusing to serve a user's own
    # profile under unknown is an outage" case the port's own docstring names. Reconsider this
    # once real consent RECORDS exist for this purpose (today: zero, anywhere — flipping to
    # fail_closed before then would silently refuse every conversation on this platform).
    CONSENT_POLICY_ON_UNKNOWN: str = "fail_open"   # fail_open | fail_closed
    # A DENIED verdict (real: consent withdrawn/expired on record) is never fail_open — an explicit
    # withdrawal has to hold regardless of policy, or the policy toggle would be able to override a
    # subject's own choice. Not configurable, on purpose.

    def assert_consent_config_ok(self) -> None:
        if not self.is_production:
            return
        if self.CONSENT_GATE_DRIVER == "null":
            raise ValueError(
                "CONSENT_GATE_DRIVER=null in production: every customer conversation would be "
                "processed with nobody ever asked whether they consented to it.")
        if self.CONSENT_GATE_DRIVER == "http" and not self.COMPLIANCE_SERVICE_URL:
            raise ValueError("CONSENT_GATE_DRIVER=http but COMPLIANCE_SERVICE_URL is empty.")
        if self.CONSENT_POLICY_ON_UNKNOWN not in ("fail_open", "fail_closed"):
            raise ValueError(
                f"CONSENT_POLICY_ON_UNKNOWN={self.CONSENT_POLICY_ON_UNKNOWN!r} — must be "
                f"'fail_open' or 'fail_closed'.")

    # ── peers this service depends on ────────────────────────────────────────
    # THEIRS. notification-service is where inbound WhatsApp messages are received, verified and
    # published (`whatsapp.message`, `whatsapp.status`) and where TEMPLATE-ONLY outbound sends go.
    NOTIFICATION_SERVICE_URL: str = ""
    NOTIFICATION_SEND_PATH: str = "/internal/notify"
    # Interactive button/list sends (app/adapters/whatsapp_sender/direct.py::InteractiveNotifySender)
    # — resolved via platform v0.16.38, commit 0c54f5e. See app/ports/whatsapp_sender.py.
    NOTIFICATION_INTERACTIVE_SEND_PATH: str = "/internal/notify/whatsapp/interactive"
    # The durable, replayable catch-up read for inbound WhatsApp messages (app/core/inbound_poll.py)
    # — resolved via platform v0.16.38, commit 31e556e. See app/api/internal.py's tick route.
    NOTIFICATION_INBOUND_PATH: str = "/internal/whatsapp/inbound"
    # Rows requested per catch-up page. Same bound-per-request reasoning as reminders'
    # HttpReceiptFeed's `page` — a page too large turns one tick into a slow, unbounded fetch.
    INBOUND_POLL_PAGE_SIZE: int = 200
    # Pages walked per tick before the sweep yields — bounds one tenant's backlog from starving
    # every other tenant's tick, same convention as reminders' Receipts._max_pages.
    INBOUND_POLL_MAX_PAGES: int = 20

    # operations — customer recognition (phone -> subject_ref) and visit-pattern summaries.
    OPERATIONS_SERVICE_URL: str = ""
    # ESCALATED: no phone->customer lookup existed anywhere in operations before this service. We
    # added the narrowest possible route, /internal/operations/customer-by-phone (reusing the
    # existing CustomerStore.by_phone — see services/operations/app/api/internal.py), returning a
    # pseudonym and a visit-count/last-visit PATTERN only — never the phone or name back to us.
    OPERATIONS_CUSTOMER_BY_PHONE_PATH: str = "/internal/operations/customer-by-phone"
    OPERATIONS_CUSTOMER_VISITS_PATH: str = "/internal/operations/customer-visits"
    # The shop's display name, for the persona built in core/conversation.py::build_system_prompt —
    # see app/core/shop_identity.py and operations' own /internal/operations/shop-name docstring for
    # why this reads the main branch's name rather than the tenant registry's.
    OPERATIONS_SHOP_NAME_PATH: str = "/internal/operations/shop-name"
    # Central-number branch-selection gate (core/branch_directory.py) — a shop's OPEN branches,
    # id/name/city only. Separate route from the pre-existing insights one on purpose; see
    # services/operations/app/api/internal.py::read_active_branches's own docstring.
    OPERATIONS_ACTIVE_BRANCHES_PATH: str = "/internal/operations/active-branches"
    # The shop's REAL, priced service list — sent to the model IN FULL (never PII, see
    # app/core/service_catalog.py's module docstring) so it can answer "how much" and cross-sell
    # honestly instead of guessing.
    OPERATIONS_CATALOGUE_WITH_PRICES_PATH: str = "/internal/operations/catalogue-with-prices"
    # Real booking assignment (core/booking_assignment.py, Phase 4) — the branch's own active
    # people, and which services a customer's picked one may perform. Neither invents an
    # assignment on its own; see booking_assignment.py's own module docstring for the full policy.
    OPERATIONS_BRANCH_OPERATORS_PATH: str = "/internal/operations/branch-operators"
    OPERATIONS_SERVICE_ELIGIBILITY_PATH: str = "/internal/operations/service-eligibility"
    # Real booking assignment's OTHER question: a real, durable `customer_id` for this phone —
    # never the pseudonym `customer-by-phone` deliberately withholds it from. See that route's own
    # docstring in services/operations/app/api/internal.py for why this is a SEPARATE door.
    OPERATIONS_CUSTOMER_ID_BY_PHONE_PATH: str = "/internal/operations/customer-id-by-phone"

    # bookings — real slot search and real booking creation (Phase 4). Empty by default: an
    # unconfigured deployment keeps BOOKING_PROVIDER_DRIVER="config" (see core/booking.py) and
    # never reaches this peer at all — see BOOKING_PROVIDER_DRIVER's own note below.
    BOOKINGS_SERVICE_URL: str = ""
    BOOKINGS_NEAREST_REAL_SLOT_PATH: str = "/internal/bookings/nearest-real-slot"
    BOOKINGS_CREATE_PATH: str = "/internal/bookings"
    # "config" (default): the zero-infra placeholder, ConfigDrivenAvailabilityProvider — writes
    # into THIS service's own store, never a real bookings/operations peer (see core/booking.py's
    # own docstring). "real": core/booking_assignment.py's RealBookingProvider — real branch
    # operators, real eligibility, a real customer_id, and a real bookings-service booking. Never
    # defaults to "real" on its own: an operator must choose it once bookings-service is actually
    # deployed and reachable, the same "opt in, never silently upgrade" posture WALLET_SERVICE_URL
    # and every other optional peer on this service already takes.
    BOOKING_PROVIDER_DRIVER: str = "config"

    # loyalty — points summaries only (read-only; see core/points.py's own docstring on why this
    # service no longer redeems anything directly — a reward rides on a real booking instead).
    LOYALTY_SERVICE_URL: str = ""
    LOYALTY_BALANCE_PATH: str = "/internal/loyalty/portal/balance"

    # insights — cross-sell suggestions during an AI-led booking conversation, reusing the SAME
    # association engine (services/insights/app/core/associations.py) staff already see via
    # apps/console/src/ServiceGrid.tsx's `together` prop. Never a new recommendation algorithm —
    # a read of an existing, plan-gated one. See app/core/related_services.py and
    # services/insights/app/api/internal.py::associated_services for the plan-gate detail (a
    # tenant without the "associations" plan feature gets an empty list here too, same as the
    # dashboard — this route is not a bypass of that paywall).
    INSIGHTS_SERVICE_URL: str = ""
    INSIGHTS_ASSOCIATED_SERVICES_PATH: str = "/internal/insights/associated-services"

    # wallet-service — the real operational stop condition (distinct from human escalation): a
    # shop with no available funds beyond its plan's included quota gets the AI stopped entirely,
    # not handed to a human. Authorization-HOLD pattern (reserve before the costed action, confirm
    # or release after) via wallet-service's own reserve/confirm/release routes — see
    # app/core/wallet_balance.py's module docstring for the full reasoning, including why this is
    # the one peer in this service that fails CLOSED on an outage rather than open.
    WALLET_SERVICE_URL: str = ""
    WALLET_SERVICE_RESERVE_PATH: str = "/internal/wallet/reserve"
    WALLET_SERVICE_CONFIRM_PATH: str = "/internal/wallet/confirm"
    WALLET_SERVICE_RELEASE_PATH: str = "/internal/wallet/release"
    # A GENEROUS per-turn ceiling, not a precise estimate — priced at the same real usage rate
    # (PRICING_USAGE_HALALAS_PER_1K_TOKENS below) that is this service's actual cost basis. Sized
    # to comfortably cover CONVERSATION_RAW_WINDOW_MESSAGES worth of context plus a normal reply;
    # revisit once real usage data exists (see core/pricing.py's own "not a final decision" note).
    WALLET_ESTIMATED_MAX_TOKENS_PER_TURN: int = 4000
    # THE HARD SAFETY MARGIN (halalas — 100 = 1 SAR) held back on TOP of the token estimate on
    # every reserve, so a misestimate or a mid-flight rate change can never itself be what pushes
    # a confirm past the true available balance. Config, not a literal in the reserve call itself.
    WALLET_SAFETY_MARGIN_HALALAS: int = 100

    @field_validator("WALLET_ESTIMATED_MAX_TOKENS_PER_TURN", "WALLET_SAFETY_MARGIN_HALALAS")
    @classmethod
    def _reject_negative_wallet_numbers(cls, v: int) -> int:
        if v < 0:
            raise ValueError("wallet hold sizing must be zero or positive — a negative estimate "
                             "or margin would UNDER-reserve, which is exactly the negative-balance "
                             "risk this exists to close")
        return v

    # NO ticket-service INTEGRATION, DELIBERATELY. An earlier version opened a ticket-service
    # ticket on human escalation — a real design error, corrected after checking ticket-service's
    # actual consumer: no screen anywhere in apps/console/src wires to it, and its own phase doc
    # (platform/docs/phases/phase-53-ticket-service.md) frames its first use as a SHOP raising a
    # ticket TO RAJE3'S OWN SUPPORT TEAM. A ticket opened here would reach Raje3's support queue,
    # never the salon's own receptionist. See app/core/conversation.py::_escalate_to_human's
    # docstring for what escalation actually does instead (rely on the shop's WhatsApp number
    # being provisioned in Meta's "coexistence" mode, confirmed in
    # platform/services/notification-service/app/api/webhooks.py's own docstring — the shop's
    # staff already see the same inbound messages directly in the WhatsApp Business App).

    PEER_TIMEOUT_SECONDS: int = 8

    # ── LLM (Gemini function calling) ────────────────────────────────────────
    LLM_DRIVER: str = "null"                 # null | gemini
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"
    GEMINI_API_KEY: str = ""                 # sealed via SecretStore in production; env for dev/test
    GEMINI_TIMEOUT_SECONDS: int = 20
    # The ONLY functions the model may call. Enforced twice: once by what we declare to Gemini's
    # function-calling API, once again server-side (core/tools.py) — a model that hallucinates a
    # tool name outside this list is rejected before any tool body runs.
    LLM_TOOL_ALLOWLIST: str = (
        "check_availability,propose_booking,get_customer_points_summary,suggest_redeemable_offer,"
        "suggest_related_service")

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

    # ── frustration escalation (core/frustration.py) ──────────────────────────
    # NO RAW TURN-COUNT CEILING, DELIBERATELY — a conversation continues however many turns it
    # takes; only a genuine frustration/repetition signal (below), a direct request for a human, a
    # triage complaint pick, or the wallet running out (WALLET_SERVICE_URL below) stop the AI.
    # EARLY escalation signal #1: a tool-proposal (propose_booking/suggest_redeemable_offer) still
    # sitting unconfirmed while the customer keeps typing instead of pressing a button, this many
    # times, reads as the assistant offering something the customer will not accept.
    FRUSTRATION_UNCONFIRMED_PROPOSALS_THRESHOLD: int = 2
    # EARLY escalation signal #2: the same (normalized) customer message appearing this many times
    # in the raw window reads as "the bot did not understand me the first time".
    FRUSTRATION_DUPLICATE_MESSAGES_THRESHOLD: int = 3

    @field_validator("FRUSTRATION_UNCONFIRMED_PROPOSALS_THRESHOLD",
                     "FRUSTRATION_DUPLICATE_MESSAGES_THRESHOLD")
    @classmethod
    def _reject_nonpositive_escalation_thresholds(cls, v: int) -> int:
        if v <= 0:
            raise ValueError(
                "escalation thresholds must be positive — zero or negative would escalate every "
                "single turn (or never validate at all), neither of which is the tunable ceiling "
                "this field exists to be")
        return v

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

    # ── chat data retention (app/core/retention.py) ──────────────────────────
    # How long a closed conversation's raw text (inbound messages + conversation state/summary) is
    # kept before being purged, counted from SESSION CLOSE — not per message. 30 days is the
    # DEFAULT: long enough to resolve a booking dispute raised after the visit, short enough that
    # this service does not become an indefinite store of customer chat content. See LegalGate/
    # privacy text for the customer-facing statement of this same number.
    CHAT_RETENTION_DAYS: int = 30
    # Bounded work per retention tick, same reasoning as CONVERSATION_TICK_BATCH_SIZE — an
    # unbounded purge sweep is how one tenant's backlog starves every other tenant's tick.
    CHAT_RETENTION_TICK_BATCH_SIZE: int = 200
    # Ceiling on rows scanned/deleted in one DSAR erasure pass (app/core/erasure.py) — a DSAR is
    # rare but must never become an unbounded read, same convention as reminders' ERASURE_MAX_SCAN.
    ERASURE_MAX_SCAN: int = 100_000

    @field_validator("CHAT_RETENTION_DAYS")
    @classmethod
    def _reject_nonsensical_retention(cls, v: int) -> int:
        if v <= 0:
            raise ValueError(
                "CHAT_RETENTION_DAYS must be positive — zero or negative would purge a "
                "conversation's raw content before (or as) it closes, defeating the dispute-"
                "resolution window this retention period exists for")
        return v

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
