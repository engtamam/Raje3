# =============================================================================
# operations — Composition root (config-driven port -> adapter wiring)
# -----------------------------------------------------------------------------
# The registry is the ALLOWLIST: only listed drivers can be constructed, so an
# unknown/injected driver is impossible (fail-fast ConfigError at boot). Adapter
# selection is pure config (zero-hardcoded). The core depends on PORTS; only this
# file knows the concrete adapters.
# =============================================================================
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.adapters.cache.memory import MemoryCache
from app.adapters.cache.redis import RedisCache
from app.adapters.datastore.memory import MemoryDataStore
from app.adapters.datastore.postgres import PostgresDataStore
from app.adapters.datastore.phone_search_ro import PhoneSearchReadOnly
from app.adapters.event_bus.memory import MemoryEventBus
from app.adapters.event_bus.redis import RedisEventBus
from app.adapters.object_store.local import LocalObjectStore
from app.adapters.object_store.memory import MemoryObjectStore
from app.adapters.object_store.s3 import S3ObjectStore
from app.adapters.queue.memory import MemoryQueue
from app.adapters.queue.redis import RedisQueue
from app.adapters.rate_limiter.memory import MemoryRateLimiter
from app.adapters.rate_limiter.redis import RedisRateLimiter
from app.adapters.secrets.env import EnvSecrets
from app.adapters.secrets.file import FileSecrets
from app.adapters.audit_sink.eventbus import EventBusAuditSink
from app.adapters.audit_sink.http import HttpAuditSink
from app.adapters.audit_sink.null import NullAuditSink
from app.adapters.consent_gate.http import HttpConsentGate
from app.adapters.consent_gate.null import NullConsentGate
from app.adapters.telemetry.stdout import StdoutTelemetry
from app.adapters.token_verifier.hs256 import HS256Verifier
from app.adapters.token_verifier.jwks import JWKSVerifier
from app.adapters.token_verifier.null import NullVerifier
from app.adapters.token_verifier.rs256 import RS256Verifier
from app.config import Settings
from app.ports.cache import Cache
from app.ports.datastore import DataStore
from app.ports.errors import ConfigError
from app.ports.event_bus import EventBus
from app.ports.object_store import ObjectStore
from app.ports.queue import Queue
from app.ports.rate_limiter import RateLimiter
from app.ports.secrets_provider import SecretsProvider
from app.ports.telemetry import Telemetry
from app.ports.token_verifier import TokenVerifier

Builder = Callable[[Settings], Any]

# ── Registries (the allowlist) — driver name -> builder ─────────────────────
_DATASTORE: dict[str, Builder] = {
    "memory": lambda s: MemoryDataStore(),
    "postgres": lambda s: PostgresDataStore(
        s.DATASTORE_DSN,
        pool_min=s.DATASTORE_POOL_MIN,
        pool_max=s.DATASTORE_POOL_MAX,
        pool_timeout=s.DATASTORE_POOL_TIMEOUT_SECONDS,
        pool_max_inactive_lifetime=s.DATASTORE_POOL_MAX_INACTIVE_LIFETIME_SECONDS,
        statement_cache_size=s.DATASTORE_STATEMENT_CACHE_SIZE,
    ),
}
_CACHE: dict[str, Builder] = {
    "memory": lambda s: MemoryCache(),
    "redis": lambda s: RedisCache(s.CACHE_URL),
}
_EVENTBUS: dict[str, Builder] = {
    "memory": lambda s: MemoryEventBus(),
    "redis": lambda s: RedisEventBus(s.EVENTBUS_URL),
}
_QUEUE: dict[str, Builder] = {
    "memory": lambda s: MemoryQueue(),
    "redis": lambda s: RedisQueue(s.QUEUE_URL),
}
_OBJECTSTORE: dict[str, Builder] = {
    "local": lambda s: LocalObjectStore(s.OBJECTSTORE_ROOT),
    "memory": lambda s: MemoryObjectStore(),
    "s3": lambda s: S3ObjectStore(
        s.OBJECTSTORE_BUCKET, s.OBJECTSTORE_ENDPOINT_URL,
        access_key=s.OBJECTSTORE_ACCESS_KEY, secret_key=s.OBJECTSTORE_SECRET_KEY,
        region=s.OBJECTSTORE_REGION, force_path_style=s.OBJECTSTORE_FORCE_PATH_STYLE),
}
_SECRETS: dict[str, Builder] = {
    "env": lambda s: EnvSecrets(),
    "file": lambda s: FileSecrets(s.SECRETS_FILE),
}
_TOKEN: dict[str, Builder] = {
    "null": lambda s: NullVerifier(),
    "hs256": lambda s: HS256Verifier(s.TOKEN_HS256_SECRET, s.TOKEN_ISSUER, s.TOKEN_AUDIENCE),
    "rs256": lambda s: RS256Verifier(s.TOKEN_PUBLIC_KEY, s.TOKEN_ISSUER, s.TOKEN_AUDIENCE),
    "jwks": lambda s: JWKSVerifier(s.TOKEN_JWKS_URL, s.TOKEN_ISSUER, s.TOKEN_AUDIENCE),
}
_RATELIMITER: dict[str, Builder] = {
    "memory": lambda s: MemoryRateLimiter(s.RATELIMIT_MAX, s.RATELIMIT_WINDOW_SECONDS),
    "redis": lambda s: RedisRateLimiter(s.RATELIMIT_URL, s.RATELIMIT_MAX, s.RATELIMIT_WINDOW_SECONDS,
                                        degrade=s.RATELIMIT_DEGRADE),
}
# Where privileged actions are witnessed. `null` records nothing and SAYS so — the boot guard
# refuses it in production, because a chain that verifies perfectly while empty is a control that
# exists only on paper.
_AUDIT_SINK: dict[str, Builder] = {
    "null": lambda s: NullAuditSink(),
    "http": lambda s: HttpAuditSink(s.audit_ingest_url, s.INTERNAL_SERVICE_TOKEN,
                                    timeout=s.AUDIT_TIMEOUT_SECONDS),
}
# Ask before processing personal data. `null` answers UNKNOWN and says so; the boot guard refuses
# it in production for any service that declares consent-gated processing, because a gate that is
# never asked is the same defect as a chain that is never written.
_CONSENT_GATE: dict[str, Builder] = {
    "null": lambda s: NullConsentGate(),
    "http": lambda s: HttpConsentGate(s.COMPLIANCE_SERVICE_URL, s.INTERNAL_SERVICE_TOKEN,
                                      timeout=s.CONSENT_TIMEOUT_SECONDS,
                                      path=s.CONSENT_CHECK_PATH),
}
_TELEMETRY: dict[str, Builder] = {
    "stdout": lambda s: StdoutTelemetry(),
}


