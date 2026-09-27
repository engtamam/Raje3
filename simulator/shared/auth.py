"""A reusable-across-apps piece (see the README's own taxonomy: `shared/` knows this platform's
own conventions — how a JWT is shaped, which claims a service reads — never any one app's domain
logic). Every real project service this simulator drives authenticates the exact same way: a
Bearer JWT with `sub`/`iss`/`aud`/`tenant`/`caps` claims, verified by the `hs256` driver when a
service is spawned with `TOKEN_VERIFIER_DRIVER=hs256` — the same shape every HTTP integration test
across this whole codebase already uses (see e.g. services/operations/tests/integration/test_till_
referral_register.py's own `_token()` helper, which this module mirrors exactly).
"""
from __future__ import annotations

import datetime as dt

import jwt

# A fixed, deliberately obviously-fake secret/issuer/audience — this simulator only ever talks to
# services IT spawned itself (stage 4's own `run_service`), configured with these same three
# values, never a real deployed instance. Sharing one fixed triple across every spawned service
# keeps the auth wiring boring and identical everywhere a scenario needs a token.
SECRET = "simulator-hs256-secret-" + "x" * 20
ISSUER = "simulator"
AUDIENCE = "simulator"


def env_for_hs256_auth() -> dict[str, str]:
    """The env vars a spawned service needs to accept tokens minted by `mint_token` below —
    pass this into `run_service(..., env={**env_for_hs256_auth(), ...other required vars})`."""
    return {
        "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": SECRET,
        "TOKEN_ISSUER": ISSUER,
        "TOKEN_AUDIENCE": AUDIENCE,
    }


def mint_token(*, tenant: str, caps: tuple[str, ...], subject: str = "simulator") -> str:
    """A real, verifiable JWT — not a stub. Any service spawned with `env_for_hs256_auth()` will
    genuinely verify this token's signature, exactly as it would a real console/till/mobile
    token; nothing here is faked or bypassed."""
    now = dt.datetime.now(dt.timezone.utc)
    claims = {
        "sub": subject, "iss": ISSUER, "aud": AUDIENCE, "tenant": tenant,
        "exp": now + dt.timedelta(minutes=10), "iat": now, "caps": list(caps),
    }
    return jwt.encode(claims, SECRET, algorithm="HS256")


def auth_header(*, tenant: str, caps: tuple[str, ...], subject: str = "simulator") -> dict[str, str]:
    """The `Authorization` header an Action's own httpx client passes straight through."""
    return {"Authorization": f"Bearer {mint_token(tenant=tenant, caps=caps, subject=subject)}"}


def forged_token(*, tenant: str, caps: tuple[str, ...], subject: str = "attacker") -> str:
    """Stage 7's own security checks: the SAME claims shape a real token would carry, signed with
    a DIFFERENT secret the spawned service was never configured with — a service verifying HS256
    signatures correctly must refuse this outright (401), regardless of how honest-looking the
    claims inside it are. Never used by an ordinary Action; only by a security check that expects
    a refusal."""
    now = dt.datetime.now(dt.timezone.utc)
    claims = {
        "sub": subject, "iss": ISSUER, "aud": AUDIENCE, "tenant": tenant,
        "exp": now + dt.timedelta(minutes=10), "iat": now, "caps": list(caps),
    }
    return jwt.encode(claims, "a-completely-different-secret-" + "y" * 20, algorithm="HS256")


def forged_auth_header(*, tenant: str, caps: tuple[str, ...]) -> dict[str, str]:
    return {"Authorization": f"Bearer {forged_token(tenant=tenant, caps=caps)}"}
