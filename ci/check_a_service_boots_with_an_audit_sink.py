"""Every deployed service sets a real AUDIT_SINK_DRIVER — never left at the "null" default.

WHY THIS EXISTS. `services/*/app/config.py::assert_audit_config_ok` refuses to boot in production
when `AUDIT_SINK_DRIVER` is left at its code-level default, `"null"` — every service that records a
CRITICAL audited action (a booking confirmed, points redeemed, a subscription changed) is built to
fail closed rather than run with no witness for those. `deploy/services/whatsapp-assistant.values.
yaml` simply never set `AUDIT_SINK_DRIVER`/`AUDIT_SERVICE_URL` at all — every sibling service's
values file had the same two lines, this one never did — which meant the very first production boot
of that service would have crash-looped on its own safety guard, discovered only by watching pods
restart forever rather than by anything in CI.

    python ci/check_a_service_boots_with_an_audit_sink.py
"""
from __future__ import annotations

import pathlib
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
VALUES_DIR = ROOT / "deploy" / "services"
SERVICES_DIR = ROOT / "services"

C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"

# The exact default `config.py::AUDIT_SINK_DRIVER` ships with, everywhere — a values file that
# repeats it explicitly is exactly as unbootable in production as one that never set it at all.
NULL_DRIVER = "null"


def main() -> int:
    files = sorted(v for v in VALUES_DIR.glob("*.values.yaml")
                   if (SERVICES_DIR / v.name.removesuffix(".values.yaml")).is_dir())
    if not files:
        print("no services/*/ directory has a matching deploy/services/*.values.yaml — "
              "this gate needs re-pointing")
        return 1

    bad: list[str] = []
    for values in files:
        name = values.name.removesuffix(".values.yaml")
        try:
            doc = yaml.safe_load(values.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            print(f"cannot parse {values.relative_to(ROOT).as_posix()}: {exc}")
            return 1
        env = (doc.get("env") or {})
        driver = str(env.get("AUDIT_SINK_DRIVER") or "").strip()
        if not driver or driver == NULL_DRIVER:
            bad.append(f"{name}: AUDIT_SINK_DRIVER is {driver!r} — this service will refuse to "
                      f"boot in production (assert_audit_config_ok)")

    if bad:
        print(f"{C_R}service(s) with no real audit sink configured:{C_N}")
        for line in bad:
            print("  " + line)
        return 1
    print(f"{C_G}every one of {len(files)} deployed service(s) has a real AUDIT_SINK_DRIVER{C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
