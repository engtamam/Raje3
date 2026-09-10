"""Every `deploy/seed/bootstrap-*.sh` must be called from `deploy/bring-up.sh`.

FOUND TWICE, SAME ROOT CAUSE. The booking Flow's bootstrap script was written, correct, tested —
and missing from `bring-up.sh` until 2026-09-08, found the same day as an unrelated gate
(`check_listed_apps_are_wired.py`) caught its own instance of the same shape: a feature finished
in code with no install-chain step to make it real on a fresh cluster. The subscription-renewal
Flow's own bootstrap script repeated the exact same gap minutes after being written, caught only
because a human asked "would a fresh install actually work end to end" rather than by any gate —
until this one.

THE RULE: a `bootstrap-*.sh` file existing in `deploy/seed/` is a promise that something runs it.
`bring-up.sh` is the one script `deploy/bring-up.sh`'s own install chain calls end to end on a
fresh cluster; a bootstrap script it never mentions is code that works, reviewed, tested, and
silently absent from every install that was not hand-run by whoever wrote it.
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SEED = ROOT / "deploy" / "seed"
BRING_UP = ROOT / "deploy" / "bring-up.sh"


def main() -> int:
    if not SEED.is_dir():
        print("no deploy/seed/ directory — this gate cannot answer, so it refuses to")
        return 1
    if not BRING_UP.is_file():
        print("no deploy/bring-up.sh — this gate cannot answer, so it refuses to")
        return 1

    scripts = sorted(SEED.glob("bootstrap-*.sh"))
    if not scripts:
        print("no deploy/seed/bootstrap-*.sh files found — this gate needs re-pointing")
        return 1

    bring_up_text = BRING_UP.read_text(encoding="utf-8")

    missing = [s.name for s in scripts if s.name not in bring_up_text]
    if missing:
        print(f"{len(missing)} bootstrap script(s) exist but are never called from "
              f"deploy/bring-up.sh:")
        for name in missing:
            print(f"  deploy/seed/{name}")
        print("\nA fresh install runs deploy/bring-up.sh end to end and nothing else — a "
              "bootstrap script it does not call simply never runs, on any install nobody hand-"
              "ran it on. Add a `soft \"<name>\" bash \"$HERE/seed/<script>\"` line alongside the "
              "existing Flow bootstrap calls.")
        return 1
    print(f"{len(scripts)} bootstrap script(s) in deploy/seed/: every one is called from "
          f"deploy/bring-up.sh")
    return 0


if __name__ == "__main__":
    sys.exit(main())
