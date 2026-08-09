# =============================================================================
# reminders — Composition root (config-driven port -> adapter wiring)
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

# ── Registries (the allowlist) — driver name -> builder ─────────────────────
_DATASTORE: dict[str, Builder] = {
    "memory": lambda s: MemoryDataStore(),
    "postgres": lambda s: PostgresDataStore(
        s.DATASTORE_DSN,
        pool_min=s.DATASTORE_POOL_MIN,
        pool_max=s.DATASTORE_POOL_MAX,
        pool_timeout=s.DATASTORE_POOL_TIMEOUT_SECONDS,
        pool_max_inactive_lifetime=s.DATASTORE_POOL_MAX_INACTIVE_LIFETIME_SECONDS,
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
    # ── this service's own pieces, built after the ports they depend on ───────────────────────
    sender: Any = None
    identity: Any = None
    scheduler: Any = None
    ingest: Any = None
    tick: Any = None

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

    # ── the domain, assembled from settings rather than from constants ────────────────────────
    # Local imports: these pull in this service's own core, and keeping them out of module scope
    # means the ports above stay importable by anything that only needs a driver.
    from app.adapters.identity import build_identity
    from app.adapters.message_sender import build_sender
    from app.core.quota import build_quota
    from app.core.adaptive import AdaptiveConfig
    from app.core.engagement import EngagementConfig
    from app.core.gate import Limits
    from app.core.ingest import HttpVisits, Ingest
    from app.core.scheduling import Scheduler
    from app.core.tick import Tick

    adaptive_cfg = AdaptiveConfig(
        alpha=settings.ADAPTIVE_ALPHA, anomaly_factor=settings.ADAPTIVE_ANOMALY_FACTOR,
        min_days=settings.ADAPTIVE_MIN_DAYS, max_days=settings.ADAPTIVE_MAX_DAYS,
        warmup=settings.ADAPTIVE_WARMUP_OBSERVATIONS)
    eng_cfg = EngagementConfig(
        half_life_days=settings.ENGAGEMENT_HALF_LIFE_DAYS,
        full_threshold=settings.ENGAGEMENT_FULL_THRESHOLD,
        minimal_threshold=settings.ENGAGEMENT_MINIMAL_THRESHOLD)
    limits = Limits(
        window_start_hour=settings.SEND_WINDOW_START_HOUR,
        window_end_hour=settings.SEND_WINDOW_END_HOUR,
        daily_service_cap=settings.DAILY_SERVICE_CAP,
        monthly_marketing_cap=settings.MONTHLY_MARKETING_CAP,
        monthly_awareness_cap=settings.MONTHLY_AWARENESS_CAP,
        marketing_cooldown_hours=settings.MARKETING_COOLDOWN_HOURS,
        daily_total_cap=settings.DAILY_TOTAL_CAP)

    container.sender = build_sender(settings)
    # The message quota. Null in a local run, refused in production by assert_sender_config_ok —
    # a service that sends without counting is a plan limit nothing enforces.
    container.quota = build_quota(settings)
    container.identity = build_identity(settings)
    container.scheduler = Scheduler(
        store=container.datastore, cfg=adaptive_cfg, eng_cfg=eng_cfg,
        default_interval_days=settings.DEFAULT_INTERVAL_DAYS,
        lead_days=settings.DEFAULT_LEAD_DAYS)
    # The catch-up client is absent when operations is not configured — and `Ingest` degrades to
    # the event path alone rather than failing at boot. A local run with no peers must still work;
    # production is covered by assert_sender_config_ok, which requires the same URL.
    visits = (HttpVisits(url=settings.OPERATIONS_SERVICE_URL,
                         path=settings.OPERATIONS_VISITS_SINCE_PATH,
                         token=settings.INTERNAL_SERVICE_TOKEN,
                         timeout=settings.PEER_TIMEOUT_SECONDS)
              if settings.OPERATIONS_SERVICE_URL else None)
    container.ingest = Ingest(store=container.datastore, scheduler=container.scheduler,
                              visits_client=visits, telemetry=container.telemetry)
    container.tick = Tick(store=container.datastore, sender=container.sender, limits=limits,
                          eng_cfg=eng_cfg, batch=settings.TICK_BATCH_SIZE,
                          telemetry=container.telemetry, quota=container.quota)
    return container
