#!/usr/bin/env python3
"""Every boot guard a service actually calls must pass against the values file it is deployed with.

WHAT THIS ANSWERS. "Why is there no gate that catches all these?" — asked after one night found
three of them by hand: bookings shipped with `OPERATIONS_SERVICE_URL` unset (every booking refused
with "مدة غير مضبوطة"), and operations shipped with `BILLING_PLANS_DRIVER` unset (no plan could be
listed, and `/api/v1/subscription/apps` answered `base: null` for every shop forever). Both are
guarded IN THE CODE — `assert_operations_peer_config_ok`, `assert_billing_plans_config_ok` — and
both guards ran against `deploy/services/<svc>.values.yaml` for the first time only when a real
pod crash-looped on a real server. That gap is what this closes.

WHY THIS IS THE OTHER HALF OF WHAT A GATE CAN SEE. A missing k8s Secret, an unprovisioned
database, a price list never pushed into billing-service, a role never repaired for an existing
tenant — none of those are readable from a git checkout; they are runtime state on a live cluster,
and no CI gate reaches them (that class needs an operational checklist, not a gate). A values FILE
sitting right here in the repo, compared against the boot guards the service's own `main.py`
already calls, is exactly the other half: readable, static, and it is the guard doing the
comparing rather than a person re-deriving it from the code each time.

HOW IT READS "WHAT main.py ACTUALLY CALLS" rather than every `assert_*_config_ok` method defined
on the class — a method defined and never called is the exact shape of د-2 (`is_subject_ref`
existed, unused, for a defect's whole lifetime): calling every method the class merely HAS would
test guards no boot path exercises, and miss nothing new, but say nothing true about what actually
runs.

WHAT IT CANNOT CHECK: values sourced from a k8s Secret rather than this values file (PII_SALT,
INTERNAL_SERVICE_TOKEN, BACKUP_KEK, ...) — those are stubbed non-empty here so a guard that only
asks "is this empty" still runs, but a guard that validates their SHAPE (a real PEM, a real DSN)
is not exercised by this gate. That is `mint-our-secrets.sh`'s and `pre-deploy.sh`'s territory,
not this one's.

    python ci/check_a_deployed_config_boots_its_own_service.py
"""
from __future__ import annotations

import importlib.util
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVICES = ROOT / "services"
VALUES_DIR = ROOT / "deploy" / "services"

C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"

#: Values a real deployment sources from a k8s Secret, never from the values file — stubbed
#: non-empty so an "is this empty" guard runs without this gate pretending to know a real secret.
SECRET_STUBS = {
    "PII_SALT": "s" * 32,
    "INTERNAL_SERVICE_TOKEN": "t" * 40,
    "BACKUP_KEK": "k" * 32,
    "SECRETS_KEK": "k" * 32,
    "TOKEN_PUBLIC_KEY": "-----BEGIN PUBLIC KEY-----\nstub\n-----END PUBLIC KEY-----",
    "TOKEN_HS256_SECRET": "h" * 40,
    "DATASTORE_DSN": "postgresql://u:p@host:5432/db",
    "CACHE_URL": "redis://host:6379/0",
    "EVENTBUS_URL": "redis://host:6379/0",
    "QUEUE_URL": "redis://host:6379/0",
    "RATELIMIT_URL": "redis://host:6379/0",
}

#: `KEY: "value"` — the shape every values file's `env:` block uses. Booleans and bare numbers
#: (`RATELIMIT_MAX: "600"`) already arrive quoted in these files; unquoted scalars are read as-is.
ENV_LINE = re.compile(r'^\s{2,4}([A-Z][A-Z0-9_]*):\s*"?([^"\n]*)"?\s*(?:#.*)?$')

ASSERT_CALL = re.compile(r"settings\.(assert_\w+_config_ok)\(\)")


def _read_env_block(values_path: pathlib.Path) -> dict[str, str]:
    """The `env:` mapping only — not `secretRefs`, not `drivers`, not the rest of the file."""
    text = values_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    out: dict[str, str] = {}
    in_env = False
    for line in lines:
        if re.match(r"^env:\s*$", line):
            in_env = True
            continue
        if in_env:
            if line and not line.startswith(" "):
                break                                     # the block ended
            m = ENV_LINE.match(line)
            if m:
                out[m.group(1)] = m.group(2)
    return out


def _asserts_called(main_path: pathlib.Path) -> list[str]:
    """The ORDERED list of `settings.assert_*_config_ok()` calls `create_app()` actually makes —
    not every such method the class defines. See the module docstring for why that distinction
    is the whole point."""
    text = main_path.read_text(encoding="utf-8")
    return ASSERT_CALL.findall(text)


def _load_settings_class(config_path: pathlib.Path, service: str):
    mod_name = f"_deployed_config_check_{service}"
    spec = importlib.util.spec_from_file_location(mod_name, config_path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.modules.pop(mod_name, None)
    return getattr(mod, "Settings", None)


def main() -> int:
    if not SERVICES.is_dir():
        print("no services/ directory — this gate cannot answer, so it refuses to")
        return 1

    problems: list[str] = []
    checked = 0
    for main_path in sorted(SERVICES.glob("*/app/main.py")):
        service = main_path.parents[1].name
        config_path = main_path.parent / "config.py"
        values_path = VALUES_DIR / f"{service}.values.yaml"
        if not config_path.is_file() or not values_path.is_file():
            continue                       # not one of our own services (or genuinely absent)

        asserts = _asserts_called(main_path)
        if not asserts:
            continue                       # nothing to check — main.py calls no boot guard

        Settings = _load_settings_class(config_path, service)
        if Settings is None:
            problems.append(f"{service}: could not import Settings from {config_path.name} — "
                            f"this gate cannot answer for it")
            continue

        env = {**SECRET_STUBS, **_read_env_block(values_path), "ENV": "production"}
        try:
            settings = Settings(**env)
        except Exception as exc:                                          # noqa: BLE001
            problems.append(f"{service}: the values file does not even construct Settings — {exc}")
            continue

        for name in asserts:
            fn = getattr(settings, name, None)
            if fn is None:
                problems.append(f"{service}: main.py calls settings.{name}(), which does not "
                                f"exist on Settings — a rename on one side and not the other")
                continue
            checked += 1
            try:
                fn()
            except ValueError as exc:
                problems.append(f"{service}.{name}: {exc}")

    if problems:
        print(f"{C_R}  ✘ {len(problems)} boot guard(s) would refuse the values file this service "
              f"is actually deployed with:{C_N}")
        for p in problems:
            print(f"{C_R}      {p}{C_N}")
        print(f"{C_R}\n    Each of these is main.py's OWN check, run against deploy/services/"
              f"<svc>.values.yaml — fix the values file, or the guard, whichever is wrong.{C_N}")
        return 1

    print(f"{C_G}  ✔ {checked} boot guard(s) across every service pass against their own "
          f"deployed values file{C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
