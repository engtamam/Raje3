#!/usr/bin/env python3
# =============================================================================
# check_ratelimit_prefixes.py — every rate-limit class matches a path something serves.
#
# THE CLASS IS CHOSEN BY LONGEST-PREFIX MATCH, AND A PREFIX THAT MATCHES NOTHING FAILS SILENTLY.
# It does not error at boot, it does not log, and it does not appear in any dashboard: the routes
# it was meant to protect simply fall through to the default budget.
#
# Ours read `/api/v1/operations` — the name of the SERVICE rather than any path it answers, since
# operations mounts /api/v1/field, /api/v1/staff and /api/v1/till. The counter screen, the one
# path with a five-second budget and its own generous class of 600/min, ran on the default 300.
# The symptom was a catalogue arriving EMPTY under load: a visit screen with no services on it,
# no error banner, nothing in any log that named a limit.
#
# So: every prefix in RATELIMIT_ROUTES must be a prefix of at least one real declared path.
# =============================================================================
from __future__ import annotations

import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GATEWAY = ROOT / "deploy" / "services" / "api-gateway.values.yaml"

C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"


def declared_paths() -> set[str]:
    """Every path our services declare in their action catalogues and manifests."""
    paths: set[str] = set()
    for pattern in ("services/*/app/*actions*.py", "services/*/app/manifest.py"):
        for f in glob.glob(str(ROOT / pattern)):
            text = Path(f).read_text(encoding="utf-8")
            paths |= set(re.findall(r'"path":\s*"(/api/[^"]+)"', text))
    # The platform's own auth surface is served by the gateway itself and declared nowhere here.
    paths |= {"/api/v1/auth/login", "/api/v1/auth/register", "/api/v1/auth/refresh"}
    return paths


def routes() -> list[dict]:
    text = GATEWAY.read_text(encoding="utf-8")
    block = text.split("RATELIMIT_ROUTES:", 1)[1]
    start = block.index("[")
    depth, end = 0, start
    for i, ch in enumerate(block[start:], start):
        depth += (ch == "[") - (ch == "]")
        if depth == 0:
            end = i + 1
            break
    return json.loads(block[start:end])


def main() -> int:
    paths = declared_paths()
    problems: list[str] = []
    rows = routes()
    for r in rows:
        prefix = r["prefix"]
        if not any(p.startswith(prefix) for p in paths):
            problems.append(f'class "{r.get("class", prefix)}" is declared for {prefix} and no '
                            f'service serves any path under it — the limit it sets applies to '
                            f'nothing, and everything it was meant to cover runs on the default '
                            f'budget with no error anywhere')

    for p in problems:
        print(f"{C_R}  ✗ {p}{C_N}")
    if problems:
        print(f"\n{C_R}  ✗ {len(problems)} rate-limit class(es) match no real path{C_N}")
        return 1
    print(f"{C_G}  ✔ all {len(rows)} rate-limit classes cover paths that exist{C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
