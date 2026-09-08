#!/usr/bin/env python3
"""Every action in every user_actions.py/admin_actions.py carries real `help` text.

WHY THIS EXISTS. A review of the whole catalog found the field organically, half
adopted: some services had it on every action, others on none — `services/bookings/app/
user_actions.py` had zero of eleven, `services/affiliate-service/app/admin_actions.py` had two
of thirty. Nothing enforced it, so a new action could ship forever with no explanation a
non-technical shop owner could read, and nobody would notice: the screen renders, the button
works, `help` is simply absent.

THIS IS THE SAME SHAPE AS check_operator_translations_are_complete.py, one层 up. That gate makes
sure a key that exists in Arabic exists in every OTHER locale too; this one makes sure `help`
exists AT ALL, for every declared action, in every service — the floor beneath the translation
question, not a duplicate of it.

WHAT COUNTS AS MISSING: no `help` key, an empty string, or whitespace only. A one-word `help` is
still a real gap this gate cannot see — writing an ACTUALLY USEFUL sentence is a human job, same
as it always was; this only refuses the state where nobody tried at all.

    python ci/check_every_action_has_help.py
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVICES = ROOT / "services"

C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"

VARS = ("USER_ACTIONS", "ADMIN_ACTIONS")


def _actions_missing_help(path: pathlib.Path) -> list[str]:
    """Every action id in this file with no real `help` — read via the AST, the same
    ast.literal_eval-safe way every other catalog gate in this repo reads these files, so a
    computed value (a variable, an f-string) fails the SAME way it fails at import time rather
    than being silently skipped here."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    missing: list[str] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.AnnAssign) and getattr(node.target, "id", "") in VARS):
            continue
        for elt in getattr(node.value, "elts", []):
            try:
                entry = ast.literal_eval(elt)
            except Exception:                                       # noqa: BLE001
                continue
            if not isinstance(entry, dict):
                continue
            aid = entry.get("id") or entry.get("action") or "?"
            help_text = entry.get("help")
            if not isinstance(help_text, str) or not help_text.strip():
                missing.append(str(aid))
    return missing


def main() -> int:
    if not SERVICES.is_dir():
        print(f"{C_R}  ✘ no services/ directory — this gate has nothing to check{C_N}")
        return 1

    problems: list[str] = []
    checked_files = 0

    for svc in sorted(p for p in SERVICES.iterdir() if p.is_dir()):
        for fname in ("user_actions.py", "admin_actions.py"):
            f = svc / "app" / fname
            if not f.is_file():
                continue
            checked_files += 1
            rel = f.relative_to(ROOT).as_posix()
            try:
                missing = _actions_missing_help(f)
            except SyntaxError as exc:
                problems.append(f"{rel}: does not parse — {exc}")
                continue
            if missing:
                shown = ", ".join(missing[:8])
                more = f" (+{len(missing) - 8} more)" if len(missing) > 8 else ""
                problems.append(f"{rel}: {len(missing)} action(s) with no real `help`: "
                                f"{shown}{more}")

    if not checked_files:
        print(f"{C_R}  ✘ no user_actions.py/admin_actions.py found anywhere under services/ — "
              f"this gate has nothing to check, which is not the same as finding nothing wrong"
              f"{C_N}")
        return 1

    if problems:
        print(f"{C_R}  ✘ {len(problems)} catalog file(s) declare an action with no real help "
              f"text:{C_N}")
        for p in problems:
            print(f"      {p}")
        print(f"\n  Add a real, plain-language `help` string to each — read the action's own "
              f"route before writing it.")
        return 1

    print(f"{C_G}  ✔ every action in {checked_files} catalog file(s) carries real help text"
          f"{C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
