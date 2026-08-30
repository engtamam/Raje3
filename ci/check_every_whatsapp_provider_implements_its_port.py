"""Every WhatsApp send provider registered in notification-service must fully implement the port.

WHY THIS EXISTS. `WhatsAppProvider` (platform/services/notification-service/app/ports/
whatsapp_provider.py) is a Protocol with TWO methods — `send` and `send_interactive` — plus a
`driver` attribute. `_WHATSAPP_PROVIDERS` in that service's container.py is a dict of driver name ->
builder lambda, and `FailoverWhatsApp` (app/adapters/failover.py) tries every registered provider in
`WHATSAPP_CHAIN` order, trusting each one to answer the full port. A provider class that is
registered but only implements `send` — the easy half to remember, since it is the one exercised by
every ordinary reminder/campaign send — passes every test that never confirms a booking or redeems a
reward, and fails silently in production the first time a real customer's WhatsApp-assistant
conversation tries to render a button.

THIS IS THE GATE THAT WOULD HAVE CAUGHT A HALF-BUILT PROVIDER BEFORE IT SHIPPED. It reads
`_WHATSAPP_PROVIDERS` directly out of container.py, resolves each class the dict actually
instantiates, and checks that class's own `app/adapters/whatsapp/*.py` definition for both required
methods and the `driver` class attribute — not by running the code, by reading the AST, so it costs
nothing and needs no cluster.

THIS REPO DOES NOT OWN notification-service'S CODE — it lives in the `platform/` submodule, a
separate team's repository we consume rather than edit (see any of this repo's own service
docstrings on the hexagonal "consume, do not reimplement" rule). This gate is READ-ONLY by design:
it can catch and report a violation, but this repo is never the place that fixes one — a failure
here is a finding to hand to the platform team, not a diff to send them.

    python ci/check_every_whatsapp_provider_implements_its_port.py
"""
from __future__ import annotations

import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SVC = ROOT / "platform" / "services" / "notification-service" / "app"
CONTAINER = SVC / "container.py"
ADAPTERS_DIR = SVC / "adapters" / "whatsapp"
PORT_FILE = SVC / "ports" / "whatsapp_provider.py"

C_G, C_R, C_Y, C_N = "\033[32m", "\033[31m", "\033[33m", "\033[0m"

REQUIRED_METHODS = {"send", "send_interactive"}
REQUIRED_ATTR = "driver"


def _registered_classes(text: str) -> dict[str, str]:
    """`{driver_name: ClassName}` from `_WHATSAPP_PROVIDERS = {"name": lambda s: ClassName(...), ...}`."""
    m = re.search(r"_WHATSAPP_PROVIDERS:\s*dict\[[^\]]*\]\s*=\s*\{(.*?)\n\}", text, re.DOTALL)
    if not m:
        return {}
    out: dict[str, str] = {}
    for line in m.group(1).splitlines():
        entry = re.match(r'\s*"([\w-]+)"\s*:\s*lambda\s+\w+\s*:\s*(\w+)\(', line)
        if entry:
            out[entry.group(1)] = entry.group(2)
    return out


def _class_capabilities(text: str, class_name: str) -> tuple[set[str], bool] | None:
    """(method names defined, has a class-level `driver` attribute) for one class, or None if the
    class is not defined in this text at all."""
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            methods = {n.name for n in node.body
                      if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)}
            has_driver = any(
                isinstance(n, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id == REQUIRED_ATTR for t in n.targets)
                or (isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)
                    and n.target.id == REQUIRED_ATTR)
                for n in node.body)
            return methods, has_driver
    return None


def main() -> int:
    if not CONTAINER.exists() or not PORT_FILE.exists():
        print(f"{C_Y}platform/services/notification-service not found under this checkout — "
              f"the submodule may not be initialised (git submodule update --init). Skipping "
              f"rather than failing the build over a checkout, not a code, gap.{C_N}")
        return 0

    registered = _registered_classes(CONTAINER.read_text(encoding="utf-8"))
    if not registered:
        print(f"{C_R}could not find _WHATSAPP_PROVIDERS in {CONTAINER.relative_to(ROOT).as_posix()} "
              f"— this gate needs re-pointing{C_N}")
        return 1

    adapter_files = list(ADAPTERS_DIR.glob("*.py")) if ADAPTERS_DIR.is_dir() else []
    bad: list[str] = []
    checked = 0
    for driver, class_name in sorted(registered.items()):
        found = None
        for f in adapter_files:
            found = _class_capabilities(f.read_text(encoding="utf-8"), class_name)
            if found is not None:
                where = f.relative_to(ROOT).as_posix()
                break
        if found is None:
            bad.append(f'"{driver}" -> {class_name}(): class not found in any '
                      f"{ADAPTERS_DIR.relative_to(ROOT).as_posix()}/*.py")
            continue
        checked += 1
        methods, has_driver = found
        missing = REQUIRED_METHODS - methods
        if missing:
            bad.append(f'"{driver}" -> {class_name} ({where}): missing '
                      f"{', '.join(sorted(missing))} — WhatsAppProvider is not fully implemented")
        if not has_driver:
            bad.append(f'"{driver}" -> {class_name} ({where}): no `driver` class attribute')

    if bad:
        print(f"{C_R}a registered WhatsApp send provider does not fully implement "
              f"WhatsAppProvider:{C_N}")
        for line in bad:
            print("  " + line)
        print(f"\n{C_Y}This repo does not own notification-service's code (platform/ submodule) — "
              f"report this to the platform team rather than editing it here.{C_N}")
        return 1
    print(f"{C_G}every registered WhatsApp send provider ({checked}) fully implements "
          f"WhatsAppProvider{C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
