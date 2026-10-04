"""The base boot env every real service in this fleet needs, regardless of which one — the same
minimum every HTTP integration test across this codebase already sets (`ENV=test`,
`INTERNAL_SERVICE_TOKEN`, `PII_SALT`, a generous `RATELIMIT_MAX` so a simulator scenario's own
concurrency/load isn't rate-limited into failures that have nothing to do with the scenario). An
app-specific module (e.g. `apps/operations/`) merges this with its own extra required vars, if any.
"""
from __future__ import annotations

# Exposed as constants (not just baked into base_env's own dict) so a module that needs to speak
# to a spawned service directly (e.g. apps/identity/directory.py's own internal-token call) uses
# the EXACT SAME value every spawned service was booted with, never a second, possibly-drifting
# copy of it.
INTERNAL_SERVICE_TOKEN = "t" * 40
PII_SALT = "s" * 32


def base_env() -> dict[str, str]:
    return {
        "ENV": "test",
        "INTERNAL_SERVICE_TOKEN": INTERNAL_SERVICE_TOKEN,
        "PII_SALT": PII_SALT,
        "RATELIMIT_MAX": "100000",
    }