def _pick(registry: dict[str, Builder], driver: str, port_name: str, settings: Settings) -> Any:
    builder = registry.get(driver)
    if builder is None:
        allowed = ", ".join(sorted(registry))
        raise ConfigError(
            f"unknown {port_name} driver: {driver!r} — allowed: {allowed}"
        )
    return builder(settings)


@dataclass
class Container:
    datastore: DataStore
    cache: Cache
    event_bus: EventBus
    queue: Queue
    object_store: ObjectStore
    secrets: SecretsProvider
    token_verifier: TokenVerifier
    rate_limiter: RateLimiter
    telemetry: Telemetry
    audit_sink: Any = None
    consent_gate: Any = None
    # The domain, and the post-response work. Built here so a route reaches for a ready object
    # rather than constructing one per request — a store built per request is a connection pool
    # decision made by accident.
    operations: Any = None
    seams: Any = None
    search: Any = None
    templates: Any = None

    def describe(self) -> list[dict[str, str]]:
        """[{port, driver}] for the service manifest."""
        return [
            {"port": "datastore", "driver": self.datastore.driver},
            {"port": "cache", "driver": self.cache.driver},
            {"port": "event_bus", "driver": self.event_bus.driver},
            {"port": "queue", "driver": self.queue.driver},
            {"port": "object_store", "driver": self.object_store.driver},
            {"port": "secrets", "driver": self.secrets.driver},
            {"port": "token_verifier", "driver": self.token_verifier.driver},
            {"port": "rate_limiter", "driver": self.rate_limiter.driver},
            {"port": "telemetry", "driver": self.telemetry.driver},
        ] + ([{"port": "audit_sink", "driver": self.audit_sink.driver}]
             if self.audit_sink is not None else [])           + ([{"port": "consent_gate", "driver": self.consent_gate.driver}]
             if self.consent_gate is not None else [])

    def health_probes(self) -> dict[str, Any]:
        """name -> async health() for adapters that support it (readiness)."""
        probes: dict[str, Any] = {}
        for name in ("datastore", "cache", "event_bus", "queue", "object_store", "rate_limiter"):
            adapter = getattr(self, name)
            # Prefer health_state (a reason string: "ok" / "pool exhausted …" / "down") when the
            # adapter offers it, so readiness can name a FULL datastore distinctly from a DOWN one;
            # fall back to the boolean health() every adapter has.
            probe = getattr(adapter, "health_state", None) or getattr(adapter, "health", None)
            if probe is not None:
                probes[name] = probe
        return probes

    async def close(self) -> None:
        for name in ("datastore", "cache", "event_bus", "queue", "object_store", "rate_limiter"):
            adapter = getattr(self, name)
            close = getattr(adapter, "close", None)
            if close is not None:
                try:
                    await close()
                except Exception:
                    pass


