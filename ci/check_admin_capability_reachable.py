#!/usr/bin/env python3
"""Every admin_actions.py capability is granted to at least one platform role — not just declared.

WHY THIS EXISTS, AND WHAT NO OTHER GATE CATCHES. check_capability_truth.py verifies a route's
DECLARED capability matches what its handler ENFORCES — a different question. check_roles.py
verifies the same thing for the SHOP side (roles.json / nav.ts / user_actions.py). Neither one
asks the question this gate asks: is a capability an admin_actions.py action requires actually
GRANTED to any seeded operator-roles.json role at all?

FOUND LIVE, THE DAY THIS WAS WRITTEN: `notifications.templates` (notification-service's WhatsApp
template list/register/submit routes) was declared correctly, enforced correctly, and the console
screen that reaches it (AdminWhatsAppTemplates.tsx) was built correctly — and NOBODY could ever
open it. Not one seeded role, including platform-owner, held the capability. Every check that
existed passed; the screen answered "هذه الشاشة ليست ضمن صلاحياتك" to everyone who tried it,
including the person the screen was built for.

WHAT THIS DOES NOT CHECK. Whether the RIGHT role holds a capability (a judgement call for a human,
same as every other line in operator-roles.json) — only whether ANY seeded role does. A capability
reachable by nobody is a bug; a capability reachable by the wrong somebody is a decision to review,
not something this script can arbitrate.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPERATOR_ROLES = ROOT / "deploy" / "seed" / "operator-roles.json"
DEPLOY_SERVICES = ROOT / "deploy" / "services"

C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"


def deployed_service_names() -> set[str]:
    """Every service this product actually ships — a values file under deploy/services/. platform/
    carries dozens of services from the upstream chart we never turn on (zatca-service,
    verification-service, ...); their admin_actions.py declares capabilities too, and NONE of them
    is reachable by design, not by accident — there is no admin screen for a service that is not
    deployed. Scoping to what we deploy is what keeps that a non-finding instead of noise that
    would bury the real one."""
    return {p.stem.removesuffix(".values") for p in DEPLOY_SERVICES.glob("*.values.yaml")}


def admin_capabilities(root: Path, deployed: set[str]) -> dict[str, str]:
    """capability -> one "service/action_id" example that requires it, from every admin_actions.py
    under this root, for a service we actually deploy. AST-literal-eval, same technique
    check_roles.py's capabilities() uses — no import, so a service with a broken dependency still
    gets checked."""
    out: dict[str, str] = {}
    for path in sorted(root.glob("services/*/app/admin_actions.py")):
        if path.parent.parent.name not in deployed:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, OSError):
            continue
        for node in tree.body:
            name = ""
            if isinstance(node, ast.AnnAssign):
                name = getattr(node.target, "id", "")
            elif isinstance(node, ast.Assign) and node.targets:
                name = getattr(node.targets[0], "id", "")
            if name != "ADMIN_ACTIONS":
                continue
            try:
                rows = ast.literal_eval(node.value)
            except (ValueError, SyntaxError):
                continue
            for row in rows:
                cap = row.get("capability")
                if not cap or cap in out:
                    continue
                out[cap] = f"{path.parent.parent.name}/{row.get('id', '?')}"
    return out


def granted_capabilities() -> set[str]:
    roles = json.loads(OPERATOR_ROLES.read_text(encoding="utf-8"))["roles"]
    held: set[str] = set()
    for role in roles:
        held.update(role.get("capabilities") or [])
    return held


def main() -> int:
    deployed = deployed_service_names()
    required = admin_capabilities(ROOT, deployed)                    # our own services
    required.update(admin_capabilities(ROOT / "platform", deployed))  # platform/'s own — read-only
    held = granted_capabilities()

    unreachable = sorted(cap for cap in required if cap not in held)
    if unreachable:
        print(f"{C_R}  ✘ {len(unreachable)} admin capabilit(ies) declared but granted to NO role "
              f"in {OPERATOR_ROLES.relative_to(ROOT)}:{C_N}")
        for cap in unreachable:
            print(f"    {C_R}{cap}{C_N}  (e.g. {required[cap]}) — nobody can ever be granted this, "
                  f"so its screen/action refuses everyone, including platform-owner")
        return 1
    print(f"{C_G}  ✔ every admin capability ({len(required)}) is granted to at least one "
          f"platform role{C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
