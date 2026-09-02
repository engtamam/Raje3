#!/usr/bin/env python3
"""api-gateway's ADMIN_SERVICES must name only services that are actually deployed — and a console
screen that goes dark because its one action is missing from the catalog must say WHY, not guess.

WHY THIS GATE EXISTS AT ALL. Found live: `secrets-admin` sits in `deploy/services-pending/` (moved
there deliberately — its image digest was a placeholder, and it needs a `platform/` chart change
before it can run), but `deploy/services/api-gateway.values.yaml`'s own ADMIN_SERVICES still names
it. The admin panel's catalog aggregator (platform/services/api-gateway's own
`core/admin_catalog.py::build_catalog`) dutifully reports it `unreachable` — exactly as designed,
"a missing service should be visible, not invisible" — and that half worked.

The OTHER half didn't: `apps/console/src/admin/AdminProviderSecrets.tsx` renders "هذه الشاشة ليست
ضمن صلاحياتك" (this screen is not within your permissions) whenever secrets-admin's own
`secrets.list` action is absent from the catalog — a condition that is IDENTICAL whether the
operator genuinely lacks the capability OR the service that would have declared the action never
answered at all. An operator with full `platform.secrets_manage` on their own token read "you lack
permission" and had no way to tell it was actually "this service isn't deployed yet" — the wrong
diagnosis sent them looking in the wrong place (their own account) for a problem that lived in
deploy config.

TWO CHECKS, ONE ROOT CAUSE EACH:

  1. STATIC — every name ADMIN_SERVICES lists must have a real `deploy/services/<name>.values.yaml`
     (deployed), not merely exist somewhere under `services-pending/` or a submodule. Catches the
     exact defect above, and any future one shaped like it, before a human has to click through the
     panel to notice a service went quiet.

  2. STRUCTURAL — a console admin screen that shows a bespoke "no permission"-shaped EmptyState
     purely because ITS OWN action id is missing from the catalog must ALSO reference
     `catalog.unreachable` somewhere in the same file. Not enforcing exact wording (screens differ,
     and should) — enforcing that the SIGNAL to distinguish the two causes is at least read, so a
     screen shaped like AdminProviderSecrets.tsx's old one cannot ship again with no way to tell an
     absent permission from an absent service.

WHAT THIS GATE CANNOT CHECK: whether a `services-pending/`-parked service ever gets promoted back —
that is a human's call to make once its own blocker (here: the platform/ chart change) is resolved,
same as every `_pending` marker on this repo already relies on someone reading it.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GATEWAY_VALUES = ROOT / "deploy" / "services" / "api-gateway.values.yaml"
DEPLOYED_DIR = ROOT / "deploy" / "services"
CONSOLE_ADMIN_DIR = ROOT / "apps" / "console" / "src" / "admin"

# Arabic phrasing this repo actually uses for "you don't have permission to see this" — matched
# loosely (a substring of the *root*, صلاحي, covers صلاحية/صلاحيات/صلاحيتك/etc.) because the point
# is catching the SHAPE of the message, not policing exact wording future screens might choose.
_NO_PERMISSION_MARKER = "صلاحي"


def _admin_services_names() -> dict[str, int]:
    """name -> the 1-indexed line it appears on, parsed straight out of the GATEWAY_ROUTES-adjacent
    `ADMIN_SERVICES: "a=url,b=url,..."` line — a tiny hand parser rather than a YAML+JSON round
    trip, because the value is a single quoted scalar this file's own comments already warn is
    fragile to over-clever parsing (see api-gateway.values.yaml's own note on the note that broke
    the block scalar once)."""
    if not GATEWAY_VALUES.exists():
        return {}
    text = GATEWAY_VALUES.read_text(encoding="utf-8")
    out: dict[str, int] = {}
    for i, line in enumerate(text.splitlines(), start=1):
        m = re.search(r'ADMIN_SERVICES:\s*"([^"]*)"', line)
        if not m:
            continue
        for pair in m.group(1).split(","):
            name = pair.split("=", 1)[0].strip()
            if name:
                out[name] = i
        break
    return out


def check_targets_deployed() -> list[str]:
    problems = []
    for name, line in sorted(_admin_services_names().items()):
        deployed = (DEPLOYED_DIR / f"{name}.values.yaml").exists()
        if not deployed:
            problems.append(
                f"api-gateway.values.yaml:{line}: ADMIN_SERVICES names {name!r}, but there is no "
                f"deploy/services/{name}.values.yaml — the admin panel's catalog will report it "
                f"unreachable forever, and any console screen keyed to one of its actions will "
                f"show whatever message it shows for 'action not found', which usually is NOT "
                f"'this service isn't deployed yet'. Either finish deploying it, or drop it from "
                f"ADMIN_SERVICES until it is (that alone quiets the panel's own unreachable notice "
                f"and empty screens, without losing the reminder that it's pending — that reminder "
                f"belongs in deploy/services-pending/, which is where the file already is).")
    return problems


def check_screens_distinguish_unreachable() -> list[str]:
    problems = []
    if not CONSOLE_ADMIN_DIR.exists():
        return problems
    for path in sorted(CONSOLE_ADMIN_DIR.glob("*.tsx")):
        if path.name.endswith(".test.tsx"):
            continue
        text = path.read_text(encoding="utf-8")
        if _NO_PERMISSION_MARKER not in text:
            continue
        # A screen that mentions permission-denial at all is expected to have READ the catalog's
        # own signal for "a service didn't answer" — not necessarily branched on it with different
        # copy (that's a design choice), but at least looked at it, so a future edit has the
        # information available rather than guessing the way AdminProviderSecrets.tsx once did.
        if "unreachable" in text:
            continue
        rel = path.relative_to(ROOT)
        problems.append(
            f"{rel}: shows a permission-denial-shaped message (contains {_NO_PERMISSION_MARKER!r}) "
            f"but never reads `catalog.unreachable` anywhere in the file — so it cannot tell an "
            f"operator who genuinely lacks a capability apart from one whose service simply never "
            f"answered when the catalog was built. See AdminProviderSecrets.tsx's own header for "
            f"the incident this gate exists to keep from repeating.")
    return problems


def main() -> int:
    problems = check_targets_deployed() + check_screens_distinguish_unreachable()
    if problems:
        print("\033[31m✖ admin catalog targets / unreachable-signal check failed:\033[0m")
        for p in problems:
            print(f"    \033[31m{p}\033[0m")
        return 1
    print("\033[32m✔ every ADMIN_SERVICES target is deployed, and every permission-denial screen "
          "reads catalog.unreachable\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