def _build_audit_sink(settings: Settings, event_bus) -> Any:
    """The eventbus sink must publish on the SAME bus instance the container hands out — a second
    instance would be a second in-memory broker, so events would vanish in tests and in any
    single-process deployment while the sink still reported success."""
    driver = settings.AUDIT_SINK_DRIVER
    if driver == "eventbus":
        return EventBusAuditSink(event_bus, settings.AUDIT_TOPIC)
    return _pick(_AUDIT_SINK, driver, "audit_sink", settings)


def build_container(settings: Settings) -> Container:
    """Resolve every port from config. Fail-fast on any unknown driver."""
    event_bus = _pick(_EVENTBUS, settings.EVENTBUS_DRIVER, "event_bus", settings)
    container = Container(
        datastore=_pick(_DATASTORE, settings.DATASTORE_DRIVER, "datastore", settings),
        cache=_pick(_CACHE, settings.CACHE_DRIVER, "cache", settings),
        event_bus=event_bus,
        queue=_pick(_QUEUE, settings.QUEUE_DRIVER, "queue", settings),
        object_store=_pick(_OBJECTSTORE, settings.OBJECTSTORE_DRIVER, "object_store", settings),
        secrets=_pick(_SECRETS, settings.SECRETS_DRIVER, "secrets", settings),
        token_verifier=_pick(_TOKEN, settings.TOKEN_VERIFIER_DRIVER, "token_verifier", settings),
        rate_limiter=_pick(_RATELIMITER, settings.RATELIMITER_DRIVER, "rate_limiter", settings),
        telemetry=_pick(_TELEMETRY, settings.TELEMETRY_DRIVER, "telemetry", settings),
        audit_sink=_build_audit_sink(settings, event_bus),
        consent_gate=_pick(_CONSENT_GATE, settings.CONSENT_GATE_DRIVER, "consent_gate", settings),
    )
    # Domain wiring. Kept out of the dataclass defaults so the ports above are resolved first and
    # a domain object can never be handed a half-built container.
    from app.adapters.search import build_search           # local import: optional dependency
    from app.core.operations import Operations
    from app.core.seams import Seams
    from app.core.templates import TemplateLibrary

    # WHO JUDGES WHICH OFFER A VISIT APPLIES is installed here, not imported inside the core: the
    # core records the spend on the visit (§5.6.2) and asks somebody else which offer that is, so a
    # test can answer without a socket and this service never learns reminders' route shape.
    from app.adapters.offer_choice import http_chooser

    # THE WEAKER ROLE FOR THE ONE SEARCH THAT DESERVES ONE — see config.py's
    # DATASTORE_DSN_PHONE_SEARCH. `None` when unset is a real, supported state (the safe default
    # every optional wire in this service shares): customer_by_phone_searched() falls back to the
    # ordinary single-role lookup rather than failing to boot over a role nobody has provisioned yet.
    phone_search_ro = (PhoneSearchReadOnly(settings.DATASTORE_DSN_PHONE_SEARCH)
                       if settings.DATASTORE_DSN_PHONE_SEARCH else None)
    # KEPT AS A LOCAL, NOT JUST HANDED TO `with_offer_chooser` — `core/entitlements.py`'s own
    # `EntitlementGateway` (built below, once `mutual_benefit` exists) wraps this SAME
    # callable as its campaign source, rather than this service learning reminders' route shape a
    # second time.
    reminders_offer_chooser = http_chooser(reminders_url=settings.REMINDERS_SERVICE_URL,
                                           token=settings.INTERNAL_SERVICE_TOKEN)
    container.operations = Operations(
        store=container.datastore, pii_salt=settings.PII_SALT, cache=container.cache,
        max_backdate=settings.MAX_BACKDATE_SECONDS, phone_search_ro=phone_search_ro,
    ).with_offer_chooser(reminders_offer_chooser)

    # THE COUNTER'S DESK AT `loyalty` — what a till may ask about a customer's points, asked on
    # its behalf so its own credential never has to carry a capability over the ledger.
    from app.adapters.loyalty_desk import build_loyalty_desk
    container.loyalty_desk = build_loyalty_desk(settings)
    # THE ONE QUESTION ASKED OF `bookings`: the shop's own working hours, so a staff member's
    # custom schedule can be refused at write time if it reaches outside them (a fail-OPEN check
    # — `bookings` intersects defensively at read time regardless of whether this peer answers).
    from app.adapters.bookings_desk import build_bookings_desk
    container.bookings_desk = build_bookings_desk(settings)
    # THE TILL'S OWN "expedite a rating request" DOOR (2026-09-14) — see till.py's
    # rating_request_at_the_counter and reminders' own expedite_rating_request docstring.
    from app.adapters.reminders_desk import build_reminders_desk
    container.reminders_desk = build_reminders_desk(settings)
    # THE GENERAL IN-APP NOTIFICATION SEND — any feature in this service that needs to put an item
    # in an operator's bell-icon feed calls this and only this (app/adapters/inapp_notify.py's own
    # header note explains why it is not one-off, feature-specific code).
    from app.adapters.inapp_notify import build_inapp_notifier
    container.inapp_notifier = build_inapp_notifier(settings)
    # WHO IN A TENANT HOLDS A GIVEN CAPABILITY — the recipient-resolution half of a branch-scoped
    # in-app alert (core/notify_recipients.py combines this with our OWN branch-visibility rules,
    # never authz's business alone; see that module's own header note for why).
    from app.adapters.authz_desk import build_authz_desk
    container.authz_desk = build_authz_desk(settings)
    # THE ADMIN PANEL'S "ليش واتساب هذا المحل معطّل" READ — an internal-token peer call made ON
    # BEHALF of an operator who holds `platform.operations`, never a capability the browser's own
    # token carries. See `api/v1/platform.py::whatsapp_diagnostics`.
    from app.adapters.whatsapp_diagnostics import build_whatsapp_diagnostics
    container.whatsapp_diagnostics = build_whatsapp_diagnostics(settings)
    # THE META CATEGORY'S "STATUS" TAB (Raje3 Meta-panel Phase 1) — the platform-wide delivery,
    # bound-numbers and opt-out figures, read from notification-service the same way as the line
    # right above. See `api/v1/platform.py::whatsapp_platform_status`.
    from app.adapters.platform_status import build_platform_status
    container.platform_status = build_platform_status(settings)
    # ONE SHOP'S OWN CONNECTED NUMBER — two-step PIN set/rotate, subscribed webhook fields, business
    # verification, and messaging-limit tier (platform v0.19.9). Sits next to `whatsapp_diagnostics`
    # above: same per-shop scope, same internal-token peer shape. See `api/v1/platform.py`'s new
    # `whatsapp/two-step-pin` / `subscribed-fields` / `business-verification` / `messaging-limit`.
    from app.adapters.whatsapp_admin import build_whatsapp_admin
    container.whatsapp_admin = build_whatsapp_admin(settings)
    # WHAT EACH SHOP ACTUALLY PAID US — the one input a commission statement takes. Unconfigured
    # in a local run, and then the monthly sweep issues nothing and says why, rather than issuing
    # a statement of zero that a partner would read and believe.
    from app.adapters.settlements import build_settlements
    container.settlements = build_settlements(settings)
    # The subscription-renewal WhatsApp Flow's data source (platform v0.19.12) — reads one due
    # invoice and creates its pay-link. Reuses the SAME platform.billing client-credentials grant
    # `settlements` just above already holds; a deployment with no billing/identity credentials
    # gets a provider that refuses every op rather than faking a renewal.
    from app.adapters.renewal_provider import build_renewal_provider
    container.renewal_provider = build_renewal_provider(settings)
    # THE 2-DAYS-AHEAD SCAN — see core/renewal_heads_up.py's own docstring. `container.jobs` is
    # ALREADY the durable job-service peer (`c.jobs`, built above for Salla's own refresh scan) —
    # this reuses it rather than minting a second one.
    from app.core.renewal_heads_up import RenewingSoonReader, WhatsAppHeadsUpNotifier

    container.renewing_soon = RenewingSoonReader(
        base_url=settings.BILLING_SERVICE_URL, path=settings.BILLING_RENEWING_SOON_PATH,
        token=settings.INTERNAL_SERVICE_TOKEN)
    container.renewal_heads_up_notifier = WhatsAppHeadsUpNotifier(
        base_url=settings.WHATSAPP_ASSISTANT_SERVICE_URL,
        path=settings.WHATSAPP_UPCOMING_RENEWAL_TRIGGER_PATH,
        token=settings.INTERNAL_SERVICE_TOKEN)
    # Fires whatsapp-assistant's own Meta Business Agent onboarding sequence right after a
    # number connects — see core/meta_agent_provision_trigger.py's own docstring.
    from app.core.meta_agent_provision_trigger import MetaAgentProvisionTrigger

    container.meta_agent_provision_trigger = MetaAgentProvisionTrigger(
        base_url=settings.WHATSAPP_ASSISTANT_SERVICE_URL,
        path=settings.WHATSAPP_META_AGENT_PROVISION_PATH,
        token=settings.INTERNAL_SERVICE_TOKEN)
    # Fires whatsapp-assistant's own Meta Commerce Catalog provisioning right after a number
    # connects — see core/catalog_provision_trigger.py's own docstring.
    from app.core.catalog_provision_trigger import CatalogProvisionTrigger

    container.catalog_provision_trigger = CatalogProvisionTrigger(
        base_url=settings.WHATSAPP_ASSISTANT_SERVICE_URL,
        path=settings.WHATSAPP_CATALOG_PROVISION_PATH,
        token=settings.INTERNAL_SERVICE_TOKEN)
    # Per-service catalog item sync — see core/catalog_item_sync_trigger.py's own docstring.
    from app.core.catalog_item_sync_trigger import CatalogItemSyncTrigger

    container.catalog_item_sync_trigger = CatalogItemSyncTrigger(
        base_url=settings.WHATSAPP_ASSISTANT_SERVICE_URL,
        path=settings.WHATSAPP_CATALOG_ITEM_SYNC_PATH,
        token=settings.INTERNAL_SERVICE_TOKEN,
        public_base_url=settings.PUBLIC_BASE_URL)
    # The on/off switch for a number already onboarded — see core/meta_agent_rollout_trigger.py.
    from app.core.meta_agent_rollout_trigger import MetaAgentRolloutTrigger

    container.meta_agent_rollout_trigger = MetaAgentRolloutTrigger(
        base_url=settings.WHATSAPP_ASSISTANT_SERVICE_URL,
        path=settings.WHATSAPP_META_AGENT_ROLLOUT_PATH,
        token=settings.INTERNAL_SERVICE_TOKEN)
    container.search = build_search(settings)
    # THE VISIT STORE IS HANDED IN so the seams can write down that they finished (ز-7). Without
    # it nothing could tell «the after-work ran» from «the pod died before it did», and the retry
    # that could have repaired the second was the one that skipped it.
    from app.core.stores import VisitStore
    container.seams = Seams(search=container.search, events=container.event_bus,
                            telemetry=container.telemetry,
                            visits=VisitStore(container.datastore),
                            index_name=settings.SEARCH_INDEX_NAME)

    # Seats and branches, reported to billing after every change. Null in a local run; the
    # production values file sets the http driver.
    from app.core.seats import build_gauges
    container.gauges = build_gauges(settings)
    # The subscribe path's two reads: is this shop connected, and does this plan carry a trial.
    from app.core.subscribe import build_connections, build_plans

    container.connections = build_connections(settings)
    container.billing_plans = build_plans(settings)

    # Mobile/on-the-go service requests — see core/mobile_requests.py's own module docstring.
    # `operations=container.operations` (already built above) is how `complete()` reaches
    # `record_visit()` directly, no network hop; `seams=container.seams` (already built) is what
    # makes «تم» run the SAME after-work every other visit-creation route runs; `plans=container.
    # billing_plans` (just built, right above) is `is_subscribed()`'s own peer — needed only by
    # the WhatsApp bot's creation door, see that method's own docstring for why.
    from app.core.mobile_requests import MobileRequestService

    container.mobile_requests = MobileRequestService(
        store=container.datastore, operations=container.operations,
        seams=container.seams, working_hours=container.bookings_desk,
        plans=container.billing_plans, default_cc=settings.SIGNUP_PHONE_DEFAULT_CC)

    # WhatsApp Direct Ordering — see core/orders.py's own module docstring. `payments` is the
    # merchant's-own-gateway pay-link minter (adapters/payments_desk.py); `services`/`branches` are
    # what prices a line server-side and confirms the branch is real, never trusted off the wire.
    from app.adapters.payments_desk import build_payments_desk
    from app.core.order_pause import OrderPauseStore
    from app.core.orders import OrderService
    from app.core.stores import BranchStore, ServiceStore

    container.payments_desk = build_payments_desk(settings)
    container.order_pauses = OrderPauseStore(container.datastore)
    # WHICH CAMPAIGN DISCOUNT A PHONE NUMBER IS HOLDING — asked of reminders, the same peer
    # `reminders_offer_chooser` above asks about visits, through its OWN single-use mechanism
    # (see adapters/discount_desk.py's own module docstring on why it is not the same one).
    from app.adapters.discount_desk import build as build_discount_desk
    container.discount_desk = build_discount_desk(settings)
    container.orders = OrderService(
        store=container.datastore, services=ServiceStore(container.datastore),
        branches=BranchStore(container.datastore), operations=container.operations,
        seams=container.seams, payments=container.payments_desk, events=container.event_bus,
        working_hours=container.bookings_desk, pauses=container.order_pauses,
        discounts=container.discount_desk, loyalty=container.loyalty_desk,
        default_cc=settings.SIGNUP_PHONE_DEFAULT_CC)

    # Shop-to-shop coupons (base-services v0.23.0) — needs `billing_plans` above, so it is built
    # right after it. See core/coupons.py's own module docstring for the full design.
    from app.core.coupons import CouponService

    container.coupons = CouponService(
        store=container.datastore, plans=container.billing_plans,
        default_cc=settings.SIGNUP_PHONE_DEFAULT_CC)

    # Per-tenant app-visibility overrides — see core/app_visibility.py's own module docstring.
    from app.core.app_visibility import AppVisibilityOverrides

    container.app_visibility = AppVisibilityOverrides(store=container.datastore)

    # Mutual benefit — NOT the same feature as coupons above (see that module's own module
    # docstring, and core/mutual_benefit.py's own for the full contrast). Needs
    # `billing_plans` (just built) for its own feature-gate/pause-resume check, `authz_desk` and
    # `inapp_notifier` (both already built above) to find and reach a proposal's own recipients.
    # Installed onto the already-built `container.operations` via its own setter — see
    # `Operations.with_mutual_benefit_engine`'s own docstring for why this is a post-construction wire
    # rather than a constructor argument.
    from app.core.mutual_benefit import MutualBenefitEngine

    container.mutual_benefit = MutualBenefitEngine(
        store=container.datastore, plans=container.billing_plans,
        notifier=container.inapp_notifier, authz=container.authz_desk,
        default_cc=settings.SIGNUP_PHONE_DEFAULT_CC)
    container.operations.with_mutual_benefit_engine(container.mutual_benefit)

    # THE GLOBAL ANONYMOUS REFERRAL CODE'S OWN TILL-SIDE REDEMPTION (services/referrals, Phase 3)
    # — the SECOND real EntitlementGateway source, alongside mutual_benefit above. Reaches
    # `referrals` (code/campaign reads) and `loyalty` (crediting the referrer's own reward) over
    # HTTP, same "empty URL means disabled" posture every optional peer here takes.
    from app.adapters.referrals_desk import build_referrals_desk
    from app.core.affiliates import AffiliateService
    from app.core.referral_redemption import ReferralRedemptionEngine

    container.referrals_desk = build_referrals_desk(settings)
    # PHASE 4 — the marketer/influencer tier (core/affiliates.py's own module docstring), wholly
    # this shop's own data, wired into the SAME redemption engine so a code typed at the till
    # never needs to know in advance whether it belongs to an ordinary referrer or an affiliate.
    container.affiliates = AffiliateService(container.datastore,
                                            default_cc=settings.SIGNUP_PHONE_DEFAULT_CC)
    container.referral_redemption = ReferralRedemptionEngine(
        store=container.datastore, referrals_desk=container.referrals_desk,
        loyalty_desk=container.loyalty_desk, pii_salt=settings.PII_SALT,
        default_cc=settings.SIGNUP_PHONE_DEFAULT_CC, affiliates=container.affiliates)
    # THE WALK-IN DOOR ONTO THE SAME ENGINE — a visit recorded with no till involved at all is now
    # able to register a new customer's referral code too, not just an integrated till's own
    # `/referral/register` route. See `Operations.with_referral_redemption_engine`'s own docstring.
    container.operations.with_referral_redemption_engine(container.referral_redemption)

    # PHASE 5a — read-only performance reporting over the same grants/affiliate rows above.
    from app.core.referral_reports import ReferralReportService

    container.referral_reports = ReferralReportService(container.datastore)

    # THE "جماعي" MILESTONE HOOK — a separate service (campaigns), reached over HTTP, unlike the
    # in-process mutual-benefit engine just above. `build_milestone_peer` returns a silent no-op
    # when `CAMPAIGNS_SERVICE_URL` is unset, the same "empty means disabled, not a guess" posture
    # every other optional peer in this fleet already takes.
    from app.adapters.milestone_peer import build_milestone_peer

    container.milestone_peer = build_milestone_peer(settings)
    container.operations.with_milestone_peer(container.milestone_peer)

    # THE ONE AGGREGATION POINT `apply_offer` now consults instead of calling the reminders
    # chooser directly — see core/entitlements.py's own module docstring for the tie-break rule
    # (referral outranks a campaign offer) and why a future single-use-entitlement source joins
    # here, never inside `Operations` itself.
    from app.core.entitlements import EntitlementGateway

    container.entitlement_gateway = EntitlementGateway(
        mutual_benefit_engine=container.mutual_benefit, campaign_chooser=reminders_offer_chooser,
        referral_code_engine=container.referral_redemption)
    container.operations.with_entitlement_gateway(container.entitlement_gateway)

    # Salla — infrastructure only, see core/marketplaces/salla.py's own module docstring.
    from app.core.marketplaces.salla import SallaClient, SallaService

    container.salla = SallaService(
        store=container.datastore,
        client=SallaClient(
            client_id=settings.SALLA_CLIENT_ID, client_secret=settings.SALLA_CLIENT_SECRET,
            redirect_uri=(f"{settings.PUBLIC_BASE_URL.rstrip('/')}/api/v1/salla/callback"
                         if settings.PUBLIC_BASE_URL else "")))

    # job-service — see adapters/job_service.py's own module docstring. Optional, like every
    # other peer here: NullJobService when JOB_SERVICE_URL is unset.
    from app.adapters.job_service import HttpJobService, NullJobService

    container.jobs = (
        HttpJobService(base_url=settings.JOB_SERVICE_URL, token=settings.INTERNAL_SERVICE_TOKEN)
        if settings.JOB_SERVICE_URL else NullJobService())
    # Shop-content translation (phase 3) — see core/translation_engine.py's own module docstring.
    # NullTranslationEngine when the driver is unset, same posture as every other optional peer
    # here: the jobs/run route simply finds nothing it can do rather than crashing.
    from app.core.translation_engine import NullTranslationEngine, Nllb200TranslationEngine

    container.translation_engine = (
        Nllb200TranslationEngine(settings.TRANSLATION_MODEL_PATH, settings.TRANSLATION_SP_MODEL_PATH)
        if settings.TRANSLATION_ENGINE_DRIVER == "nllb200" else NullTranslationEngine())
    # What the shop bought, for every lock the console draws. One read, five keys, no enforcement:
    # the gates are in the services that own the acts.
    from app.core.apps import build_apps

    container.apps = build_apps(settings)
    # Putting a newly connected shop's template library where Meta can review it — the step that
    # was a script somebody had to remember to run for every new establishment.
    from app.core.library import build_library

    container.library = build_library(settings)
    # Each shop's own clone of the master rating Flow, provisioned right alongside the library —
    # see core/flows.py's module docstring for why a Flow needs cloning per WABA at all.
    from app.core.flows import build_flows

    container.flows = build_flows(settings)
    # And `feature.api`, asked on the one act that IS the programmatic link: a machine writing
    # visits. Separate from `apps` because it answers a third state — «تعذّر السؤال» — that the
    # till path treats as a yes and the store treats as unknown.
    from app.core.licence import build_api_licence

    container.api_licence = build_api_licence(settings)
    # NO `feature.base` ANY MORE — the bundled الأساس plan is retired entirely (2026-09-10). Every
    # app is its own licence now, and `subscribed_write` (api/subscribed.py) is itself an OR across
    # all of them: a generic shop-management write (staff, branches, services) needs ANY one paid
    # app, not a specific bundle nobody sells any more.
    #
    # `feature.whatsapp` — the one plan sold with no other app underneath it. Also joins the
    # generic OR below, same as every other app; it kept its own file (rather than the parametrised
    # builder) because it predates `feature_licence.py` — see that module's own docstring.
    from app.core.whatsapp_licence import build_whatsapp_licence

    container.whatsapp_licence = build_whatsapp_licence(settings)
    # Every OTHER standalone app's own licence, one parametrised builder rather than N hand-copied
    # files — see core/feature_licence.py's own docstring for why that stopped being safe at the
    # third key. Each joins `subscribed_write`'s OR (api/subscribed.py) under its own attribute
    # name; `campaigns_licence`/`loyalty_licence`/`rating_licence` exist here ONLY so that OR can
    # ask about them too — none of the three has a narrower, app-specific gate of its own the way
    # visit/bookings/contacts do (api/subscribed.py::subscribed_write_or_visit and friends).
    from app.core.feature_licence import build_feature_licence

    container.contacts_licence = build_feature_licence(settings, "feature.contacts")
    container.bookings_licence = build_feature_licence(settings, "feature.bookings")
    container.visit_licence = build_feature_licence(settings, "feature.visit")
    container.campaigns_licence = build_feature_licence(settings, "feature.campaigns")
    container.loyalty_licence = build_feature_licence(settings, "feature.loyalty")
    container.rating_licence = build_feature_licence(settings, "feature.rating")
    # `feature.partner_loyalty`/`feature.insights.engine`/`feature.mobile_requests` — each already
    # has its OWN narrow, door-specific entitlement check (core/coupons.py::granter_is_subscribed,
    # core/mobile_requests.py::is_subscribed) for the one act that IS the point of buying it. These
    # three licences exist here ONLY so `subscribed_write`'s generic "holds ANY app" OR
    # (api/subscribed.py, built from `core/apps.py::KEYS`/`licence_attr`) can ask about them too —
    # without this row a shop paying for one of these three alone, and nothing else, was wrongly
    # refused an ordinary shop-management write.
    container.insights_engine_licence = build_feature_licence(settings, "feature.insights.engine")
    container.partner_loyalty_licence = build_feature_licence(settings, "feature.partner_loyalty")
    container.mobile_requests_licence = build_feature_licence(settings, "feature.mobile_requests")
    container.mutual_benefit_licence = build_feature_licence(
        settings, "feature.mutual_benefit")
    # WITHOUT THIS, `subscribed_write`'s own generic OR-gate (app/api/subscribed.py::_ANY_APP,
    # derived from core/apps.py::KEYS) reads `getattr(container, "mobile_ai_assistant_licence",
    # None)` as `None` for EVERY tenant and, by that gate's own documented "an unwired licence
    # lets the write through" rule, makes the WHOLE gate pass for EVERY shop — a real regression a
    # real review caught the moment `feature.mobile_ai_assistant` joined `core/apps.py::APPS`
    # without this line landing in the same change.
    container.mobile_ai_assistant_licence = build_feature_licence(
        settings, "feature.mobile_ai_assistant")
    # SAME REASON AS `mobile_ai_assistant_licence` ABOVE — feature.coworking's own entitlement
    # check lives entirely inside services/coworking (its own separate microservice, never a
    # module here); this attribute exists ONLY so `subscribed_write`'s generic "holds ANY app" OR
    # can see it, not because operations enforces anything about co-working resources itself.
    container.coworking_licence = build_feature_licence(settings, "feature.coworking")
    # Same rule, same reason: `feature.referrals` joined `core/apps.py::APPS` (Phase 0 backend
    # registration), so it must join here in the same change or `subscribed_write`'s generic
    # OR-gate reads it as unwired and opens for every shop.
    container.referrals_licence = build_feature_licence(settings, "feature.referrals")
    # Same rule again: `feature.whatsapp_delivery_orders` joined `core/apps.py::APPS` too — its own
    # entitlement enforcement lives in services/whatsapp-assistant (core/order_licence.py), never
    # here; this attribute exists only so `subscribed_write`'s OR-gate can see it.
    container.whatsapp_delivery_orders_licence = build_feature_licence(
        settings, "feature.whatsapp_delivery_orders")
    container.templates = TemplateLibrary(container.datastore)
    # The door. Built early, because a signup that cannot
    # seed a catalogue is a signup that lands the new owner on an empty «خدماتي».
    from app.core.partners import PartnerRegistry
    from app.core.signup import Http, SignupService

    # THE ROLE DEFINITIONS, READ ONCE AT BOOT. A missing or malformed file leaves the list empty,
    # and signup then REFUSES rather than creating an account with no capabilities — see
    # core/signup.py for why a useless account is worse than none.
    _roles: list[dict] = []
    if settings.SIGNUP_ROLES_FILE:
        try:
            import json as _json
            with open(settings.SIGNUP_ROLES_FILE, encoding="utf-8") as _f:
                _roles = list(_json.load(_f).get("roles") or [])
        except Exception:                                                   # noqa: BLE001
            _roles = []

    container.signup = SignupService(
        store=container.datastore,
        http=Http(timeout=settings.SIGNUP_TIMEOUT_SECONDS,
                  internal_token=settings.INTERNAL_SERVICE_TOKEN),
        identity_url=settings.IDENTITY_SERVICE_URL,
        tenants_url=settings.TENANT_SERVICE_URL,
        default_cc=settings.SIGNUP_PHONE_DEFAULT_CC,
        authz_url=settings.AUTHZ_SERVICE_URL,
        loyalty_url=settings.LOYALTY_SERVICE_URL,
        compliance_url=settings.COMPLIANCE_SERVICE_URL,
        affiliate_url=settings.AFFILIATE_SERVICE_URL,
        ticket_url=settings.TICKET_SERVICE_URL,
        affiliate_ticket_scope_types=settings.AFFILIATE_TICKET_SCOPE_TYPES,
        data_map=[e for e in (settings.TENANT_DATA_MAP or "").split(",") if e.strip()],
        roles=_roles,
        # ATTRIBUTION AT CREATION, before the first invoice — and stamped once, so a till company
        # that replaces another's software six months later cannot inherit its commission.
        partners=PartnerRegistry(container.datastore, salt=settings.PII_SALT),
        owner_role=settings.SIGNUP_OWNER_ROLE,
        otp_deliverable=settings.SIGNUP_OTP_DELIVERABLE,
        # AN INCOMPLETE DATA MAP MUST BE AUDIBLE. A shop registered while compliance was briefly
        # unreachable for ONE entry keeps a map missing that service for ever — and every later
        # erasure then closes as COMPLETED while a whole service's copy is untouched. The failure
        # used to be a string in a response body nobody reads.
        telemetry=container.telemetry,
        require_otp=settings.SIGNUP_REQUIRE_OTP,
        # HIS FREE MONTH, OPENED THE MOMENT HE SIGNS UP — see signup.py's own note on
        # `_start_base_trial`. `None` on a deployment with billing_plans left at its null driver
        # (tests, a local run) — the same optional trade the peers just above it already make.
        plans=container.billing_plans if getattr(container.billing_plans, "driver", "") == "http"
        else None)
    # WHO CAN ANSWER FOR CONSENT AND FOR WHAT WENT OUT. None when reminders is not configured,
    # and the evidence file says so rather than showing an empty section (core/evidence.py).
    from app.adapters.evidence_peer import build_evidence_peer

    container.evidence_peer = build_evidence_peer(settings)

    return container
