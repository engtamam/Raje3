#!/usr/bin/env python3
# =============================================================================
# check_cron_bodies.py — a scheduled route must accept the empty POST its cron sends.
#
# WHAT THIS COST US. Every heartbeat in the product was failing, nightly, for days: the insights
# snapshot, the loyalty expiry sweep, the campaign tick, the reminder tick. The platform's
# scheduled-job template posts an EMPTY payload with a JSON content type; a route that declares a
# required Pydantic body answers 422 before a line of its own code runs.
#
# AND NOTHING SAID SO. Every probe green, every route answering, every dashboard showing «أحسب
# مؤشرات محلك الآن» for ever and every reminder simply not going out. The only evidence was a
# Job's exit code, in a resource nobody reads on a good day. It was found because an owner
# photographed a screen that had been "computing" for eighteen hours.
#
# SO THE SHAPE IS CHECKED HERE, where it is cheap: for every `cronJobs` entry in every values
# file, find the route it targets and require that its body parameter be optional — or that it
# take no body at all, which is the better answer for a route only a scheduler calls.
# =============================================================================
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEPLOY = ROOT / "deploy" / "services"
SERVICES = ROOT / "services"

C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"


def cron_paths(values: Path) -> list[str]:
    """The `path:` of every cronJobs entry. Read with a regex rather than a YAML parser, because
    these files are read by three other guards the same way and a dependency here is a dependency
    in CI."""
    text = values.read_text(encoding="utf-8")
    block = text.split("cronJobs:", 1)
    if len(block) < 2:
        return []
    out: list[str] = []
    for line in block[1].splitlines():
        stripped = line.strip()
        if stripped.startswith("path:"):
            out.append(stripped.split(":", 1)[1].strip().strip('"\''))
        elif stripped and not line.startswith((" ", "-", "\t")) and not stripped.startswith("#"):
            break        # a new top-level key: the cronJobs block is over
    return out


def main() -> int:
    problems: list[str] = []
    checked = 0

    for values in sorted(DEPLOY.glob("*.values.yaml")):
        service = values.name.replace(".values.yaml", "")
        internal = SERVICES / service / "app" / "api" / "internal.py"
        if not internal.is_file():
            continue                     # a platform service: not ours to check
        source = internal.read_text(encoding="utf-8")

        for path in cron_paths(values):
            route = path.replace("/internal", "", 1)
            # NON-GREEDY THROUGH THE DECORATOR, because `Depends(require_internal_token)` closes a
            # paren inside it — a `[^)]*` here matches nothing and reports every route in the
            # fleet as missing, which is a guard that cries wolf on its very first run.
            m = re.search(r'@router\.post\("' + re.escape(route) + r'".*?\n'
                          r'async def \w+\((.*?)\)\s*->', source, re.S)
            if not m:
                problems.append(f"{service}: the cron targets {path} and no route in "
                                f"{internal.relative_to(ROOT)} serves it — the job posts every "
                                f"night into a 404 nobody reads")
                continue
            checked += 1
            args = m.group(1)
            body = re.search(r"body:\s*([^,)=]+)(\s*=\s*[^,)]+)?", args)
            if body and not body.group(2):
                problems.append(
                    f"{service}: {path} declares a REQUIRED body ({body.group(1).strip()}), and "
                    f"the platform's scheduled job posts an empty payload — so it answers 422 on "
                    f"every schedule, silently, with every probe green. Give it a default.")

    for p in problems:
        print(f"{C_R}  ✗ {p}{C_N}")
    if problems:
        print(f"\n{C_R}  ✗ {len(problems)} scheduled route(s) cannot accept their own cron{C_N}")
        return 1
    print(f"{C_G}  ✔ all {checked} scheduled routes accept the empty POST their cron sends{C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
