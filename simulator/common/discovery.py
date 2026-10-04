"""The "smart link" piece: reads a service's OWN declared routes directly from its source code
(`app/user_actions.py` / `app/admin_actions.py`) instead of a hand-maintained list inside this
simulator — a new route, a new capability, or a changed one shows up here automatically the next
time this runs, with zero edits to the simulator itself.

SAME AST-LITERAL-EVAL PARSING EVERY OTHER CATALOG GATE IN THIS REPO ALREADY USES (see ci/
check_every_action_has_help.py's own docstring) — these files are documented as "a PURE literal
dict... no variables, no f-strings" specifically so a gate (and now this discovery module) can
read them without ever importing/executing the service's own code.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

_VARS = ("USER_ACTIONS", "ADMIN_ACTIONS")


@dataclass(frozen=True)
class DeclaredAction:
    """One route a service itself says it exposes, exactly as its own user_actions.py/
    admin_actions.py declares it — never guessed, never hand-typed here."""

    id: str
    method: str
    path: str
    capability: str
    source_file: str


def discover_actions(service_dir: Path) -> list[DeclaredAction]:
    """Every declared action across a service's own `app/user_actions.py` and
    `app/admin_actions.py` (either or both may be absent — an empty result is a real, valid
    answer, not an error: see user_actions.py's own docstring, "declaring nothing is fine")."""
    actions: list[DeclaredAction] = []
    for filename in ("user_actions.py", "admin_actions.py"):
        path = service_dir / "app" / filename
        if not path.exists():
            continue
        actions.extend(_parse(path))
    return actions


def _parse(path: Path) -> list[DeclaredAction]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list[DeclaredAction] = []
    for node in ast.walk(tree):
        target_name = getattr(getattr(node, "target", None), "id", None) or \
            (getattr(node, "targets", [None])[0].id if getattr(node, "targets", None)
             and hasattr(node.targets[0], "id") else None)
        if target_name not in _VARS:
            continue
        for elt in getattr(node.value, "elts", []):
            try:
                entry = ast.literal_eval(elt)
            except Exception:                                        # noqa: BLE001
                continue
            if not isinstance(entry, dict):
                continue
            method = entry.get("method")
            route_path = entry.get("path")
            capability = entry.get("capability")
            if not (method and route_path and capability):
                # UNDECLARED_ROUTES-style entries, or anything malformed — real gates elsewhere
                # in this repo already refuse these at CI time; discovery just skips what it
                # cannot use rather than guessing.
                continue
            found.append(DeclaredAction(
                id=str(entry.get("id") or "?"), method=str(method).upper(),
                path=str(route_path), capability=str(capability), source_file=path.name,
            ))
    return found
