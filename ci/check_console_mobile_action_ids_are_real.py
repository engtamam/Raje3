#!/usr/bin/env python3
# =============================================================================
# check_console_mobile_action_ids_are_real.py — every capability gate on console/mobile must
# name an action id a backend actually declared, or the control it guards is permanently invisible
# to everyone, owner included.
#
# FOUND LIVE (2026-10-06), TWICE IN ONE SESSION, TWO DIFFERENT SHAPES OF THE SAME MISTAKE:
#   - apps/mobile/.../coworking_screen.dart gated «مورد جديد» on `CapabilityGate(requires:
#     ['coworking.manage'])` — `coworking.manage` is only ever a CAPABILITY field on several
#     actions in services/coworking/app/user_actions.py, never an action ID of its own. The real
#     id for "add a resource" is `coworking.create_resource`. The button never rendered for
#     anyone, including the owner, and nothing said so — `/readyz` stayed green, the screen
#     rendered, it just quietly had one fewer button than it should.
#   - apps/console/.../AppLauncher.tsx and BranchesPane.tsx gated the app-store tab on
#     `action(catalog, 'operations.create_operator')` — that id was never declared either; the
#     real one is `operations.hire_member`. A code comment right next to it confidently asserted
#     it WAS real and even cited roles.seed.json, which made the bug invisible to a human reader
#     too — the comment agreed with the bug.
#
# WHY THIS IS INVISIBLE TO EVERY OTHER GATE. `Catalog.hasAll`/`action(catalog, id)` do exactly
# what they are told: look up `id` in whatever the gateway sent. A typo'd or renamed id is not a
# network error, not a 403, not a missing capability on any role — the lookup simply returns
# `undefined`/empty every time, for every operator, and the control silently never renders. No
# exception, no failed request, no CI test exercises a button that was never there to click.
#
# THE RULE THIS ENFORCES: every string passed to `CapabilityGate(requires: [...])` (mobile) or
# `action(catalog, '...')` (console) must be a real `"id"` from SOME service's own
# `user_actions.py` — ours (services/*/app/user_actions.py) or platform's
# (platform/services/*/app/user_actions.py), since both aggregate into the one catalogue the
# gateway serves. A string that matches neither set is this exact bug, waiting to be found live.
# =============================================================================
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"
problems: list[str] = []


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


def real_action_ids() -> set[str]:
    """Every `"id"` declared in any user_actions.py — ours and platform's alike, since the
    gateway aggregates both into one catalogue (see ADMIN_SERVICES in api-gateway.values.yaml)."""
    ids: set[str] = set()
    for base in (ROOT / "services", ROOT / "platform" / "services"):
        if not base.is_dir():
            continue
        for f in base.glob("*/app/user_actions.py"):
            try:
                tree = ast.parse(read(f))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Dict):
                    continue
                for k, v in zip(node.keys, node.values):
                    if (isinstance(k, ast.Constant) and k.value == "id"
                            and isinstance(v, ast.Constant) and isinstance(v.value, str)):
                        ids.add(v.value)
    return ids


def dart_requires(text: str) -> set[str]:
    """`CapabilityGate(requires: const [...])` / `requires: [...]` — one or more quoted ids."""
    out: set[str] = set()
    for block in re.findall(r"requires:\s*(?:const\s*)?\[([^\]]*)\]", text):
        out |= set(re.findall(r"'([a-zA-Z0-9_.]+)'", block))
    return out


def ts_action_calls(text: str) -> set[str]:
    """`action(catalog, 'id')` / `action(catalog, "id")` — the console's own lookup helper."""
    out = set(re.findall(r"action\(\s*catalog\s*,\s*'([a-zA-Z0-9_.]+)'", text))
    out |= set(re.findall(r'action\(\s*catalog\s*,\s*"([a-zA-Z0-9_.]+)"', text))
    return out


ID_RE = re.compile(r"^[a-z][a-z0-9_]*\.[a-z0-9_.]+$")

# TEMPORARY, NAMED, AND OWNED — identity-service's service-accounts endpoints are real
# (app/api/v1/service_accounts.py) but were never declared in its own user_actions.py (found by
# this gate, 2026-10-06; escalated to the sister session that owns platform/services/* directly,
# since this repo never edits that submodule — see [[platform-changes-via-sister-session]]).
# Remove this pair the moment that lands; until then this gate would otherwise block every ship
# in the repo over a gap neither this repo nor this ship can fix.
_PENDING_UPSTREAM = {"identity.list_service_accounts", "identity.revoke_service_account"}

real_ids = real_action_ids()
if not real_ids:
    problems.append("found zero user_actions.py declarations anywhere — the AST walk itself is "
                     "broken, and a check that reads nothing passes by examining an empty set")

referenced: dict[str, list[Path]] = {}

mobile_lib = ROOT / "apps" / "mobile" / "lib"
if mobile_lib.is_dir():
    for f in mobile_lib.rglob("*.dart"):
        for rid in dart_requires(read(f)):
            if ID_RE.match(rid):  # a bare word like 'required' or a non-dotted literal, skip
                referenced.setdefault(rid, []).append(f)

console_src = ROOT / "apps" / "console" / "src"
if console_src.is_dir():
    for f in console_src.rglob("*.ts*"):
        if f.name.endswith((".test.ts", ".test.tsx")):
            continue
        for rid in ts_action_calls(read(f)):
            referenced.setdefault(rid, []).append(f)

for rid, files in sorted(referenced.items()):
    if rid in real_ids or rid in _PENDING_UPSTREAM:
        continue
    locs = ", ".join(sorted({str(f.relative_to(ROOT)) for f in files}))
    problems.append(f"'{rid}' is not a real action id in any user_actions.py (ours or "
                     f"platform's) — referenced from {locs}. If this used to be real it was "
                     f"renamed and never updated here; the gate/button it guards is invisible "
                     f"to everyone, owner included.")

if problems:
    print(f"{C_R}  ✗ {len(problems)} dead action-id reference(s):{C_N}")
    for p in problems:
        print(f"    {C_R}{p}{C_N}")
    sys.exit(1)

print(f"{C_G}  ✔ every CapabilityGate/action(catalog, …) reference on console and mobile names "
      f"a real, currently-declared action id ({len(real_ids)} known across our services and "
      f"platform's){C_N}")
