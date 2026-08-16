"""A name that does not exist — the bug that ships green and dies on the first real call.

WHY THIS EXISTS. `services/operations/app/api/internal.py` called `_svc(request)` in the customer
DSAR route. There is no `_svc` in that module, and there never was. Python does not notice until the
line runs, so import succeeded, the app booted, every test passed — and every privacy request a
customer made through his own page returned 500 and was never recorded. The one path a regulator
asks about, dead, silently, with no row anywhere to show it was ever attempted.

A unit test cannot catch this class: it only fails on the line that is actually executed, and the
lines that carry these are the rare ones — an error branch, an admin route, a monthly cron. Those
are exactly the paths nobody exercises until the day they matter.

WHAT IT CHECKS, AND ONLY THIS. pyflakes' undefined-name family:

    F821  undefined name          — the one above
    F811  redefinition of unused  — the second definition silently wins, so the first is dead
    F841  local assigned, never used — usually a result that was meant to be returned or checked

NO ALLOW-LIST FOR F821. There is no version of "this name is meant not to exist". The other two are
listed here because in this codebase they have each hidden a real defect, and because a rule with an
exception nobody can name is a rule that will be argued with at the worst moment.

IT FAILS ON ITS OWN ABSENCE. If pyflakes is not installed, this exits non-zero rather than printing
a green line — a check that quietly does nothing is worse than no check, because the repository then
carries a claim that is not true.

    python ci/check_undefined_names.py
"""
from __future__ import annotations

import pathlib
import re
import subprocess  # nosec B404 — runs pyflakes on our own tree, no user input
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
C_G, C_R, C_Y, C_N = "\033[32m", "\033[31m", "\033[33m", "\033[0m"

# OUR CODE ONLY. platform/ is a read-only submodule — reporting its lint would be noise we are not
# allowed to act on, and would train everyone to ignore this gate's output.
TREES = ["services", "apps", "ci", "deploy"]

# The messages that mean "this cannot work when the line runs".
FATAL = (
    ("undefined name", "the name does not exist — this line raises NameError when it runs"),
    ("undefined local", "used before it is assigned on this path"),
)
# Ones that are almost always a defect wearing a warning's clothes.
SUSPECT = (
    ("redefinition of unused", "the earlier definition is dead — the second one silently wins"),
    ("local variable", "assigned and never used — a result that was meant to be returned or checked"),
)


def python_files() -> list[pathlib.Path]:
    out: list[pathlib.Path] = []
    for tree in TREES:
        base = ROOT / tree
        if not base.exists():
            continue
        out.extend(p for p in base.rglob("*.py")
                   if "__pycache__" not in p.parts
                   and ".venv" not in p.parts
                   and "node_modules" not in p.parts)
    return sorted(out)


def main() -> int:
    try:
        import pyflakes  # noqa: F401
    except ImportError:
        print(f"{C_R}  ✘ pyflakes is not installed — this check cannot run, and a check that "
              f"cannot run must not report success.{C_N}")
        print(f"{C_R}    pip install pyflakes{C_N}")
        return 1

    files = python_files()
    if not files:
        print(f"{C_R}  ✘ found no Python files to check — the paths in TREES are wrong{C_N}")
        return 1

    # BATCHED, because Windows caps a command line at 32k characters and this tree is well past it.
    # A gate that dies on the platform it runs on is a gate nobody keeps.
    out_lines: list[str] = []
    for start in range(0, len(files), 80):
        batch = files[start:start + 80]
        proc = subprocess.run(  # nosec B603
            [sys.executable, "-m", "pyflakes", *[str(p) for p in batch]],
            capture_output=True, text=True, cwd=ROOT)
        if proc.returncode not in (0, 1) or (proc.stderr.strip() and not proc.stdout.strip()):
            print(f"{C_R}  ✘ pyflakes failed to run: {proc.stderr.strip()[:400]}{C_N}")
            return 1
        out_lines.extend((proc.stdout or "").splitlines())

    fatal: list[str] = []
    suspect: list[str] = []
    for raw in out_lines:
        line = raw.strip()
        if not line:
            continue
        low = line.lower()
        # Paths come back absolute; make them repo-relative so the output is clickable.
        line = line.replace(str(ROOT) + "\\", "").replace(str(ROOT) + "/", "").replace("\\", "/")
        if any(k in low for k, _ in FATAL):
            fatal.append(line)
        elif any(k in low for k, _ in SUSPECT):
            suspect.append(line)

    # pyflakes exits 1 when it reports anything at all, so its status is not the signal — but a
    # crash (2, or a stderr with no findings) is, and swallowing it would be the silent skip this
    # file exists to refuse.
    if proc.returncode not in (0, 1) or (proc.stderr.strip() and not proc.stdout.strip()):
        print(f"{C_R}  ✘ pyflakes failed to run: {proc.stderr.strip()[:400]}{C_N}")
        return 1

    if suspect:
        print(f"{C_Y}  ~ {len(suspect)} name(s) that usually mean a defect:{C_N}")
        for line in suspect[:40]:
            print(f"{C_Y}      {line}{C_N}")

    if fatal:
        print(f"{C_R}  ✘ {len(fatal)} name(s) that do not exist — each raises NameError the "
              f"moment its line runs:{C_N}")
        for line in fatal:
            print(f"{C_R}      {line}{C_N}")
        return 1

    print(f"{C_G}  ✔ every name resolves ({len(files)} files){C_N}")
    return 0 if not suspect else 0


if __name__ == "__main__":
    sys.exit(main())
