"""The base boot env every real service in this fleet needs, regardless of which one — the same
minimum every HTTP integration test across this codebase already sets (`ENV=test`,
`INTERNAL_SERVICE_TOKEN`, `PII_SALT`, a generous `RATELIMIT_MAX` so a simulator scenario's own
concurrency/load isn't rate-limited into failures that have nothing to do with the scenario). An
app-specific module (e.g. `apps/operations/`) merges this with its own extra required vars, if any.
"""
from __future__ import annotations


def base_env() -> dict[str, str]:
    return {
        "ENV": "test",
        "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "PII_SALT": "s" * 32,
        "RATELIMIT_MAX": "100000",
    }
