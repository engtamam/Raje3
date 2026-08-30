"""Every service with a deploy values file must actually be buildable and published.

WHY THIS EXISTS. `services/whatsapp-assistant/` shipped a complete, tested feature and a real
`deploy/services/whatsapp-assistant.values.yaml` — years of work — with no `Dockerfile` at all, and
was never added to `deploy/publish-images.sh`'s `ALL` list. The values file's own image digest sat
at the all-zero placeholder from the day it was written. `helm upgrade --install` against that
values file would have deployed a manifest naming an image that has never existed, in a service
this platform believed was ready to switch on. Two more services (`affiliate-service`, `bookings`)
had the identical gap — a Dockerfile existed but the service was never in `ALL`, so a plain
`bash deploy/publish-images.sh` (the documented "all N, in parallel" default) silently never built
them.

Nothing failed anywhere. A values file rendering correctly and a service being deployable are two
different facts, and only the first one was ever checked (see `check_a_deployed_config_boots_its_
own_service.py`'s own scope) — this is the other half.

WHAT IT DELIBERATELY DOES NOT COVER. A service under `platform/services/` (the submodule) has its
own separate build pipeline and is out of scope here entirely — only a `deploy/services/*.values.
yaml` whose name matches a directory under THIS repo's `services/` (or the special-cased `console`,
built from `apps/console/`) is checked.

    python ci/check_a_deployed_service_has_a_buildable_image.py
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
VALUES_DIR = ROOT / "deploy" / "services"
SERVICES_DIR = ROOT / "services"
PUBLISH_SCRIPT = ROOT / "deploy" / "publish-images.sh"

C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"


def _this_repo_service_names() -> set[str]:
    """Every values file whose name is a real directory under services/ — the only ones this
    repo's own publish-images.sh could ever be responsible for building."""
    out = set()
    for values in sorted(VALUES_DIR.glob("*.values.yaml")):
        name = values.name.removesuffix(".values.yaml")
        if (SERVICES_DIR / name).is_dir():
            out.add(name)
    return out


def _publish_all_list() -> set[str]:
    text = PUBLISH_SCRIPT.read_text(encoding="utf-8")
    m = re.search(r"^ALL=\(([^)]*)\)", text, re.MULTILINE)
    if not m:
        print(f"{C_R}cannot find ALL=(...) in {PUBLISH_SCRIPT.relative_to(ROOT).as_posix()} — "
              f"this gate needs re-pointing{C_N}")
        sys.exit(1)
    return set(m.group(1).split())


def main() -> int:
    names = _this_repo_service_names()
    if not names:
        print("no services/*/ directory has a matching deploy/services/*.values.yaml — "
              "this gate needs re-pointing")
        return 1

    all_list = _publish_all_list()

    missing_dockerfile = sorted(n for n in names if not (SERVICES_DIR / n / "Dockerfile").exists())
    missing_from_publish_list = sorted(names - all_list)

    bad = False
    if missing_dockerfile:
        bad = True
        print(f"{C_R}service(s) with a deploy values file but no Dockerfile — cannot be built at "
              f"all:{C_N}")
        for n in missing_dockerfile:
            print(f"  services/{n}/Dockerfile")
    if missing_from_publish_list:
        bad = True
        print(f"{C_R}service(s) never built by `bash deploy/publish-images.sh` (missing from "
              f"ALL=(...) in {PUBLISH_SCRIPT.name}):{C_N}")
        for n in missing_from_publish_list:
            print(f"  {n}")

    if bad:
        return 1
    print(f"{C_G}every one of this repo's {len(names)} deployed service(s) has a Dockerfile and "
          f"is in publish-images.sh's build list{C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
