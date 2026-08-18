# =============================================================================
# campaigns — Composition root (config-driven port -> adapter wiring)
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


@dataclass(frozen=True)
class _Unknown:
    """A ceiling nobody could read. `0` is the shape notification-service reports for unknown, and
    share.compute() reads it as 'do not promise anything' rather than 'send nothing'."""

    limit: int = 0
    tier: str = ""
    quality: str = ""


class _NoCeiling:
    """Answers unknown. A deployment without the peer plans nothing and still sends everything."""

    async def read(self, tenant: str) -> _Unknown:
        return _Unknown()


async def _engine_load(peers, tenant: str) -> tuple[int, int]:
    """What the automatic engine has reserved for today, and what it has already spent.

    BOTH FROM PEERS THAT ALREADY OWN THEM. The reserve is in the insights snapshot, computed from
    visits it already holds; what has been used today is reminders' unique-customer count. Either
    computed here would be a second version of somebody else's number, drifting from it quietly.

    A peer that does not answer contributes ZERO rather than blocking, which errs toward letting
    the campaign run — the same direction as an unknown ceiling, and for the same reason.
    """
    reserved = used = 0
    read = getattr(peers, "engine_load", None)
    if read is not None:
        try:
            out = await read(tenant)
            reserved = int(out.get("reserved") or 0)
            used = int(out.get("used") or 0)
        except Exception:                                              # noqa: BLE001
            pass
    return reserved, used



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
    # ── this service's own pieces ─────────────────────────────────────────────────────────────
    templates: Any = None
    audience: Any = None
    sender: Any = None
    identity: Any = None
    gate: Any = None
    dispatcher: Any = None
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

    from app.adapters.peers import build_peers
    from app.core.audience import resolve as resolve_audience
    from app.core.dispatch import Dispatcher
    from app.core.tick import Tick

    peers = build_peers(settings)
    container.templates = peers["templates"]
    container.audience = _AudienceFacade(peers["audience"], resolve_audience,
                                         max_audience=settings.CAMPAIGN_MAX_AUDIENCE)
    container.sender = peers["sender"]
    container.identity = peers["identity"]
    container.gate = peers["window"]
    # THE THREE NUMBERS BEHIND "this will take five days", each from whoever owns it (core/share).
    # The ceiling is Meta's, read through notification-service; the reserve and today's usage
    # belong to insights and reminders. This service computes none of them, and that is the point:
    # a second version of somebody else's number drifts from it silently.
    container.ceiling = peers.get("ceiling") or _NoCeiling()
    container.engine_load = lambda tenant: _engine_load(peers.get("engine"), tenant)
    container.settings = settings

    async def _resolver(campaign, *, already_reached, now):
        # THE SEND RESOLVES THE SAME AUDIENCE THE PREVIEW SHOWED — including the service. Dropping
        # it here would mean the owner is shown a targeted count and the run reaches everybody, and
        # the report would agree with neither.
        return await container.audience.resolve_for(
            campaign.get("tenant", ""), goal=campaign.get("goal", ""), now=now,
            already_reached=already_reached, cls=campaign.get("cls", "marketing"),
            service_id=campaign.get("service_id", ""),
            branch_id=campaign.get("branch_id", ""))

    container.dispatcher = Dispatcher(store=container.datastore, sender=container.sender,
                                      audience_resolver=_resolver,
                                      batch=settings.DISPATCH_BATCH_SIZE,
                                      telemetry=container.telemetry)
    from app.core.licence import build_licence
    container.licence = build_licence(settings)
    async def _share_for(tenant: str) -> int:
        """Today's share for one shop — the ceiling, minus the engine's reserve, minus what has
        already gone. The same three numbers the preview shows, read the same way, so the screen's
        «سنوزّعها على N أيام» and the cron's behaviour cannot disagree."""
        from app.core.share import compute as compute_share

        ceiling = await container.ceiling.read(tenant)
        reserved, used = await container.engine_load(tenant)
        share = compute_share(ceiling=ceiling.limit, reserved=reserved, used=used,
                              fallback=settings.CAMPAIGN_MAX_AUDIENCE)
        return share.per_day if share.known else 0

    container.tick = Tick(store=container.datastore, dispatcher=container.dispatcher,
                          licence=container.licence,
                          awareness_lock_days=settings.AWARENESS_LOCK_DAYS,
                          share_reader=_share_for,
                          telemetry=container.telemetry)
    return container


class _AudienceFacade:
    """Binds the peer client to the pure resolver.

    The resolver stays pure — every input passed in — and this is the one place that knows both
    it and the network. Putting the peer call inside the resolver would make the function that
    decides who receives a message untestable across its space.
    """

    def __init__(self, client, resolve, *, max_audience: int) -> None:
        self._c = client
        self._resolve = resolve
        # The ceiling on one send. A product judgement, not a technical limit, and one that
        # changes with the size of the shops we serve — so it arrives from the deployment.
        self._max_audience = int(max_audience)

    async def resolve_for(self, tenant: str, *, goal: str, now: int, cls: str,
                          already_reached=None,
                          service_id: str = "", branch_id: str = ""):
        """`cls` HAS NO DEFAULT, AND THAT IS THE FIX (ج-1).

        It decides WHICH RULES the audience is resolved under: marketing needs explicit consent and
        is capped at four messages a month; awareness needs none and is capped at one. The send has
        always passed the campaign's real class. The preview did not — so it silently took
        `"marketing"`, and every awareness campaign was previewed under one rulebook and executed
        under another. The screen said 12 and the run reached 180, and both numbers came out of
        this same function, which is why nobody looked at the argument list.

        A default here is a policy chosen by whoever forgets to pass one. Removing it is worth more
        than any check that could have caught the omission: a caller that does not say now cannot
        compile, and there is no list of exceptions to keep.

        `service_id` IS THE 70% CYCLE LOCK'S ONLY INPUT, and it used not to arrive.

        The resolver has always accepted it and `_too_early` has always enforced it: whoever took
        this service two days ago is held out, and whoever is 70% through his own rhythm for it is
        exactly who the offer should reach. But no caller passed it — so every "offer on a service"
        resolved as a shop-wide announcement, and the audience count read as proof of targeting
        that never happened.
        """
        async def _customers(t):
            # THE SERVICE TRAVELS WITH THE READ. The rhythm joined onto each row is per SERVICE,
            # so asking without it returns the customer's rhythm for something else entirely — and
            # the 70% lock would then hold people back on a cycle that is not this one's.
            #
            # AND SO DOES THE BRANCH, for a harder reason: operations applies `limit` in the
            # datastore. Narrowing here instead would mean filtering the 5000 most recent customers
            # of the WHOLE chain down to one branch — an answer that is wrong, plausible, and
            # stable, which is the worst combination a number can have.
            return await self._c.customers(t, service_id=service_id, branch_id=branch_id)

        async def _gate(subject: str) -> bool:
            return await self._c.allows(tenant, subject, cls)

        return await self._resolve(goal=goal, tenant=tenant, now=now,
                                   customers=_customers, gate_check=_gate,
                                   already_reached=already_reached or set(),
                                   max_audience=self._max_audience,
                                   service_id=service_id)

    async def redeemed(self, tenant: str, reached: list[dict]) -> int:
        """Passthrough to the peer (ط-3) — see `HttpAudience.redeemed` for the join it makes."""
        return await self._c.redeemed(tenant, reached)
