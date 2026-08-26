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

    container.operations = Operations(
        store=container.datastore, pii_salt=settings.PII_SALT,
        max_backdate=settings.MAX_BACKDATE_SECONDS,
    ).with_offer_chooser(http_chooser(reminders_url=settings.REMINDERS_SERVICE_URL,
                                      token=settings.INTERNAL_SERVICE_TOKEN))
    # THE COUNTER'S DESK AT `loyalty` — what a till may ask about a customer's points, asked on
    # its behalf so its own credential never has to carry a capability over the ledger.
    from app.adapters.loyalty_desk import build_loyalty_desk
    container.loyalty_desk = build_loyalty_desk(settings)
    # THE ONE QUESTION ASKED OF `bookings`: the shop's own working hours, so a staff member's
    # custom schedule can be refused at write time if it reaches outside them (a fail-OPEN check
    # — `bookings` intersects defensively at read time regardless of whether this peer answers).
    from app.adapters.bookings_desk import build_bookings_desk
    container.bookings_desk = build_bookings_desk(settings)
    # THE ADMIN PANEL'S "ليش واتساب هذا المحل معطّل" READ — an internal-token peer call made ON
    # BEHALF of an operator who holds `platform.operations`, never a capability the browser's own
    # token carries. See `api/v1/platform.py::whatsapp_diagnostics`.
    from app.adapters.whatsapp_diagnostics import build_whatsapp_diagnostics
    container.whatsapp_diagnostics = build_whatsapp_diagnostics(settings)
    # WHAT EACH SHOP ACTUALLY PAID US — the one input a commission statement takes. Unconfigured
    # in a local run, and then the monthly sweep issues nothing and says why, rather than issuing
    # a statement of zero that a partner would read and believe.
    from app.adapters.settlements import build_settlements
    container.settlements = build_settlements(settings)
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
    # What the shop bought, for every lock the console draws. One read, five keys, no enforcement:
    # the gates are in the services that own the acts.
    from app.core.apps import build_apps

    container.apps = build_apps(settings)
    # Putting a newly connected shop's template library where Meta can review it — the step that
    # was a script somebody had to remember to run for every new establishment.
    from app.core.library import build_library

    container.library = build_library(settings)
    # And `feature.api`, asked on the one act that IS the programmatic link: a machine writing
    # visits. Separate from `apps` because it answers a third state — «تعذّر السؤال» — that the
    # till path treats as a yes and the store treats as unknown.
    from app.core.licence import build_api_licence

    container.api_licence = build_api_licence(settings)
    # And `feature.base` — the 99-a-month product itself, which had no licence at all until the
    # subscription gate. Asked on every write the owner makes; never on a read.
    from app.core.base_licence import build_base_licence

    container.base_licence = build_base_licence(settings)
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
