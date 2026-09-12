"""platform-owner's own role description says it out loud: «كل صلاحيات المنصة» — every platform
capability, held explicitly rather than by a wildcard (`deploy/seed/operator-roles.json`'s own
comment on this role: a `*` would silently grant whatever gets added next, to nobody who ever
reviewed it). "Explicitly" only holds if something checks that the list is actually complete.

FOUND LIVE, THE DAY THIS WAS WRITTEN: `platform.notifications` — the capability
notification-service's own `POST /api/v1/templates` route enforces (`_PLATFORM_CAP` in
`platform/services/notification-service/app/api/v1/notifications.py`) — was never granted to
platform-owner at all. Not a typo in the ROUTE; a gap in OUR OWN seed file, which we own and can
fix ourselves (the route's enforcement lives in the vendored `platform/` submodule and is not
ours to edit — see `platform/deploy/seed/seed-templates.sh`'s sibling files for what IS ours).
Two more of the same shape (`platform.files`, `platform.zatca`) turned up the same run — a real,
repeating pattern, not a one-off.

WHY A REGEX OVER SOURCE, NOT `admin_actions.py`'s OWN DECLARED CAPABILITY. That file can drift from
what a route actually enforces — notification-service's own `admin_actions.py` declares
`/api/v1/templates` as capability `"notifications.templates"`, while the route itself checks
`require_capability("platform.notifications")`. The declaration is documentation; the
`require_capability(...)` call IS the door. This gate reads the door, the same "trust the
enforcement, not the label" posture `check_capability_truth.py` already holds.

SCOPE: every `platform.*` string passed to `require_capability(...)` anywhere under `platform/
services/*/app` (the vendored base-services code) or `services/*/app` (ours) — a plain literal
scan, matching this repo's own established convention for this class of check.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROLES = ROOT / "deploy" / "seed" / "operator-roles.json"
_PATTERN = re.compile(r'require_capability\(\s*["\'](platform\.[a-zA-Z0-9_]+)["\']')


def enforced_platform_capabilities() -> set[str]:
    out: set[str] = set()
    for base in (ROOT / "platform" / "services", ROOT / "services"):
        for path in sorted(base.glob("*/app/**/*.py")):
            if "__pycache__" in path.parts:
                continue
            out.update(_PATTERN.findall(path.read_text(encoding="utf-8")))
    return out


def platform_owner_capabilities() -> set[str]:
    roles = json.loads(ROLES.read_text(encoding="utf-8"))
    for role in roles.get("roles", roles if isinstance(roles, list) else []):
        if role.get("name") == "platform-owner":
            return set(role.get("capabilities", []))
    raise SystemExit(f"{ROLES}: no role named 'platform-owner' found")


def main() -> int:
    enforced = enforced_platform_capabilities()
    held = platform_owner_capabilities()
    missing = sorted(enforced - held)
    if missing:
        print("\033[31m  ✗ platform-owner is missing capabilities its own routes enforce:\033[0m")
        for cap in missing:
            print(f"\033[31m    ✗\033[0m  {cap}")
        print(f"\n\033[31m  ✗ {len(missing)} platform capability(ies) unreachable by the role "
              f"whose own description promises all of them\033[0m")
        return 1
    print(f"\033[32m  ✔ platform-owner holds every one of the {len(enforced)} platform.* "
          f"capabilities a route actually enforces\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
