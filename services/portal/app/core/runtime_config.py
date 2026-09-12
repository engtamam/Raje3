"""Policy an operator owns — editable at runtime, per tenant, without a redeploy.

Retention periods, quotas, thresholds, grace windows, provider preference. These are business
decisions, and today each one is an environment variable, which means the person who owns the
decision cannot make it. That is the gap this closes.

IT IS NOT A SECOND CONFIG SYSTEM. There is one source of truth for what a setting MEANS — the
Settings class — and this only overrides values. A knob that does not exist there cannot be set
here, so a typo in the panel is refused instead of silently stored and ignored, and there is never
a runtime value nothing reads.

THE BOOT GUARD'S RULES APPLY AT RUNTIME TOO. If production refuses to start with a negative
retention or a wildcard CORS origin, the panel must refuse the same value. Validating only at boot
means the restriction lasts exactly until someone finds the settings page, and the resulting
deployment is one no boot guard would have allowed — which is worse than never having had the
guard, because everyone believes it is still holding.

WHAT MAY NOT BE SET HERE. Wiring and secrets. A driver swapped under a live request is a class of
bug nobody can reproduce, and credentials belong in the SecretStore where they are sealed and
write-only. The deny-list is explicit rather than inferred, because a rule you can read is a rule
somebody can check.

A KNOB IS ADVERTISED ONLY IF SOMETHING READS IT. This started the other way round — every settable
field was offered to the panel — and that was wrong in the most convincing way available: the panel
accepted the change, the audit log recorded it with an actor and a timestamp, and behaviour did not
move, because nothing consulted the override. An operator would have had a receipt proving they had
raised a limit that was never raised, and no test would have failed, because a test that writes a
value and reads it back through the same store measures the store rather than the service.

So each service declares RUNTIME_POLICY: the exact keys it resolves through this class at the point
of use. Anything not declared is refused, and the default is empty — fail-closed, so forgetting to
declare a knob makes it unavailable rather than silently inert.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

_COLL = "runtime_config"

# Never settable at runtime, whatever a caller asks for. Matched as a prefix so a new adapter knob
# is covered the day it is added rather than the day somebody remembers this list.
_DENY_PREFIXES = (
    # Wiring: an adapter that changes under a live request cannot be reasoned about.
    "DATASTORE_", "CACHE_", "EVENTBUS_", "QUEUE_", "OBJECTSTORE_", "RATELIMITER_",
    "SECRETS_", "TELEMETRY_", "TOKEN_VERIFIER_",
    # Identity of the deployment itself.
    "SERVICE_", "ENV", "HOST", "PORT", "LOG_LEVEL",
)
# Secrets live in the SecretStore, sealed and write-only. Setting one here would store it in the
# clear and hand it back through any config read.
# Plurals are listed explicitly because this matches names LITERALLY. A setting called
# INBOUND_SECRETS does not end in "_SECRET", so without "_SECRETS" here it was settable from the
# panel AND readable back in the clear through the config view — a credential past every rule meant
# to stop it, found by a test rather than by reading this line.
_DENY_SUFFIXES = ("_KEY", "_KEYS", "_SECRET", "_SECRETS", "_TOKEN", "_TOKENS",
                  "_PASSWORD", "_PASSWORDS", "_DSN", "_URL", "_SALT")

# Explicit exceptions: values that LOOK like wiring by name but are ordinary policy.
_ALLOW = frozenset({
    "ASSISTANT_NOT_FOUND_TEXT", "ASSISTANT_UNAVAILABLE_TEXT",
})


class RuntimeConfigError(ValueError):
    """A value the panel must refuse, with the reason an operator can act on."""


@dataclass(frozen=True)
class Override:
    key: str
    value: Any
    tenant: str = ""
    set_by: str = ""      # a pseudonym, never an identity
    set_at: str = ""


def settable(key: str, settings_cls, policy: frozenset[str] | None = None) -> bool:
    """May this knob be changed at runtime?

    `policy` is the service's RUNTIME_POLICY — the keys it actually resolves through RuntimeConfig
    at the point of use. Empty by default, so a service that has declared nothing offers nothing:
    an advertised knob nothing reads is worse than an absent one, because the panel reports success
    and the audit log records a change that never took effect.
    """
    allowed = policy if policy is not None else frozenset()
    if key not in allowed:
        return False
    if key not in getattr(settings_cls, "model_fields", {}) and key not in _ALLOW:
        return False
    if any(key.startswith(p) for p in _DENY_PREFIXES):
        return False
    return not any(key.endswith(s) for s in _DENY_SUFFIXES)


class RuntimeConfig:
    def __init__(self, store, settings_cls, *, now=None, validate=None,
                 policy: frozenset[str] | None = None) -> None:
        self._s = store
        self._cls = settings_cls
        # The keys this service resolves through here at the point of use. Declared rather than
        # inferred: the whole failure this prevents is a knob that looks live and is not.
        self._policy = policy if policy is not None else frozenset()
        self._now = now or (lambda: "")
        # The service's own boot guard, so runtime and startup enforce identical rules rather than
        # two implementations that drift.
        self._validate = validate

    @staticmethod
    def _key_of(tenant: str, key: str) -> str:
        return f"{tenant or '*'}|{key}"

    def _coerce(self, key: str, raw: Any) -> Any:
        """Cast to the type the Settings field declares, or refuse.

        A retention of "ninety" stored as a string would pass validation and then fail at the
        comparison that uses it — days later, in a sweeper, at 3am.
        """
        field = self._cls.model_fields[key]
        want = field.annotation
        try:
            if want is bool:
                if isinstance(raw, bool):
                    return raw
                s = str(raw).strip().lower()
                if s in ("true", "1", "yes", "on"):
                    return True
                if s in ("false", "0", "no", "off"):
                    return False
                raise ValueError("expected true or false")
            if want is int:
                return int(raw)
            if want is float:
                return float(raw)
            return str(raw)
        except (TypeError, ValueError) as exc:
            raise RuntimeConfigError(
                f"{key}: {raw!r} is not a valid {getattr(want, '__name__', want)} — "
                f"a value stored in the wrong type passes here and fails later, "
                f"inside whatever uses it") from exc

    # ── write ─────────────────────────────────────────────────────────────────
    async def set(self, *, tenant: str, key: str, value: Any, actor_ref: str = "") -> Override:
        if not settable(key, self._cls, self._policy):
            # One message for "no such knob" and "not settable", because listing which internal
            # settings exist is itself information an operator does not need and an attacker does.
            raise RuntimeConfigError(
                f"{key} cannot be changed at runtime. Wiring and credentials are deploy-time: a "
                f"driver that changes under a live request cannot be reasoned about, and secrets "
                f"belong in the credential store where they are sealed and write-only. Anything "
                f"this service does not read at runtime is refused too, because a knob the panel "
                f"accepts and nothing consults reports a change that never happened.")
        typed = self._coerce(key, value)

        if self._validate is not None:
            # The boot guard, applied to the value that WOULD result. Validating only at startup
            # means the rule lasts until somebody finds the settings page.
            self._validate(key, typed)

        row = {"id": self._key_of(tenant, key), "tenant": tenant, "key": key,
               "value": json.dumps(typed), "set_by": actor_ref, "set_at": self._now()}
        await self._s.put(_COLL, row["id"], row)
        return Override(key=key, value=typed, tenant=tenant, set_by=actor_ref, set_at=row["set_at"])

    async def clear(self, *, tenant: str, key: str) -> bool:
        """Remove an override so the configured default applies again."""
        return await self._s.delete(_COLL, self._key_of(tenant, key))

    async def _drain(self, where: dict[str, Any]) -> list[dict]:
        """Every row matching `where`, across as many pages as it takes.

        A scope's rows are bounded by the service's own RUNTIME_POLICY — `set()` refuses any key
        `settable()` does not allow, so a tenant can never hold more overrides than the service
        declares knobs for. That is small in every case this codebase has, but a single
        `find(..., limit=500)` still silently dropped anything past the first page with no signal
        to the caller — fixed 2026-09-12, a real gap a QA audit found. Draining every page here
        keeps the read honest without inventing a truncation flag for a collection that is never
        actually unbounded.
        """
        out: list[dict] = []
        cursor: str | None = None
        while True:
            rows, cursor = await self._s.find(_COLL, where, limit=500, sort=("key", "asc"), after=cursor)
            out.extend(rows)
            if not cursor or not rows:
                break
        return out

    # ── read ──────────────────────────────────────────────────────────────────
    async def get(self, *, tenant: str, key: str, default: Any) -> Any:
        """The effective value: tenant override, then platform override, then config."""
        for scope in ([tenant, ""] if tenant else [""]):
            row = await self._s.get(_COLL, self._key_of(scope, key))
            if row:
                try:
                    return json.loads(row["value"])
                except ValueError:
                    # A corrupt row must not take the service down: the configured default is a
                    # working answer, and a broken override is an operator problem rather than an
                    # outage.
                    return default
        return default

    async def effective(self, *, tenant: str, settings) -> dict[str, Any]:
        """Every settable knob and its current value — what the panel renders.

        Never includes a denied key, so a credential or a DSN cannot appear in a config read even
        by accident.

        ONE ROUND TRIP PER SCOPE, NOT PER KEY. This used to `await self.get(...)` for each policy
        key, and `get` itself does up to two sequential store round trips (tenant-scoped, then
        platform-wide) — rendering the config panel meant up to 2 × len(policy) round trips in
        series. `overrides()` below already fetches a whole scope in one `find()`; the same move
        here: one `find()` for tenant-scoped rows, one for platform-wide rows, then apply the same
        tenant-then-platform-then-default resolution per key in memory.
        """
        tenant_rows: dict[str, dict] = {}
        if tenant:
            rows = await self._drain({"tenant": tenant})
            tenant_rows = {r["key"]: r for r in rows}
        platform_rows_list = await self._drain({"tenant": ""})
        platform_rows = {r["key"]: r for r in platform_rows_list}

        out: dict[str, Any] = {}
        for key in sorted(self._policy):
            if not settable(key, self._cls, self._policy):
                continue
            default = getattr(settings, key, None)
            row = tenant_rows.get(key) if tenant else None
            if row is None:
                row = platform_rows.get(key)
            if row is None:
                out[key] = default
                continue
            try:
                out[key] = json.loads(row["value"])
            except ValueError:
                # Same rule as `get()`: a corrupt row must not take the service down — the
                # configured default is a working answer, and a broken override is an operator
                # problem rather than an outage.
                out[key] = default
        return out

    async def overrides(self, *, tenant: str) -> list[Override]:
        rows = await self._drain({"tenant": tenant})
        out = []
        for r in rows:
            try:
                value = json.loads(r["value"])
            except ValueError:
                continue
            out.append(Override(key=r["key"], value=value, tenant=tenant,
                                set_by=r.get("set_by", ""), set_at=r.get("set_at", "")))
        return out
