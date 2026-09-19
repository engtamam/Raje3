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
    # job-service push-dispatch verification (app/core/push_verify.py) — empty means "verify
    # against INTERNAL_SERVICE_TOKEN instead", the SAME fallback job-service's own dispatcher uses
    # when ITS OWN PUSH_SIGNING_SECRET is unset, so the two sides agree by default with nothing
    # extra to configure.
    PUSH_SIGNING_SECRET: str = ""
    PUSH_SIGNATURE_MAX_SKEW_SECONDS: int = 300
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

    # ── Connector API (app/api/v1/connectors.py) — EXTERNAL auth, never INTERNAL_SERVICE_TOKEN ────
    # 2026-09-19: a Meta Business Agent Connector calls this service directly, over the public
    # internet, per its own registered OpenAPI spec. This is NOT a peer inside our own fleet the
    # way every INTERNAL_SERVICE_TOKEN caller is — a deliberately SEPARATE secret, so a leak of one
    # never widens the other's blast radius (this token can only ever invoke the 16 read/propose
    # tool endpoints and the confirm endpoint, none of which are internal-service operations).
    # Empty means the router is NOT MOUNTED AT ALL (see app/main.py) — degrade to "the feature does
    # not exist", never to "any caller with an empty header is accepted".
    CONNECTOR_API_TOKEN: str = ""

    @field_validator("CONNECTOR_API_TOKEN")
    @classmethod
    def _reject_connector_token_placeholder(cls, v: str) -> str:
        lowered = v.strip().lower()
        if lowered.startswith("placeholder") or lowered in {"changeme", "change_me"}:
            raise ValueError("CONNECTOR_API_TOKEN is a placeholder — set a real secret")
        return v

    def assert_connector_config_ok(self) -> None:
        if self.is_production and self.CONNECTOR_API_TOKEN and len(self.CONNECTOR_API_TOKEN) < 32:
            raise ValueError(
                "CONNECTOR_API_TOKEN is set but under 32 characters — the same minimum "
                "INTERNAL_SERVICE_TOKEN enforces, for an externally-reachable secret this must "
                "hold to at least as strictly.")

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
    # A real media-card carousel (app/adapters/whatsapp_sender/carousel.py::CarouselSender) —
    # both routes already exist and are already used by other carousel senders on the platform.
    NOTIFICATION_CAROUSEL_SEND_PATH: str = "/internal/notify/whatsapp/carousel"
    NOTIFICATION_MEDIA_UPLOAD_ID_PATH: str = "/internal/whatsapp/media/upload-id"
    # The durable, replayable catch-up read for inbound WhatsApp messages (app/core/inbound_poll.py)
    # — resolved via platform v0.16.38, commit 31e556e. See app/api/internal.py's tick route.
    NOTIFICATION_INBOUND_PATH: str = "/internal/whatsapp/inbound"
    # Rows requested per catch-up page. Same bound-per-request reasoning as reminders'
    # HttpReceiptFeed's `page` — a page too large turns one tick into a slow, unbounded fetch.
    INBOUND_POLL_PAGE_SIZE: int = 200
    # Pages walked per tick before the sweep yields — bounds one tenant's backlog from starving
    # every other tenant's tick, same convention as reminders' Receipts._max_pages.
    INBOUND_POLL_MAX_PAGES: int = 20

    # WhatsApp COEXISTENCE (a shop keeps using its own WhatsApp Business app on the SAME number it
    # connected to us) — platform v0.18.56. OFF by default, and meant to flip together with
    # notification-service's own WHATSAPP_COEXISTENCE_ENABLED at install time (deploy/bring-up.sh):
    # this flag decides whether THIS service polls the echo feed at all, not whether the platform
    # records echoes. See app/core/coexistence_poll.py and app/core/owner_presence.py.
    WHATSAPP_COEXISTENCE_ENABLED: bool = False
    NOTIFICATION_COEXISTENCE_ECHOES_PATH: str = "/internal/whatsapp/coexistence/echoes"
    COEXISTENCE_POLL_PAGE_SIZE: int = 200
    COEXISTENCE_POLL_MAX_PAGES: int = 20
    # How long the AI stays quiet on a customer after the owner answers them by hand from their own
    # phone — long enough to cover one real back-and-forth, short enough that a single manual reply
    # never silences the assistant on that customer for the rest of the day. 0 disables the
    # suppression (echoes are still polled and recorded upstream; nothing here would act on them).
    COEXISTENCE_HUMAN_COOLDOWN_SECONDS: int = 1800

    # operations — customer recognition (phone -> subject_ref) and visit-pattern summaries.
    # identity-service — the subscription-renewal trigger's ONE read: the tenant's founding
    # owner's own login identifier (platform v0.19.13), to send the renewal Flow to. Empty ⇒ the
    # trigger cannot resolve a recipient and simply does not send (never a fake/guessed number —
    # see core/owner_phone.py).
    IDENTITY_SERVICE_URL: str = ""
    IDENTITY_OWNER_PHONE_PATH: str = "/internal/tenancy/owner-phone"

    OPERATIONS_SERVICE_URL: str = ""
    # ESCALATED: no phone->customer lookup existed anywhere in operations before this service. We
    # added the narrowest possible route, /internal/operations/customer-by-phone (reusing the
    # existing CustomerStore.by_phone — see services/operations/app/api/internal.py), returning a
    # pseudonym and a visit-count/last-visit PATTERN only — never the phone or name back to us.
    OPERATIONS_CUSTOMER_BY_PHONE_PATH: str = "/internal/operations/customer-by-phone"
    # Read on every turn from a number `customer-by-phone` does not already recognise, BEFORE ever
    # calling OPERATIONS_CUSTOMER_ID_BY_PHONE_PATH below for real — OFF for every tenant until its
    # owner opts in explicitly (services/operations' own core/whatsapp_auto_register.py has the
    # full reasoning). "Opt in, never silently widen who gets written into the customer book" is
    # the same posture every owner-facing trust switch on this service already holds.
    OPERATIONS_WHATSAPP_AUTO_REGISTER_PATH: str = "/internal/operations/whatsapp-auto-register"
    # NOT DECLARED: a "customer-visits" path was published here once, alongside this one, and
    # nothing in this service ever called it — `customer_lookup.py` only ever asks
    # OPERATIONS_CUSTOMER_BY_PHONE_PATH above (which already returns visit_count_90d bundled in
    # that one response). Deleted rather than wired: giving the assistant its own separate
    # full-visit-history read is a real feature (what would it DO with it?), not a config fix.
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
    OPERATIONS_PACKAGES_PATH: str = "/internal/operations/packages"
    # ONE service's own ordered protocol (`Service.procedure_step_ids` resolved to real step text
    # + severity) — the `get_service_procedure` tool's own read, called one service at a time by
    # design (see core/service_procedure.py's own module docstring for why never the whole
    # catalogue in one call).
    OPERATIONS_SERVICE_PROCEDURE_PATH: str = "/internal/operations/service-procedure"
    # The mobile/on-the-go service-requests creation door (services/operations/app/api/internal.py)
    # — the one write core/tools.py's `request_mobile_visit` tool + core/conversation.py's
    # `handle_location` make together. Reuses OPERATIONS_SERVICE_URL like every other operations
    # peer call here; withheld from the model entirely (see llm_tool_allowlist below) whenever that
    # URL is empty, same "withheld, not offered-and-refused" posture as the carousel/rhythm tools.
    OPERATIONS_MOBILE_REQUESTS_PATH: str = "/internal/operations/mobile-requests"
    # The read `check_mobile_visit_hours` makes before `request_mobile_visit` is ever proposed —
    # the shop's own real weekly working hours (services/operations/app/api/internal.py::
    # internal_mobile_visit_hours, itself a thin proxy over bookings' own working-hours read).
    OPERATIONS_MOBILE_VISIT_HOURS_PATH: str = "/internal/operations/mobile-visit-hours"
    # The photo behind a CatalogCard (app/ports/catalog_provider.py) — `{}`/`{}` are `kind`/
    # `item_id`, filled in per card by PlatformCatalogProvider, never templated at request time.
    OPERATIONS_CATALOGUE_IMAGE_PATH: str = "/internal/operations/catalogue/{}/{}/image"
    # null (no provider wired) | platform (our own services/packages, images included). See
    # app/ports/catalog_provider.py's own docstring — infrastructure only, no consumer wired yet.
    CATALOG_PROVIDER_DRIVER: str = "null"

    # reminders — the same real, learned per-(customer, service) rhythm reminders' own tick already
    # schedules on (core/adaptive.py there), read here to feed list_due_services/list_lapsed_
    # services (core/tools.py). null (no provider wired, both tools always answer "nothing") | http.
    RHYTHM_PROVIDER_DRIVER: str = "null"
    REMINDERS_SERVICE_URL: str = ""
    REMINDERS_RHYTHM_PATH: str = "/internal/reminders/rhythm-for-subject"
    # `check_active_offers` (core/tools.py) — the SAME read reminders already answers for a
    # customer's own public offers page (core/active_offers.py's own module docstring).
    REMINDERS_PORTAL_OFFERS_PATH: str = "/internal/reminders/portal/offers"
    # Real booking assignment (core/booking_assignment.py, Phase 4) — the branch's own active
    # people, and which services a customer's picked one may perform. Neither invents an
    # assignment on its own; see booking_assignment.py's own module docstring for the full policy.
    OPERATIONS_BRANCH_OPERATORS_PATH: str = "/internal/operations/branch-operators"
    OPERATIONS_SERVICE_ELIGIBILITY_PATH: str = "/internal/operations/service-eligibility"
    OPERATIONS_PACKAGE_ELIGIBILITY_PATH: str = "/internal/operations/package-eligibility"
    # Real booking assignment's OTHER question: a real, durable `customer_id` for this phone —
    # never the pseudonym `customer-by-phone` deliberately withholds it from. See that route's own
    # docstring in services/operations/app/api/internal.py for why this is a SEPARATE door.
    OPERATIONS_CUSTOMER_ID_BY_PHONE_PATH: str = "/internal/operations/customer-id-by-phone"

    # bookings — real slot search and real booking creation (Phase 4). Empty by default: an
    # unconfigured deployment keeps BOOKING_PROVIDER_DRIVER="config" (see core/booking.py) and
    # never reaches this peer at all — see BOOKING_PROVIDER_DRIVER's own note below.
    BOOKINGS_SERVICE_URL: str = ""
    BOOKINGS_NEAREST_REAL_SLOT_PATH: str = "/internal/bookings/nearest-real-slot"
    # THE REAL ASSIGNMENT ENGINE (assignment-mode redesign, phase 4) — merges across every
    # eligible operator and applies the shop's own algorithm (AssignmentSettingsStore), replacing
    # the "sorted by id, first one" placeholder `_pick_operator` used before this existed.
    BOOKINGS_NEAREST_ANY_REAL_SLOT_PATH: str = "/internal/bookings/nearest-any-real"
    # PHASE 5 (WhatsApp Flow) — the TIME screen's own question: every time on ONE day at least one
    # eligible operator is free for, never who. See core/flow_booking_backend.py's own docstring.
    BOOKINGS_DAY_SLOTS_ANY_REAL_PATH: str = "/internal/bookings/day-slots-real"
    BOOKINGS_CREATE_PATH: str = "/internal/bookings"
    # Booking-management-via-WhatsApp (view/cancel/reschedule an EXISTING booking) — the
    # customer-ownership counterparts to bookings-service's staff-only routes. See
    # services/bookings/app/api/internal.py's own "customer self-service" section.
    BOOKINGS_FOR_CUSTOMER_PATH: str = "/internal/bookings/for-customer"
    BOOKINGS_CANCEL_PATH: str = "/internal/bookings/{booking_id}/cancel"
    BOOKINGS_RESCHEDULE_PATH: str = "/internal/bookings/{booking_id}/reschedule"
    # Growth reporting's own read — every booking a given actor (this service's own ACTOR constant,
    # "whatsapp-assistant") made, for invoice_report.py's average-invoice-value stat. See that
    # module's own docstring and bookings-service's api/internal.py `InternalByActorIn`.
    BOOKINGS_BY_ACTOR_PATH: str = "/internal/bookings/by-actor"
    # "config" (default): the zero-infra placeholder, ConfigDrivenAvailabilityProvider — writes
    # into THIS service's own store, never a real bookings/operations peer (see core/booking.py's
    # own docstring). "real": core/booking_assignment.py's RealBookingProvider — real branch
    # operators, real eligibility, a real customer_id, and a real bookings-service booking. Never
    # defaults to "real" on its own: an operator must choose it once bookings-service is actually
    # deployed and reachable, the same "opt in, never silently upgrade" posture WALLET_SERVICE_URL
    # and every other optional peer on this service already takes.
    BOOKING_PROVIDER_DRIVER: str = "config"
    # The shop's weekly working-hours policy (bookings-service's own store, the SAME one the
    # console's own calendar reads) — feeds the Flow CALENDAR step's include_days/unavailable
    # constraints. See core/flow_booking_backend.py.
    BOOKINGS_WORKING_HOURS_PATH: str = "/internal/working-hours"

    # PHASE 5 — the WhatsApp Flow (structured screens) booking channel, distinct from the AI text
    # channel above (BOOKING_PROVIDER_DRIVER). Off by default: the platform's own generic Flow
    # infrastructure (v0.18.54+) POSTs to a URL WE configure on THEIR side once this is on; turning
    # it on here only builds our half (the endpoint answering those calls) — see
    # core/flow_booking_backend.py and api/internal.py's /internal/whatsapp-flow/booking route.
    # Requires BOOKING_PROVIDER_DRIVER="real" (reuses the exact same peers/engine, never a second
    # policy) — checked at build() time, same fail-fast posture as every other combined-config
    # assertion on this service.
    WHATSAPP_FLOW_BOOKING_ENABLED: bool = False

    # Booking-management-via-WhatsApp — view/cancel/reschedule an EXISTING booking through the
    # bot. TWO INDEPENDENT FLAGS, both default true (fully on, for this round's testing), each
    # flippable with a plain config-value change and a restart — NO code edit, NO redeploy of new
    # code — the same "flip it off, no surgery" requirement every other kill-switch on this
    # service already meets.
    #
    # BOOKING_MANAGEMENT_ENABLED: the master switch for the whole capability (list/cancel/
    # reschedule together). False removes the three tools from `llm_tool_allowlist` below AND
    # stops booking_assignment.py::build() from even constructing the peers they'd need (belt and
    # suspenders — either one alone already prevents the model from ever reaching bookings-service
    # for this).
    BOOKING_MANAGEMENT_ENABLED: bool = True
    # THE MERGE-SIDE KILL SWITCH for shop-owner AI-assistant notes (build_system_prompt's
    # `owner_notes` section). operations.AI_NOTES_ENABLED already blanks the value at its own
    # source; this is a SECOND, independent switch — turning it off here stops the merge even if
    # the peer call still answers a non-empty value, no coordination with operations required, and
    # no code edit or redeploy of new code. False means every reply behaves exactly as it did
    # before this feature shipped.
    SHOP_NOTES_ENABLED: bool = True
    # THE MERGE-SIDE KILL SWITCH for the customer-message word limit (handle_inbound_text's own
    # gate, before any AI call). operations.MSG_WORD_LIMIT_ENABLED already answers
    # DEFAULT_MSG_WORD_LIMIT at its own source when off; this is a second, independent switch —
    # turning it off here lets every message through regardless of what the peer answers. False
    # means this reply behaves exactly as it did before this feature shipped.
    MSG_WORD_LIMIT_ENABLED: bool = True
    # BOOKING_HISTORY_VISIBLE: separate and narrower — governs ONLY whether `list_my_bookings` may
    # also show bookings BEFORE today (Riyadh business day). Current and upcoming bookings show
    # regardless of this flag; false does not hide anything happening today or later, it only
    # refuses a look further into the past — see core/tools.py::list_my_bookings for the exact
    # cutoff and the "ask a human for older bookings" refusal text it returns instead of silently
    # trimming or guessing.
    BOOKING_HISTORY_VISIBLE: bool = True

    # loyalty — points summaries only (read-only; see core/points.py's own docstring on why this
    # service no longer redeems anything directly — a reward rides on a real booking instead).
    LOYALTY_SERVICE_URL: str = ""
    LOYALTY_BALANCE_PATH: str = "/internal/loyalty/portal/balance"
    # The hypothetical points-comparison read `check_growth_opportunities` (core/growth.py) builds
    # on — never a spend, see that route's own docstring on loyalty's side.
    LOYALTY_EARN_PREVIEW_PATH: str = "/internal/loyalty/earn-preview"

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
    # A GENEROUS per-turn ceiling, not a precise estimate — sized to comfortably cover
    # CONVERSATION_RAW_WINDOW_MESSAGES worth of context plus a normal reply; revisit once real
    # usage data exists (see core/ai_unit_pricing.py for the actual cost basis this service prices
    # against).
    WALLET_ESTIMATED_MAX_TOKENS_PER_TURN: int = 4000
    # AN EXTRA HALALA AMOUNT (100 = 1 SAR) HELD BACK ON TOP OF THE TOKEN ESTIMATE on every
    # reserve — held, never spent unless actually needed: wallet-service v0.19.2's own
    # confirm(final_net=...) always charges the real, usually-smaller cost and auto-releases
    # whatever of the reserve (margin included) was not actually used.
    #
    # 0 IS THE RIGHT VALUE, DELIBERATELY, NOT A PLACEHOLDER. `reserve()` is already the one
    # atomic gate against overspending (wallet-service's own compare-and-set against the held
    # balance — see app/core/wallet_balance.py's module docstring), and `confirm()`'s final_net is
    # always clamped to what was reserved, so it can never itself push a charge past what reserve
    # already verified was available. A margin here does not add any protection that does not
    # already exist — its ONLY real effect is making the reserve check itself STRICTER: a shop
    # whose balance genuinely covers a turn's real cost, but sits just under the reserve's own
    # padded estimate, would be refused and see the AI stop replying for no real financial reason.
    # A positive margin here would be a real regression, not a safety net.
    WALLET_SAFETY_MARGIN_HALALAS: int = 0
    # THE NAMED FUND(S) this bot's own hold is scoped to (wallet-service v0.18.42's fund-scoping,
    # comma-separated — plural for a future deployment that ever needs more than one). Empty
    # means the historical all-funds behaviour. Set to the AI-usage credit fund's name once
    # wallet-service declares one — never left to wander into a shop's commission balance or its
    # subscription-renewal top-up, which the SAME wallet may also hold.
    WALLET_RESERVE_FUNDS: str = ""

    # THE PLATFORM'S OWN PUBLIC URL — for the top-up link in the low-balance owner notice
    # (core/wallet_low_balance_trigger.py). The owner logs in there and tops up normally; no
    # dedicated top-up page or auto-login token, by owner decision (2026-09-10) — simpler, cheaper,
    # and console already serves the whole platform from this one domain (deploy/edge/console.yaml).
    PUBLIC_BASE_URL: str = "https://kobo-cloud.com"

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

    # ── assistant-service (the LLM backend) ───────────────────────────────────────────────────
    ASSISTANT_SERVICE_URL: str = ""
    ASSISTANT_SERVICE_CONNECTIONS_PATH: str = "/internal/assistant/connections"
    ASSISTANT_SERVICE_TIMEOUT_SECONDS: int = 20
    # The underlying model EVERY tenant's connection points at — one platform-wide GCP project/
    # model/credential, not a per-tenant choice (see core/assistant_connections.py's own note on
    # why only system_prompt/tools vary per tenant). me-central2 (Dammam) per the sibling team's
    # own Saudi-residency guidance.
    #
    # PROJECT AND CREDENTIAL ARE THE ENV FALLBACK ONLY — no real GCP project exists yet at the
    # time this driver was wired in, so both are read live via SecretStore first
    # (app/adapters/llm/assistant_service.py's own _resolve_project/_resolve_credential), letting
    # an operator supply them later from «مفاتيح المزوّدين» with no redeploy.
    ASSISTANT_MODEL_PROJECT: str = ""
    ASSISTANT_MODEL_LOCATION: str = "me-central2"
    ASSISTANT_MODEL_NAME: str = "gemini-2.5-flash"
    ASSISTANT_MODEL_AUTH: str = "vertex"          # api_key | vertex
    ASSISTANT_MODEL_CREDENTIAL: str = ""          # a GCP service-account key JSON
    # A TECHNICAL COST CEILING, NOT A BUSINESS SETTING — unlike operations' own msg_word_limit
    # (per-shop, the owner's own choice about how long a CUSTOMER's message may be), this caps how
    # long the model's OWN reply may run, so one unusually rambling generation cannot cost many
    # times a normal reply's worth of output tokens (the pricier side — see the pricing calculator's
    # own note on output being ~8x input per token). No shop ever sees or sets this — live-tunable
    # by an operator only, through the same "النموذج والسلوك" runtime_config panel as
    # ASSISTANT_MODEL_NAME (app/runtime_policy.py). A WhatsApp reply is a few sentences at most;
    # 500 tokens is generous headroom, not a target.
    MAX_REPLY_TOKENS: int = 500

    @field_validator("MAX_REPLY_TOKENS")
    @classmethod
    def _reject_implausible_max_reply_tokens(cls, v: int) -> int:
        if not (1 <= v <= 4_000):
            raise ValueError(
                "must be a positive count up to 4,000 — a WhatsApp reply is a few sentences at "
                "most (500 is already generous headroom); zero or negative would refuse every "
                "reply outright, and anything past 4,000 is far more likely a typo (a token "
                "count where a word or character count was meant) than a real ceiling")
        return v

    # ── LLM (function calling, via assistant-service) ─────────────────────────
    LLM_DRIVER: str = "null"                 # null | assistant_service
    # The ONLY functions the model may call. Enforced twice: once by what we declare to the
    # provider's function-calling API, once again server-side (core/tools.py) — a model that
    # hallucinates a tool name outside this list is rejected before any tool body runs.
    LLM_TOOL_ALLOWLIST: str = (
        "check_availability,propose_booking,get_customer_points_summary,suggest_redeemable_offer,"
        "suggest_related_service,list_my_bookings,propose_cancel_booking,"
        "propose_reschedule_booking,suggest_services_carousel,list_packages,"
        "list_due_services,list_lapsed_services,check_mobile_visit_hours,request_mobile_visit,"
        "check_growth_opportunities,check_active_offers,get_service_procedure")

    # The three booking-management tool names — named once here so the kill-switch below and
    # core/tools.py's own dispatch never risk drifting apart on the literal strings.
    _BOOKING_MANAGEMENT_TOOLS = frozenset(
        {"list_my_bookings", "propose_cancel_booking", "propose_reschedule_booking"})

    # ── carousel (real photos, real services — app/ports/catalog_provider.py) ────────────────
    # One platform-wide approved template — see the approved plan (`stateless-wondering-fox.md`):
    # ONE carousel template, registered once with a placeholder example image, used by every shop;
    # the REAL per-shop photos travel as media ids at send time, never at template-registration time.
    WHATSAPP_CATALOG_CAROUSEL_TEMPLATE_NAME: str = "wa_catalog_carousel"
    WHATSAPP_CATALOG_CAROUSEL_LANGUAGE: str = "ar"
    # Meta's own carousel bounds are 2-10 cards; the default stays well under that ceiling — a
    # customer scrolling ten cards on a small screen is not "helpful", it is noise.
    MAX_CAROUSEL_CARDS: int = 5

    @field_validator("MAX_CAROUSEL_CARDS")
    @classmethod
    def _reject_carousel_cards_outside_metas_own_bounds(cls, v: int) -> int:
        if not (2 <= v <= 10):
            raise ValueError(
                "Meta's own WhatsApp carousel template bounds are 2-10 cards — a value outside "
                "that range is accepted by nothing downstream of this: below 2 there is no "
                "carousel to show, above 10 Meta itself refuses the send")
        return v

    @property
    def llm_tool_allowlist(self) -> frozenset[str]:
        declared = frozenset(t.strip() for t in self.LLM_TOOL_ALLOWLIST.split(",") if t.strip())
        # THE MASTER KILL-SWITCH, ENFORCED HERE REGARDLESS OF WHAT LLM_TOOL_ALLOWLIST LITERALLY
        # SAYS — see BOOKING_MANAGEMENT_ENABLED's own note. Flipping this one value off silently
        # drops the three tools even if an operator forgot to also edit the allowlist string.
        # ALSO gated on the booking driver being "real": ConfigDrivenAvailabilityProvider (the
        # zero-infra local placeholder — core/booking.py) has no concept of "this customer's real
        # existing bookings" at all, so these tools are meaningless — and unsafe to even offer —
        # under any driver but "real" (booking_assignment.py's own module docstring). A deployment
        # still on "config" gets these three withheld automatically, not by remembering to also
        # flip BOOKING_MANAGEMENT_ENABLED off.
        if not self.BOOKING_MANAGEMENT_ENABLED or self.BOOKING_PROVIDER_DRIVER != "real":
            declared = declared - self._BOOKING_MANAGEMENT_TOOLS
        # SAME REASONING FOR THE CAROUSEL TOOL: NullCatalogProvider always returns [], so offering
        # this tool with no real provider wired would be a model that "tries" it every time and
        # always gets nothing — withheld entirely rather than offered and refused, same posture as
        # the booking-management tools above.
        if self.CATALOG_PROVIDER_DRIVER != "platform":
            declared = declared - {"suggest_services_carousel"}
        # SAME REASONING, FOR THE TWO RHYTHM TOOLS: NullRhythmProvider always returns [], so a
        # model offered these with no real rhythm provider wired would try them every turn and
        # always get "لا يوجد شيء هنا الآن." — withheld entirely rather than offered and refused.
        if self.RHYTHM_PROVIDER_DRIVER != "http":
            declared = declared - {"list_due_services", "list_lapsed_services"}
        # SAME REASONING, FOR THE MOBILE-SERVICE-REQUEST TOOL: with no OPERATIONS_SERVICE_URL
        # wired, app/adapters/mobile_requests::build returns NullMobileRequests, whose .create
        # always raises — a model offered this tool anyway would propose it and always fail the
        # customer at the very last step (after they already shared a location). Withheld
        # entirely instead, same posture as every other peer-backed tool above.
        if not self.OPERATIONS_SERVICE_URL:
            declared = declared - {"request_mobile_visit", "check_mobile_visit_hours"}
        # SAME BASELINE REASONING: with no OPERATIONS_SERVICE_URL, both service_catalog and
        # package_catalog degrade to Null (empty) — the tool's own `service_ids` argument would
        # name services this deployment cannot even look up. The other four peers it optionally
        # also reads (points, rhythm, associations) each degrade on their own already; this is only
        # the one baseline every real use of the tool needs.
        if not self.OPERATIONS_SERVICE_URL:
            declared = declared - {"check_growth_opportunities"}
        # `check_active_offers` reads reminders' own send-log (core/active_offers.py) — with no
        # REMINDERS_SERVICE_URL it degrades to Null (always empty), so the tool would only ever
        # answer "nothing" rather than genuinely check.
        if not self.REMINDERS_SERVICE_URL:
            declared = declared - {"check_active_offers"}
        return declared

    def assert_llm_config_ok(self) -> None:
        if not self.is_production:
            return
        if self.LLM_DRIVER == "null":
            raise ValueError(
                "LLM_DRIVER=null in production: the assistant would receive every message and "
                "propose nothing — a receptionist that never answers.")
        if self.LLM_DRIVER == "assistant_service":
            # ASSISTANT_SERVICE_URL is the in-cluster address of a sibling service — always a real
            # value at deploy time, never something an operator supplies later. PROJECT/CREDENTIAL
            # are the ones with no value yet (no GCP project exists): SECRETS_KEK present means
            # there IS a way to get real values into this process without a redeploy —
            # app/api/v1/operator.py's PUT /operator/secrets, once the pod is up. Only refuse to
            # boot when NEITHER path can ever supply them: env is empty and there is nothing for
            # an operator to write into either, which used to crash-loop this pod on every
            # wipe+reinstall (an LLM credential is never part of the automated secret-minting set)
            # with no way to recover it except a redeploy carrying the env values again.
            if not self.ASSISTANT_SERVICE_URL:
                raise ValueError("LLM_DRIVER=assistant_service but ASSISTANT_SERVICE_URL is empty.")
            if not self.SECRETS_KEK and not (self.ASSISTANT_MODEL_PROJECT and self.ASSISTANT_MODEL_CREDENTIAL):
                raise ValueError(
                    "LLM_DRIVER=assistant_service but ASSISTANT_MODEL_PROJECT/ASSISTANT_MODEL_"
                    "CREDENTIAL are not both set and SECRETS_KEK is also empty — there is no way "
                    "for an operator to supply them at runtime either. Set both, or set SECRETS_KEK "
                    "and PUT them to /api/v1/assistant/operator/secrets once the service is up.")

    # ── billing — feature.whatsapp, the AI assistant sold as its own app (core/licence.py) ────
    # An independent price-list row, same shape as campaigns'/loyalty's own licence gate (and the
    # same billing endpoint every one of them calls — a generic keyed check, not a route owned by
    # this catalogue). Ordinary service messages are NOT behind this key and never asked here; only
    # an AI-composed reply and an AI-driven booking are. See core/licence.py's own docstring.
    BILLING_SERVICE_URL: str = ""
    BILLING_CHECK_PATH: str = "/internal/billing/entitlements/check"

    # ── the platform-wide external-AI kill switch (2026-09-19) ────────────────────────────────
    # ONE FLAG, EVERY SHOP, NOT A PER-TENANT TOGGLE. `shop_identity.ai_enabled` (ToggleGatedLicence
    # below) is the OWNER's own per-shop choice; this is ours — a single switch for the whole
    # fleet, meant to sit OFF for the entire window between "stop calling Gemini" and "Meta Business
    # Agent Platform is wired in", so no shop silently keeps billing for a provider we are mid-
    # migration away from. Reuses the exact same enforcement path every existing licence caller
    # already goes through (conversation.py's door gate and its second check right before the LLM
    # call) — OFF reads EXACTLY like "never bought it", never a softer state, so there is no
    # second customer-facing message to keep in step.
    AI_ASSISTANT_ENABLED: bool = True

    def assert_licence_config_ok(self) -> None:
        """Boot guard. Refuse production that cannot ask whether a shop bought the assistant.

        Without billing wired, build_licence returns NullLicence and every shop gets the AI
        assistant for free, silently, for as long as nobody compares the price list to the code —
        the same invisible-giveaway defect campaigns' own boot guard exists to close.
        """
        if not self.is_production:
            return
        if not self.BILLING_SERVICE_URL or not self.BILLING_CHECK_PATH:
            raise ValueError(
                "BILLING_SERVICE_URL/BILLING_CHECK_PATH empty in production: the WhatsApp AI "
                "assistant would be given away to every shop, quietly. Set them.")

    # ── conversation engine — debounce, session, summary (all config-driven) ─
    # Consecutive inbound messages inside this window are coalesced into ONE reply cycle — a
    # customer typing three short messages in a row must not receive three separate replies.
    CONVERSATION_DEBOUNCE_SECONDS: int = 180
    # A logical session closes on intent completion OR this much silence — whichever comes first.
    CONVERSATION_SESSION_TIMEOUT_SECONDS: int = 2400
    # How many raw messages are kept verbatim before being folded into the rolling summary. Bounds
    # LLM context/cost — the transcript is never sent whole, only this window plus the summary.
    CONVERSATION_RAW_WINDOW_MESSAGES: int = 25
    # NOT DECLARED: a "tick cadence in seconds" setting was published here once, but nothing ever
    # read it — the tick's real cadence is the CronJob's `schedule` string in this service's own
    # values file (deploy/services/whatsapp-assistant.values.yaml's `cronJobs:`), which is
    # minute-granularity cron syntax and cannot represent "every 30 seconds" at all. Deleted rather
    # than wired: computing a cron expression FROM a seconds value would mean templating the chart
    # itself, well past a backlog-cleanup fix, for a schedule that already has one place it lives.

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

    # ── soft-decline (core/soft_decline.py) — NOT frustration, a quieter signal ────────────────
    # This many real promotional suggestions waved off (core/tools.py::PROMO_TOOLS), THIS SESSION,
    # and every PROMO_TOOLS member drops out of `allowed` for the rest of it — no escalation, the
    # conversation continues completely normally, it simply stops being pitched anything. One
    # decline is normal conversation; two is a pattern worth respecting.
    SOFT_DECLINE_THRESHOLD: int = 2

    @field_validator("FRUSTRATION_UNCONFIRMED_PROPOSALS_THRESHOLD",
                     "FRUSTRATION_DUPLICATE_MESSAGES_THRESHOLD", "SOFT_DECLINE_THRESHOLD")
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

    # ── AI-unit pricing (وحدات الذكاء, app/core/ai_unit_pricing.py) ─────────────────────────────
    # A FIXED, model-independent display scale — 1 halala is always worth this many units, no
    # matter which model answered. What actually varies per model is the halala rate below it is
    # wrapped around (PRICING_AI_UNIT_MODEL_COSTS_JSON). Pricing keys, like the seven above: any
    # change goes through core/pricing_schedule.py's scheduled-change gate, never applied instantly.
    PRICING_AI_UNIT_UNITS_PER_HALALA: int = 1000
    # Separate input/output margins — output tokens cost Google far more per token than input for
    # every model checked, so one blended multiplier would misprice one direction or the other.
    PRICING_AI_UNIT_INPUT_MARGIN_MULTIPLIER: float = 5.0
    PRICING_AI_UNIT_OUTPUT_MARGIN_MULTIPLIER: float = 2.0
    # SAR is pegged to USD at 3.75 (SAMA); Google bills in USD, this platform prices in SAR. A
    # currency conversion, not a cost adjustment — see ai_unit_pricing.py's own note on why there is
    # no separate regional-markup step anywhere in this pipeline.
    PRICING_AI_UNIT_USD_TO_SAR: float = 3.75
    # {model_name: {"input_usd_per_million": x, "output_usd_per_million": y}} — the REAL, admin-
    # entered Google price per model (off the real invoice/pricing page, never inflated by a
    # guessed markup — see ai_unit_pricing.ModelCost's own docstring). A model missing from this
    # registry falls back to a zero halalas-per-1k rate in both directions rather than blocking
    # the assistant. Ships with today's deployed default model
    # (ASSISTANT_MODEL_NAME=gemini-3.1-flash-lite, per deploy/services/whatsapp-assistant.values.yaml)
    # priced from Google's own published global rate.
    PRICING_AI_UNIT_MODEL_COSTS_JSON: str = (
        '{"gemini-3.1-flash-lite": {"input_usd_per_million": 0.25, '
        '"output_usd_per_million": 1.50}}')

    @field_validator("PRICING_AI_UNIT_UNITS_PER_HALALA")
    @classmethod
    def _reject_bad_units_per_halala(cls, v: int) -> int:
        if not (0 < v <= 1_000_000):
            raise ValueError(
                "PRICING_AI_UNIT_UNITS_PER_HALALA must be a positive integer up to 1,000,000 — a "
                "typo here silently rescales every shop's displayed AI-unit balance and consumption")
        return v

    @field_validator("PRICING_AI_UNIT_INPUT_MARGIN_MULTIPLIER", "PRICING_AI_UNIT_OUTPUT_MARGIN_MULTIPLIER")
    @classmethod
    def _reject_bad_margin_multiplier(cls, v: float) -> float:
        if not (1.0 < v <= 50.0):
            raise ValueError(
                "AI-unit margin multipliers must be greater than 1 and at most 50 — a typo like "
                "'500' instead of '5' would silently overcharge every shop by 100x")
        return v

    @field_validator("PRICING_AI_UNIT_USD_TO_SAR")
    @classmethod
    def _reject_bad_usd_to_sar(cls, v: float) -> float:
        if not (0.0 < v <= 50.0):
            raise ValueError(
                "PRICING_AI_UNIT_USD_TO_SAR must be a positive, plausible exchange rate (<= 50) — "
                "the SAR peg is 3.75; anything wildly off is a typo, not a real rate change")
        return v

    @field_validator("PRICING_AI_UNIT_MODEL_COSTS_JSON")
    @classmethod
    def _reject_bad_model_costs_json(cls, v: str) -> str:
        from app.core.ai_unit_pricing import parse_model_costs

        parsed = parse_model_costs(v)
        if v.strip() and v.strip() != "{}" and not parsed:
            raise ValueError(
                "PRICING_AI_UNIT_MODEL_COSTS_JSON did not parse into any usable model — expected "
                '{"model_name": {"input_usd_per_million": x, "output_usd_per_million": y}}')
        for name, cost in parsed.items():
            if cost.input_usd_per_million < 0 or cost.output_usd_per_million < 0:
                raise ValueError(f"PRICING_AI_UNIT_MODEL_COSTS_JSON: {name!r} has a negative price")
            if cost.input_usd_per_million > 1000 or cost.output_usd_per_million > 1000:
                raise ValueError(
                    f"PRICING_AI_UNIT_MODEL_COSTS_JSON: {name!r} exceeds $1000/million tokens — "
                    f"almost certainly a typo (e.g. a per-1k price entered where per-million is "
                    f"expected)")
        return v

    # ── ceilings / rate limits specific to this service ──────────────────────
    # Bounded work per tick — an unbounded sweep of due conversations is how a slow query becomes
    # a missed batch, exactly as in reminders' TICK_BATCH_SIZE.
    CONVERSATION_TICK_BATCH_SIZE: int = 200
    # ── outbound safety net, TWO SEPARATE LIMITERS, DIFFERENT THREATS ────────────────────────────
    # The single shop-wide-per-hour cap this used to be had a real flaw: on a genuinely busy day
    # (many customers, all legitimate) it could trip and go silent mid-conversation for every
    # customer at once — the cure looking like the disease it was meant to prevent. The actual
    # failure this guards against (a bug that keeps re-proposing the same reply, or a loop in the
    # LLM/tool-call path) hammers ONE conversation, not the whole shop — so the tight limiter
    # should be scoped to match: WhatsApp's own "pair rate limit" (same business number, same
    # recipient, too fast) is the same reasoning, at the platform level.
    #
    # 1) PER CONVERSATION (tenant + subject_ref) — the real circuit breaker. A normal back-and-forth
    #    is nowhere near this pace; a runaway loop blows through it in seconds and gets stopped
    #    there, without silencing any OTHER customer's conversation with the same shop.
    CONVERSATION_OUTBOUND_MAX_PER_10MIN: int = 10
    # 2) PER WHATSAPP NUMBER (tenant + branch_id — "" for a central shop's one number), a much
    #    higher backstop for the case a bug somehow spans MANY different conversations at once.
    #    Sized well above real usage on purpose: WhatsApp's own lowest tier already allows 250
    #    conversations/24h per number, and a shop this busy should never see its own assistant
    #    silenced by an internal ceiling before Meta's own limit would ever bite. This is a last
    #    resort, not a routine brake — see developers.facebook.com/docs/whatsapp/messaging-limits.
    OUTBOUND_MAX_PER_NUMBER_PER_HOUR: int = 2000
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
    DATASTORE_STATEMENT_CACHE_SIZE: int = 0   # 0 => PgBouncer transaction-mode safe (no asyncpg prepared-statement cache)

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
