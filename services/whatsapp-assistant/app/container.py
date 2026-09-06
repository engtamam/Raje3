# =============================================================================
# whatsapp-assistant — Composition root (config-driven port -> adapter wiring)
# -----------------------------------------------------------------------------
# The registry is the ALLOWLIST: only listed drivers can be constructed. Adapter
# selection is pure config. The core depends on PORTS; only this file knows the
# concrete adapters.
# =============================================================================
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
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
from app.adapters.secrets.vault import VaultSecrets
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

_DATASTORE: dict[str, Builder] = {
    "memory": lambda s: MemoryDataStore(),
    "postgres": lambda s: PostgresDataStore(
        s.DATASTORE_DSN, pool_min=s.DATASTORE_POOL_MIN, pool_max=s.DATASTORE_POOL_MAX,
        pool_timeout=s.DATASTORE_POOL_TIMEOUT_SECONDS,
        pool_max_inactive_lifetime=s.DATASTORE_POOL_MAX_INACTIVE_LIFETIME_SECONDS),
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
    "vault": lambda s: VaultSecrets(s.VAULT_ADDR, s.VAULT_TOKEN, s.VAULT_PATH),
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
_AUDIT_SINK: dict[str, Builder] = {
    "null": lambda s: NullAuditSink(),
    "http": lambda s: HttpAuditSink(s.audit_ingest_url, s.INTERNAL_SERVICE_TOKEN,
                                    timeout=s.AUDIT_TIMEOUT_SECONDS),
}
_CONSENT_GATE: dict[str, Builder] = {
    "null": lambda s: NullConsentGate(),
    "http": lambda s: HttpConsentGate(s.COMPLIANCE_SERVICE_URL, s.INTERNAL_SERVICE_TOKEN),
}
_TELEMETRY: dict[str, Builder] = {
    "stdout": lambda s: StdoutTelemetry(),
}


def _pick(registry: dict[str, Builder], driver: str, port_name: str, settings: Settings) -> Any:
    builder = registry.get(driver)
    if builder is None:
        allowed = ", ".join(sorted(registry))
        raise ConfigError(f"unknown {port_name} driver: {driver!r} — allowed: {allowed}")
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
    # ── this service's own pieces ─────────────────────────────────────────
    inbound_store: Any = None
    llm: Any = None
    booking_provider: Any = None
    points_summary: Any = None
    customer_lookup: Any = None
    branch_directory: Any = None
    shop_identity: Any = None
    service_catalog: Any = None
    package_catalog: Any = None
    catalog_provider: Any = None
    related_services: Any = None
    wallet_balance: Any = None
    licence: Any = None
    sender: Any = None
    secret_store: Any = None
    inbound_feed: Any = None
    engine: Any = None

    def describe(self) -> list[dict[str, str]]:
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
             if self.audit_sink is not None else []) + ([{"port": "llm", "driver": self.llm.driver}]
             if self.llm is not None else [])

    def health_probes(self) -> dict[str, Any]:
        probes: dict[str, Any] = {}
        for name in ("datastore", "cache", "event_bus", "queue", "object_store", "rate_limiter"):
            adapter = getattr(self, name)
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


