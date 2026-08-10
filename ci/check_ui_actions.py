#!/usr/bin/env python3
"""Every action id the UI names is one a service actually declares.

THE RULE THIS ENFORCES was agreed before a line of the console was written: the UI never composes a
path. It names an ACTION, and the catalogue supplies the method, the path and the capability. That
rule removes a whole class of mistakes — a wrong URL, a stale param, a button rendered for someone
the server will refuse — and replaces it with exactly one new way to be wrong: naming an id that
does not exist.

AND THAT ONE FAILS SILENTLY, WHICH IS WHY IT NEEDS A GATE. The catalogue legitimately omits actions
the caller may not use, so a screen looking for a missing id sees the same thing as a screen looking
for one this person lacks: nothing. A section simply does not render. Nobody is refused, nothing
errors, no log line appears — the feature is just absent, for everyone, for ever.

It happened while writing the very first nav: `operations.recent_customers` (the real id is
`operations.recent`) and `loyalty.get_settings` (`loyalty.settings.read`). Both plausible, both
wrong, and both would have silently deleted a section from every owner's console.

WHAT IT READS. The backend side is parsed with ast from each service's user_actions/admin_actions —
the same literals the CI gates and the gateway read, so there is one source. The UI side is every
string literal in apps/ that looks like an action id and appears where the catalogue is consulted.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT / "services"
APPS = ROOT / "apps"

C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"


def declared() -> set[str]:
    """Every action id any service declares, in either catalogue."""
    out: set[str] = set()
    for svc in sorted(p for p in SERVICES.iterdir() if (p / "app").is_dir()):
        for name in ("user_actions.py", "admin_actions.py"):
            f = svc / "app" / name
            if not f.exists():
                continue
            try:
                tree = ast.parse(f.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not (isinstance(node, ast.List) and node.elts
                        and isinstance(node.elts[0], ast.Dict)):
                    continue
                for e in node.elts:
                    if not isinstance(e, ast.Dict):
                        continue
                    for k, v in zip(e.keys, e.values):
                        if (isinstance(k, ast.Constant) and k.value == "id"
                                and isinstance(v, ast.Constant)):
                            out.add(str(v.value))
                break
    return out


# An id looks like `service.thing` or `service.thing.more`, lowercase with dots and underscores.
# Deliberately narrow: it must not match a css class, a path fragment or an English sentence.
ID = re.compile(r"'([a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+)'")

# Where in the UI an id is meaningful. A string that merely looks like one elsewhere — a file name,
# a mime type — is not this check's business.
USES = re.compile(r"requires:\s*\[([^\]]*)\]|action\(\s*\w+\s*,\s*('[^']+')|hasAll\(\s*\w+\s*,\s*([^)]*)\)")


def used() -> dict[str, list[str]]:
    """id -> the files that name it."""
    out: dict[str, list[str]] = {}
    for f in sorted(APPS.rglob("*.ts*")):
        if "node_modules" in f.parts or "dist" in f.parts:
            continue
        try:
            src = f.read_text(encoding="utf-8")
        except OSError:
            continue
        for m in USES.finditer(src):
            for group in m.groups():
                if not group:
                    continue
                for hit in ID.findall(group):
                    out.setdefault(hit, []).append(f.relative_to(ROOT).as_posix())
    return out


have = declared()
problems: list[str] = []
for action_id, files in sorted(used().items()):
    if action_id not in have:
        near = sorted(h for h in have if h.split(".")[0] == action_id.split(".")[0])
        hint = f" — that service declares: {', '.join(near)}" if near else ""
        problems.append(
            f"{files[0]}: names `{action_id}`, which no service declares. The catalogue would "
            f"simply not contain it, so the screen renders nothing and nobody is told{hint}")

if problems:
    print(f"{C_R}  ✗ {len(problems)} unknown action id(s) in the UI:{C_N}")
    for p in problems:
        print(f"    {C_R}{p}{C_N}")
    sys.exit(1)

n = len(used())
print(f"{C_G}  ✔ every action id the UI names is declared by a service "
      f"({n} id(s) checked against {len(have)} declared){C_N}")
