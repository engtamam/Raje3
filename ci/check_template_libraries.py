#!/usr/bin/env python3
# =============================================================================
# check_template_libraries.py — the reviewed spec and the curated library say the same thing.
#
# ONE FILE ON DISK NOW (2026-09-13) — `services/operations/data/…seed.json`, the CURATED set
# operations holds and pushes into a tenant's registry when they connect, carrying the fields the
# spec has no opinion about: the label an operator reads, the button, who fills each variable, the
# reminder model, and whether it is active. The comparison below is against the SPEC ITSELF
# (docs/وصف-منصة-راجع.md, parsed fresh by `gen_templates.parse`/`build` — never a second stored
# file that could go stale between an edit to the spec and this check catching it, which is
# exactly how it went stale before this rewrite).
#
# WHAT WENT WRONG WITHOUT THIS CHECK. They drifted by three whole types. The runtime library —
# the one that actually reaches Meta for a real establishment — held 23 while the spec defined 26:
# `per_weekly_digest`, `wrn_safety_notice` and `per_dsar_code` existed in the document and in the
# code that sends them, and were never submitted for anybody. Every one of them was a finished
# feature that could not send a single message, and nothing failed loudly: the send path checks
# approval and correctly declines a template no account ever had.
#
# SO THE OVERLAP IS COMPARED, NOT THE WHOLE FILE. Type, tone, class, category and the BODY TEXT
# must match exactly — those are the spec's to decide, and a body that differs by one word is two
# different messages under one approved name. The curated fields are operations' own and are not
# looked at here.
# =============================================================================
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CURATED = ROOT / "services" / "operations" / "data" / "templates.seed.json"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gen_templates import build, parse  # noqa: E402

C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"


def main() -> int:
    types, problems = parse()
    if problems:
        # The spec itself does not parse cleanly — gen_templates.py's own run already prints why
        # in detail; this check has nothing to compare against until that is fixed.
        print(f"{C_R}  ✗ the specification itself has {len(problems)} problem(s) — run "
              f"`python ci/gen_templates.py` for detail{C_N}")
        return 1
    lib = build(types)
    ops = json.loads(CURATED.read_text(encoding="utf-8"))["templates"]

    want: dict[str, dict] = {}
    for t in lib["types"]:
        for tone, body in t["tones"].items():
            want[f"{t['name']}_{tone}"] = {"body": body, "class": t["cls"],
                                           "category": t["category"], "header": t["header"]}
    got = {t["name"]: t for t in ops}

    problems: list[str] = []
    for name in sorted(set(want) - set(got)):
        problems.append(f"{name} is in the specification and NOT in the curated library — it is "
                        f"never submitted for any establishment, so every send of it is declined "
                        f"for want of approval, silently")
    for name in sorted(set(got) - set(want)):
        problems.append(f"{name} is in the curated library and not in the specification — it is "
                        f"submitted to Meta under wording nobody reviewed")
    for name in sorted(set(want) & set(got)):
        for field in ("body", "class", "category", "header"):
            if str(got[name].get(field, "")) != str(want[name][field]):
                problems.append(f"{name}: {field} differs — spec says {want[name][field]!r}, the "
                                f"curated library says {got[name].get(field)!r}. A name is frozen "
                                f"after Meta approves it, so this is two messages under one name")

    for p in problems:
        print(f"{C_R}  ✗ {p}{C_N}")
    if problems:
        print(f"\n{C_R}  ✗ the two template libraries disagree on {len(problems)} point(s){C_N}")
        return 1
    print(f"{C_G}  ✔ both template libraries carry the same {len(want)} templates, word for word{C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