def build_container(settings: Settings) -> Container:
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
        audit_sink=_pick(_AUDIT_SINK, settings.AUDIT_SINK_DRIVER, "audit_sink", settings),
    )

    # ── this service's own domain, assembled from settings ────────────────────────────────────
    from app.adapters.inbound_store.datastore_backed import build as build_inbound_store
    from app.adapters.llm import build as build_llm
    from app.adapters.whatsapp_sender import build as build_sender
    from app.core import booking as B
    from app.core import booking_assignment as BA
    from app.core import customer_lookup as CL
    from app.core import branch_directory as BD
    from app.core import shop_identity as SI
    from app.core import points as P
    from app.core import service_catalog as SC
    from app.core import package_catalog as PC
    from app.core import related_services as RS
    from app.core import wallet_balance as WB
    from app.core.licence import build_licence
    from app.core.conversation import ConversationEngine
    from app.core.secret_store import SecretStore

    # None only when SECRETS_KEK is genuinely absent (a boot with nothing to seal with — rather
    # than construct a store that would raise on first use). In a real deployment it is present
    # (one of the seven shared secrets every wipe+reinstall mints), and app/api/v1/operator.py's
    # ASSISTANT_MODEL_PROJECT/CREDENTIAL rotation is what actually reads it now — see
    # app/adapters/llm/__init__.py.
    container.secret_store = SecretStore(container.datastore, settings.SECRETS_KEK) \
        if settings.SECRETS_KEK else None
    container.inbound_store = build_inbound_store(container.datastore)
    # secret_store BEFORE llm, and passed in: an operator-rotated credential (app/api/v1/
    # operator.py) needs the same store instance the LLM adapter resolves it from, not a second
    # one that would never see the write.
    container.llm = build_llm(settings, secret_store=container.secret_store)
    # "config" (default) keeps the zero-infra placeholder; "real" (Phase 4) swaps in
    # RealBookingProvider — same port, see app/ports/booking_provider.py's own note. An unknown
    # driver value fails fast rather than silently falling back to the placeholder — a typo'd
    # deployment config must never SEEM to have real bookings wired when it does not.
    if settings.BOOKING_PROVIDER_DRIVER == "real":
        container.booking_provider = BA.build(settings)
    elif settings.BOOKING_PROVIDER_DRIVER == "config":
        container.booking_provider = B.build(settings, store=container.datastore)
    else:
        raise ValueError(f"unknown BOOKING_PROVIDER_DRIVER {settings.BOOKING_PROVIDER_DRIVER!r}")
    container.points_summary = P.build(settings)
    container.customer_lookup = CL.build(settings)
    container.branch_directory = BD.build(settings)
    container.shop_identity = SI.build(settings)
    container.service_catalog = SC.build(settings)
    container.package_catalog = PC.build(settings)
    # Infrastructure only — see app/ports/catalog_provider.py's own docstring. No caller depends
    # on this yet; an unknown driver still fails fast, same reasoning as BOOKING_PROVIDER_DRIVER
    # just above.
    from app.core import catalog_provider as CP
    if settings.CATALOG_PROVIDER_DRIVER == "null":
        container.catalog_provider = CP.NullCatalogProvider()
    elif settings.CATALOG_PROVIDER_DRIVER == "platform":
        container.catalog_provider = CP.build(
            settings, service_catalog=container.service_catalog,
            package_catalog=container.package_catalog)
    else:
        raise ValueError(f"unknown CATALOG_PROVIDER_DRIVER {settings.CATALOG_PROVIDER_DRIVER!r}")
    container.related_services = RS.build(settings)
    container.wallet_balance = WB.build(settings)
    container.licence = build_licence(settings)
    from app.core.base_entitlement import build_base_entitlement

    container.base_entitlement = build_base_entitlement(settings)
    container.sender = build_sender(settings)
    # WAS NEVER ASSIGNED HERE AT ALL — `_CONSENT_GATE`'s registry existed, the field on `Container`
    # existed, and nothing between the two ever ran; `container.consent_gate` stayed the dataclass
    # default (`None`) forever, one line short of doing anything. See app/core/inbound_ingest.py
    # for the actual call this makes reachable.
    container.consent_gate = _pick(_CONSENT_GATE, settings.CONSENT_GATE_DRIVER, "consent_gate",
                                   settings)

    from app.adapters.inbound_feed import build as build_inbound_feed

    # The catch-up half of the "missed bus event" mitigation — see app/main.py's
    # `_on_whatsapp_message` docstring and app/core/inbound_poll.py for the full design.
    container.inbound_feed = build_inbound_feed(settings)
    container.engine = ConversationEngine(
        store=container.datastore, llm=container.llm, booking_provider=container.booking_provider,
        points_summary=container.points_summary, shop_identity=container.shop_identity,
        service_catalog=container.service_catalog, package_catalog=container.package_catalog,
        customer_lookup=container.customer_lookup,
        branch_directory=container.branch_directory,
        related_services=container.related_services, wallet_balance=container.wallet_balance,
        licence=container.licence,
        base_entitlement=container.base_entitlement,
        catalog_provider=container.catalog_provider,
        max_carousel_cards=settings.MAX_CAROUSEL_CARDS,
        wallet_estimated_tokens=settings.WALLET_ESTIMATED_MAX_TOKENS_PER_TURN,
        wallet_rate_halalas_per_1k=settings.PRICING_USAGE_HALALAS_PER_1K_TOKENS,
        wallet_margin_halalas=settings.WALLET_SAFETY_MARGIN_HALALAS,
        debounce_seconds=settings.CONVERSATION_DEBOUNCE_SECONDS,
        session_timeout_seconds=settings.CONVERSATION_SESSION_TIMEOUT_SECONDS,
        max_duration_seconds=settings.CONVERSATION_MAX_DURATION_SECONDS,
        raw_window_messages=settings.CONVERSATION_RAW_WINDOW_MESSAGES,
        allowed_tools=settings.llm_tool_allowlist,
        frustration_unconfirmed_proposals_threshold=settings.FRUSTRATION_UNCONFIRMED_PROPOSALS_THRESHOLD,
        frustration_duplicate_messages_threshold=settings.FRUSTRATION_DUPLICATE_MESSAGES_THRESHOLD,
        booking_history_visible=settings.BOOKING_HISTORY_VISIBLE,
        booking_management_enabled=settings.BOOKING_MANAGEMENT_ENABLED,
        shop_notes_enabled=settings.SHOP_NOTES_ENABLED,
        msg_word_limit_enabled=settings.MSG_WORD_LIMIT_ENABLED)
    # `auditor` is NOT passed here — app/main.py builds it AFTER build_container() (it needs the
    # container) and wires it in with `container.engine.set_auditor(...)` right after. See
    # app/core/conversation.py::ConversationEngine.__init__ for why.
    return container
