#!/usr/bin/env python3
"""Every deploy/kb/shop/*.json entry is well-formed, before it ever reaches the cluster.

WHY THIS IS A GATE AND NOT JUST A DEPLOY-SCRIPT CHECK. deploy/kb/sync-shop-kb.sh applies these
files as a ConfigMap, and assistant-service's own parse_kb refuses a bad entry by failing the
WHOLE load — one malformed file would take down every anchor across all nine shop screens, not
just its own. Catching that at DEPLOY time (inside sync-shop-kb.sh) means it is only ever found the
day someone actually runs the sync — which could be long after the bad commit landed, by someone
who did not write it, with no idea which of the nine files is the culprit. A gate catches it on the
same commit, in review, same as every other check in this repo.

WHAT THIS CHECKS, matching exactly what assistant-service's own `parse_kb`/`parse_entry`
(platform/services/assistant-service/app/core/kb.py) will accept, plus two rules specific to how
this repo's own files are organised into a directory:

  - every file parses as JSON and is a bare array of entries (the shape sync-shop-kb.sh's
    ConfigMap expects, and parse_kb's own "list" branch);
  - id and anchor are both present and IDENTICAL (this repo's own convention — see any file in
    deploy/kb/shop/ — so a screen's `<AssistantHint anchor="x">` always finds the entry named `x`);
  - title/body are explicit `{"ar": "..."}` maps, never a bare string (a bare string is stored
    under kb.py's internal DEFAULT_LANG, "en" — not wrong, since `text()` falls back to any
    language present, but every entry in this repo is meant to be genuinely Arabic-first, and a
    silently-"en"-keyed entry is how that would go unnoticed);
  - no id is duplicated ACROSS files — parse_kb's own directory-merge in file.py raises on this at
    load time (a "last-one-wins" here would silently drop half of two authors' work), so this
    gate catches it before that 500 in production.

    python ci/check_shop_kb_is_valid.py
"""
from __future__ import annotations

import glob
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
KB_DIR = ROOT / "deploy" / "kb" / "shop"

C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"


def main() -> int:
    files = sorted(KB_DIR.glob("*.json")) if KB_DIR.is_dir() else []
    if not files:
        print(f"{C_R}  ✘ no *.json files under {KB_DIR} — this gate has nothing to check, which "
              f"is not the same as finding nothing wrong{C_N}")
        return 1

    problems: list[str] = []
    seen: dict[str, str] = {}
    total = 0

    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        try:
            entries = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            problems.append(f"{rel}: not valid JSON ({exc})")
            continue
        if not isinstance(entries, list):
            problems.append(f"{rel}: must be a JSON array of entries, got "
                            f"{type(entries).__name__}")
            continue

        for i, e in enumerate(entries):
            where = f"{rel}#{i}"
            if not isinstance(e, dict):
                problems.append(f"{where}: entry is not an object")
                continue
            eid, anchor = e.get("id"), e.get("anchor")
            if not isinstance(eid, str) or not eid.strip():
                problems.append(f"{where}: missing or empty 'id'")
                continue
            if anchor != eid:
                problems.append(f"{where} ({eid!r}): 'anchor' must equal 'id' exactly, "
                                f"got {anchor!r}")
            if eid in seen:
                problems.append(f"{rel}: duplicate id {eid!r}, already declared in {seen[eid]}")
            else:
                seen[eid] = rel
            for field in ("title", "body"):
                v = e.get(field)
                if not isinstance(v, dict) or "ar" not in v or not str(v.get("ar") or "").strip():
                    problems.append(f"{where} ({eid!r}): {field!r} must be a non-empty "
                                    f"{{'ar': ...}} map")
            total += 1

    if problems:
        print(f"{C_R}  ✘ {len(problems)} problem(s) across {len(files)} file(s) under "
              f"deploy/kb/shop/:{C_N}")
        for p in problems:
            print(f"      {p}")
        return 1

    print(f"{C_G}  ✔ {total} entries across {len(files)} file(s) under deploy/kb/shop/ — all "
          f"valid, no duplicate ids{C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
