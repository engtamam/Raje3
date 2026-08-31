# =============================================================================
# secrets-admin — Composition root (config-driven port -> adapter wiring)
# -----------------------------------------------------------------------------
# The registry is the ALLOWLIST: only listed drivers can be constructed, so an
# unknown/injected driver is impossible (fail-fast ConfigError at boot).
#
# FIVE PORTS, WHERE EVERY OTHER SERVICE HAS TEN, AND THE ABSENCES ARE THE POINT.
#
# There is no datastore, no event bus, no queue and no object store here, because this service
# holds nothing: the k8s Secret objects it patches ARE the store, and they already carry the value,
# its last four characters, and who set it when. Wiring a Postgres would not add durability — it
# would add a second copy of a fact with one owner, and a screen that shows the stale one on the
# day the two disagree.
#
# What is left is exactly what a write needs to be legitimate: who is asking (token_verifier),
# how often they may ask (rate_limiter), that the ask was witnessed (audit_sink), and the one
# adapter that does the work (k8s).
# =============================================================================
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.adapters.audit_sink.http import HttpAuditSink
from app.adapters.audit_sink.null import NullAuditSink
from app.adapters.cache.memory import MemoryCache
from app.adapters.cache.redis import RedisCache
from app.adapters.k8s_client import K8sClient, UrllibTransport
from app.adapters.rate_limiter.memory import MemoryRateLimiter
from app.adapters.rate_limiter.redis import RedisRateLimiter
from app.adapters.secrets.env import EnvSecrets
from app.adapters.secrets.file import FileSecrets
from app.adapters.telemetry.stdout import StdoutTelemetry
from app.adapters.token_verifier.hs256 import HS256Verifier
from app.adapters.token_verifier.jwks import JWKSVerifier
from app.adapters.token_verifier.null import NullVerifier
from app.adapters.token_verifier.rs256 import RS256Verifier
from app.config import Settings
from app.ports.cache import Cache
from app.ports.errors import ConfigError
from app.ports.rate_limiter import RateLimiter
from app.ports.secrets_provider import SecretsProvider
from app.ports.telemetry import Telemetry
from app.ports.token_verifier import TokenVerifier

Builder = Callable[[Settings], Any]

# ── Registries (the allowlist) — driver name -> builder ─────────────────────
_CACHE: dict[str, Builder] = {
    "memory": lambda s: MemoryCache(),
    "redis": lambda s: RedisCache(s.CACHE_URL),
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
    "redis": lambda s: RedisRateLimiter(s.RATELIMIT_URL, s.RATELIMIT_MAX,
                                        s.RATELIMIT_WINDOW_SECONDS, degrade=s.RATELIMIT_DEGRADE),
}
# Where privileged actions are witnessed. `null` records nothing and SAYS so — the boot guard
# refuses it in production, because a chain that verifies perfectly while empty is a control that
# exists only on paper.
#
# NO `eventbus` SINK HERE, and dropping it is not a trim. That sink's receipt means PUBLISHED, not
# RECORDED — and every action this service performs is `critical`, which means it is REFUSED unless
# it can be proved recorded. A sink that cannot tell those apart would turn the fail-closed rule
# into a fail-open one without changing a line of route code.
_AUDIT_SINK: dict[str, Builder] = {
    "null": lambda s: NullAuditSink(),
    "http": lambda s: HttpAuditSink(s.audit_ingest_url, s.INTERNAL_SERVICE_TOKEN,
                                    timeout=s.AUDIT_TIMEOUT_SECONDS),
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
    cache: Cache
    secrets: SecretsProvider
    token_verifier: TokenVerifier
    rate_limiter: RateLimiter
    telemetry: Telemetry
    audit_sink: Any = None
    #: The only adapter that does this service's actual work.
    k8s: Any = None

    def describe(self) -> list[dict[str, str]]:
        """[{port, driver}] for the service manifest."""
        return [
            {"port": "cache", "driver": self.cache.driver},
            {"port": "secrets", "driver": self.secrets.driver},
            {"port": "token_verifier", "driver": self.token_verifier.driver},
            {"port": "rate_limiter", "driver": self.rate_limiter.driver},
            {"port": "telemetry", "driver": self.telemetry.driver},
        ] + ([{"port": "audit_sink", "driver": self.audit_sink.driver}]
             if self.audit_sink is not None else [])

    def health_probes(self) -> dict[str, Any]:
        """name -> async health() for adapters that support it (readiness).

        THE K8S CLIENT IS DELIBERATELY NOT A READINESS PROBE. A probe against the API server would
        make this pod's readiness a function of the control plane's, so a slow apiserver would take
        the pod out of the endpoints and the operator would lose the screen at exactly the moment
        the cluster was misbehaving. The failure belongs on the request, where it can be read.
        """
        probes: dict[str, Any] = {}
        for name in ("cache", "rate_limiter"):
            adapter = getattr(self, name)
            probe = getattr(adapter, "health_state", None) or getattr(adapter, "health", None)
            if probe is not None:
                probes[name] = probe
        return probes

    async def close(self) -> None:
        for name in ("cache", "rate_limiter"):
            adapter = getattr(self, name)
            close = getattr(adapter, "close", None)
            if close is not None:
                try:
                    await close()
                except Exception:
                    pass


def build_container(settings: Settings) -> Container:
    """Resolve every port from config. Fail-fast on any unknown driver."""
    return Container(
        cache=_pick(_CACHE, settings.CACHE_DRIVER, "cache", settings),
        secrets=_pick(_SECRETS, settings.SECRETS_DRIVER, "secrets", settings),
        token_verifier=_pick(_TOKEN, settings.TOKEN_VERIFIER_DRIVER, "token_verifier", settings),
        rate_limiter=_pick(_RATELIMITER, settings.RATELIMITER_DRIVER, "rate_limiter", settings),
        telemetry=_pick(_TELEMETRY, settings.TELEMETRY_DRIVER, "telemetry", settings),
        audit_sink=_pick(_AUDIT_SINK, settings.AUDIT_SINK_DRIVER, "audit_sink", settings),
        # THE TRANSPORT IS A SEPARATE OBJECT so a test can hand in a fake one and assert the exact
        # PATCH bodies this would send. There is no cluster to test against from a laptop, and a
        # test that needs one is a test nobody runs.
        k8s=K8sClient(UrllibTransport(ca_file=settings.K8S_CA_FILE,
                                      timeout=settings.K8S_TIMEOUT_SECONDS),
                      host=settings.KUBERNETES_SERVICE_HOST,
                      port=settings.KUBERNETES_SERVICE_PORT,
                      token_file=settings.K8S_TOKEN_FILE),
    )
