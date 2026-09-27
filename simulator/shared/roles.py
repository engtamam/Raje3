"""The "smart link" for roles: reads the REAL `deploy/seed/roles.json` directly — the same file
this platform's own `ci/check_roles.py` treats as one half of the source of truth (the other half,
`services/operations/data/roles.seed.json`, is a byte-identical mirror by design — see that gate's
own docstring). A role added, renamed, or given a new capability shows up here the next time this
runs, with zero edits to the simulator itself.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

# simulator/shared/roles.py -> repo root is 2 parents up.
_ROLES_FILE = Path(__file__).resolve().parents[2] / "deploy" / "seed" / "roles.json"


@dataclass(frozen=True)
class Role:
    name: str
    capabilities: frozenset[str]


def load_roles(*, path: Path | None = None) -> dict[str, Role]:
    """Every real role this platform seeds, keyed by name — read fresh from disk every call (no
    caching): a role file edited between two runs of a long-lived process must be picked up, not
    served stale."""
    path = path or _ROLES_FILE
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows = raw if isinstance(raw, list) else raw.get("roles", [])
    roles: dict[str, Role] = {}
    for row in rows:
        name = row.get("name")
        if not name:
            continue
        roles[name] = Role(name=name, capabilities=frozenset(row.get("capabilities") or []))
    return roles
